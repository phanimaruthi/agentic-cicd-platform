"""Provider-specific webhook parsers into provider-neutral event models."""

from __future__ import annotations

from typing import Any

from agentic_cicd.events.models import PullRequestAction, PullRequestEvent, SCMProvider


def _normalize_action(value: str | None, *, merged: bool = False) -> PullRequestAction:
    if merged:
        return PullRequestAction.MERGED
    if not value:
        return PullRequestAction.UNKNOWN
    value = value.lower()
    mapping = {
        "open": PullRequestAction.OPENED,
        "opened": PullRequestAction.OPENED,
        "reopen": PullRequestAction.REOPENED,
        "reopened": PullRequestAction.REOPENED,
        "synchronize": PullRequestAction.SYNCHRONIZE,
        "update": PullRequestAction.UPDATED,
        "updated": PullRequestAction.UPDATED,
        "close": PullRequestAction.CLOSED,
        "closed": PullRequestAction.CLOSED,
        "merge": PullRequestAction.MERGED,
        "merged": PullRequestAction.MERGED,
        "labeled": PullRequestAction.LABELED,
    }
    return mapping.get(value, PullRequestAction.UNKNOWN)


def parse_github_pull_request(payload: dict[str, Any], *, repo_path: str = ".") -> PullRequestEvent:
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    base = pr.get("base", {})
    head = pr.get("head", {})
    labels = [label.get("name", "") for label in pr.get("labels", []) if isinstance(label, dict)]
    merged = bool(pr.get("merged"))
    return PullRequestEvent(
        provider=SCMProvider.GITHUB,
        action=_normalize_action(payload.get("action"), merged=merged),
        repository=repo.get("full_name") or repo.get("name") or "unknown",
        repo_path=repo_path,
        pr_number=str(pr.get("number") or payload.get("number") or "unknown"),
        title=pr.get("title") or "Untitled pull request",
        author=(pr.get("user") or {}).get("login"),
        source_branch=head.get("ref") or "unknown",
        target_branch=base.get("ref") or repo.get("default_branch") or "main",
        default_branch=repo.get("default_branch") or "main",
        commit_sha=(head.get("sha") or pr.get("merge_commit_sha")),
        merged=merged,
        labels=[label for label in labels if label],
        changed_files=[],
        raw_event=payload,
    )


def parse_gitlab_merge_request(payload: dict[str, Any], *, repo_path: str = ".") -> PullRequestEvent:
    attrs = payload.get("object_attributes", {})
    project = payload.get("project", {})
    labels = [label.get("title", "") for label in payload.get("labels", []) if isinstance(label, dict)]
    state = str(attrs.get("state") or "").lower()
    action = attrs.get("action") or state
    merged = state == "merged" or action == "merge"
    last_commit = attrs.get("last_commit") or payload.get("last_commit") or {}
    return PullRequestEvent(
        provider=SCMProvider.GITLAB,
        action=_normalize_action(str(action), merged=merged),
        repository=project.get("path_with_namespace") or project.get("name") or "unknown",
        repo_path=repo_path,
        pr_number=str(attrs.get("iid") or attrs.get("id") or "unknown"),
        title=attrs.get("title") or "Untitled merge request",
        author=(payload.get("user") or {}).get("username"),
        source_branch=attrs.get("source_branch") or "unknown",
        target_branch=attrs.get("target_branch") or project.get("default_branch") or "main",
        default_branch=project.get("default_branch") or "main",
        commit_sha=last_commit.get("id") if isinstance(last_commit, dict) else None,
        merged=merged,
        labels=[label for label in labels if label],
        changed_files=[],
        raw_event=payload,
    )


def parse_pull_request_event(provider: SCMProvider | str, payload: dict[str, Any], *, repo_path: str = ".") -> PullRequestEvent:
    provider = SCMProvider(provider)
    if provider == SCMProvider.GITHUB:
        return parse_github_pull_request(payload, repo_path=repo_path)
    if provider == SCMProvider.GITLAB:
        return parse_gitlab_merge_request(payload, repo_path=repo_path)
    raise ValueError(f"provider {provider.value!r} is not implemented for pull request parsing")
