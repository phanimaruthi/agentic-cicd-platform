from __future__ import annotations

import hashlib
import hmac
import json

from agentic_cicd.core.enums import ExecutionStatus, Role
from agentic_cicd.core.identity import Principal
from agentic_cicd.integrations.github import (
    GitHubClient,
    GitHubCommitState,
    GitHubStatusRequest,
    execution_status_to_github_state,
)
from agentic_cicd.orchestration.github_delivery import GitHubPRDeliveryService


def test_github_signature_verification() -> None:
    client = GitHubClient()
    body = b'{"hello":"world"}'
    secret = "top-secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert client.verify_signature(body, signature, secret=secret) is True
    assert client.verify_signature(body, "sha256=bad", secret=secret) is False


def test_github_status_dry_run_without_token() -> None:
    client = GitHubClient()
    result = client.set_commit_status(
        "owner/repo",
        "abc123",
        GitHubStatusRequest(state=GitHubCommitState.SUCCESS, description="ok"),
        dry_run=True,
    )
    assert result.sent is False
    assert result.dry_run is True
    assert result.repository == "owner/repo"


def test_execution_status_mapping() -> None:
    assert execution_status_to_github_state(ExecutionStatus.SUCCEEDED.value) == GitHubCommitState.SUCCESS
    assert execution_status_to_github_state(ExecutionStatus.APPROVAL_REQUIRED.value) == GitHubCommitState.PENDING
    assert execution_status_to_github_state(ExecutionStatus.FAILED.value) == GitHubCommitState.FAILURE


def test_github_pr_delivery_service_runs_pipeline_and_status_dry_run(tmp_path) -> None:
    payload = json.loads(open("samples/webhooks/github_pull_request_merged.json", encoding="utf-8").read())
    result = GitHubPRDeliveryService().handle_payload(
        payload,
        Principal(id="maintainer", roles={Role.MAINTAINER}),
        repo_path="samples/python_app",
        dry_run_pipeline=True,
        report_path=tmp_path / "report.html",
        send_status=False,
    )
    assert result.bundle.execution.status == ExecutionStatus.SUCCEEDED
    assert result.pending_status is not None and result.pending_status.dry_run is True
    assert result.final_status is not None and result.final_status.dry_run is True
    assert (tmp_path / "report.html").exists()
