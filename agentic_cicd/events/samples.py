"""Sample event builders for local demos."""

from __future__ import annotations

from agentic_cicd.events.models import PullRequestAction, PullRequestEvent, SCMProvider


def sample_pull_request_event(
    *,
    provider: SCMProvider = SCMProvider.GITHUB,
    repo_path: str = "samples/python_app",
    action: PullRequestAction = PullRequestAction.OPENED,
    merged: bool = False,
    labels: list[str] | None = None,
) -> PullRequestEvent:
    return PullRequestEvent(
        provider=provider,
        action=PullRequestAction.MERGED if merged else action,
        repository="local/sample-python-app",
        repo_path=repo_path,
        pr_number="42",
        title="Improve sample application delivery flow",
        author="local-developer",
        source_branch="feature/agentic-cicd-demo",
        target_branch="main",
        default_branch="main",
        commit_sha="local-demo-sha",
        merged=merged,
        labels=labels or [],
        changed_files=["src/sample_app/main.py", "tests/test_main.py"],
    )
