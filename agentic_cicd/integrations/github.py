"""GitHub integration adapter.

The adapter is intentionally explicit about configuration. Without a token it returns
NOT_CONFIGURED/DRY_RUN results rather than pretending to update GitHub.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import RiskLevel
from agentic_cicd.integrations.base import IntegrationCapability, IntegrationStatus


class GitHubCommitState(str, Enum):
    ERROR = "error"
    FAILURE = "failure"
    PENDING = "pending"
    SUCCESS = "success"


class GitHubRepositoryRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str
    repo: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    @classmethod
    def parse(cls, value: str) -> "GitHubRepositoryRef":
        if "/" not in value:
            raise ValueError("GitHub repository must be in owner/repo form")
        owner, repo = value.split("/", 1)
        return cls(owner=owner, repo=repo)


class GitHubStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: GitHubCommitState
    context: str = "agentic-cicd/platform"
    description: str
    target_url: str | None = None


class GitHubStatusResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sent: bool
    dry_run: bool
    configured: bool
    repository: str
    sha: str
    state: GitHubCommitState
    status_code: int | None = None
    response: dict[str, Any] | None = None
    message: str


class GitHubIntegrationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_url: str = "https://api.github.com"
    token_env: str = "GITHUB_TOKEN"
    webhook_secret_env: str = "GITHUB_WEBHOOK_SECRET"
    user_agent: str = "agentic-cicd-platform/0.2"


class GitHubClient:
    id = "github-api"
    provider = "github"

    def __init__(self, config: GitHubIntegrationConfig | None = None) -> None:
        self.config = config or GitHubIntegrationConfig()

    @property
    def token(self) -> str | None:
        return os.getenv(self.config.token_env)

    @property
    def webhook_secret(self) -> str | None:
        return os.getenv(self.config.webhook_secret_env)

    def status(self) -> IntegrationStatus:
        configured = bool(self.token)
        return IntegrationStatus(
            id=self.id,
            provider=self.provider,
            implemented=True,
            configured=configured,
            healthy=configured,
            capabilities=[
                IntegrationCapability(
                    name="commit_status",
                    read_only=False,
                    mutates_external_state=True,
                    requires_credentials=True,
                ),
                IntegrationCapability(
                    name="webhook_signature_verify",
                    read_only=True,
                    mutates_external_state=False,
                    requires_credentials=True,
                ),
            ],
            message=None if configured else f"NOT_CONFIGURED: set {self.config.token_env} for GitHub API updates",
        )

    def verify_signature(self, body: bytes, signature_header: str | None, *, secret: str | None = None) -> bool:
        secret = secret if secret is not None else self.webhook_secret
        if not secret or not signature_header:
            return False
        if not signature_header.startswith("sha256="):
            return False
        expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header)

    def set_commit_status(
        self,
        repository: GitHubRepositoryRef | str,
        sha: str,
        status: GitHubStatusRequest,
        *,
        dry_run: bool = True,
    ) -> GitHubStatusResult:
        repo = GitHubRepositoryRef.parse(repository) if isinstance(repository, str) else repository
        if dry_run:
            return GitHubStatusResult(
                sent=False,
                dry_run=True,
                configured=bool(self.token),
                repository=repo.full_name,
                sha=sha,
                state=status.state,
                message="DRY_RUN: would update GitHub commit status",
                response=status.model_dump(mode="json"),
            )
        token = self.token
        if not token:
            return GitHubStatusResult(
                sent=False,
                dry_run=False,
                configured=False,
                repository=repo.full_name,
                sha=sha,
                state=status.state,
                message=f"NOT_CONFIGURED: set {self.config.token_env} to update GitHub commit status",
            )
        payload = {
            "state": status.state.value,
            "context": status.context,
            "description": status.description[:140],
        }
        if status.target_url:
            payload["target_url"] = status.target_url
        url = f"{self.config.api_url.rstrip('/')}/repos/{repo.owner}/{repo.repo}/statuses/{sha}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": self.config.user_agent,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 - fixed GitHub API URL/config
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
                return GitHubStatusResult(
                    sent=True,
                    dry_run=False,
                    configured=True,
                    repository=repo.full_name,
                    sha=sha,
                    state=status.state,
                    status_code=response.status,
                    response=data,
                    message="GitHub commit status updated",
                )
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            return GitHubStatusResult(
                sent=False,
                dry_run=False,
                configured=True,
                repository=repo.full_name,
                sha=sha,
                state=status.state,
                status_code=exc.code,
                response={"error": error_body},
                message="GitHub commit status update failed",
            )
        except urllib.error.URLError as exc:
            return GitHubStatusResult(
                sent=False,
                dry_run=False,
                configured=True,
                repository=repo.full_name,
                sha=sha,
                state=status.state,
                message=f"GitHub commit status update failed: {exc.reason}",
            )


def execution_status_to_github_state(status: str) -> GitHubCommitState:
    if status == "SUCCEEDED":
        return GitHubCommitState.SUCCESS
    if status in {"APPROVAL_REQUIRED", "PENDING", "RUNNING"}:
        return GitHubCommitState.PENDING
    if status in {"DENIED", "FAILED"}:
        return GitHubCommitState.FAILURE
    return GitHubCommitState.ERROR


GITHUB_STATUS_RISK = RiskLevel.LOW_RISK
