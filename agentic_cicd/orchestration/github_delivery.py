"""GitHub PR delivery orchestration.

This composes the provider-neutral pull request control plane with the optional
GitHub commit status adapter. It is safe by default: GitHub mutations are dry-run
unless `send_status=True` and `GITHUB_TOKEN` is configured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from agentic_cicd.core.identity import Principal
from agentic_cicd.events.parsers import parse_github_pull_request
from agentic_cicd.integrations.github import (
    GitHubClient,
    GitHubStatusRequest,
    GitHubStatusResult,
    execution_status_to_github_state,
)
from agentic_cicd.orchestration.control_plane import PipelineRunBundle, PullRequestControlPlane


class GitHubDeliveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    bundle: PipelineRunBundle
    pending_status: GitHubStatusResult | None = None
    final_status: GitHubStatusResult | None = None

    def summary(self) -> dict[str, Any]:
        control_plane = PullRequestControlPlane()
        data = control_plane.bundle_summary(self.bundle)
        data["github_pending_status"] = self.pending_status.model_dump(mode="json") if self.pending_status else None
        data["github_final_status"] = self.final_status.model_dump(mode="json") if self.final_status else None
        return data


class GitHubPRDeliveryService:
    def __init__(
        self,
        *,
        control_plane: PullRequestControlPlane | None = None,
        github: GitHubClient | None = None,
    ) -> None:
        self.control_plane = control_plane or PullRequestControlPlane()
        self.github = github or GitHubClient()

    def handle_payload(
        self,
        payload: dict[str, Any],
        principal: Principal,
        *,
        repo_path: str = ".",
        dry_run_pipeline: bool = True,
        approved: bool = False,
        report_path: str | Path | None = None,
        send_status: bool = False,
        status_target_url: str | None = None,
    ) -> GitHubDeliveryResult:
        event = parse_github_pull_request(payload, repo_path=repo_path)
        repository = event.repository
        sha = event.commit_sha or "unknown"
        pending = self.github.set_commit_status(
            repository,
            sha,
            GitHubStatusRequest(
                state=execution_status_to_github_state("RUNNING"),
                description="Agentic CI/CD pipeline started",
                target_url=status_target_url,
            ),
            dry_run=not send_status,
        )
        bundle = self.control_plane.handle_pull_request(
            event,
            principal,
            dry_run=dry_run_pipeline,
            approved=approved,
            report_path=report_path,
        )
        final = self.github.set_commit_status(
            repository,
            sha,
            GitHubStatusRequest(
                state=execution_status_to_github_state(bundle.execution.status.value),
                description=f"Agentic CI/CD finished: {bundle.execution.status.value}",
                target_url=status_target_url or bundle.report_path,
            ),
            dry_run=not send_status,
        )
        return GitHubDeliveryResult(bundle=bundle, pending_status=pending, final_status=final)
