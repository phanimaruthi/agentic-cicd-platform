"""SCM connector interfaces and local Git implementation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.integrations.base import IntegrationCapability, IntegrationStatus


class CommitInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha: str
    branch: str | None = None
    message: str | None = None


class PullRequestInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    source_branch: str
    target_branch: str
    state: str


class SCMConnector(Protocol):
    id: str
    provider: str

    def status(self) -> IntegrationStatus:
        ...

    def changed_files(self, repo_path: str) -> list[str]:
        ...

    def current_commit(self, repo_path: str) -> CommitInfo | None:
        ...


class LocalGitConnector:
    id = "local-git"
    provider = "generic_git"

    def status(self) -> IntegrationStatus:
        return IntegrationStatus(
            id=self.id,
            provider=self.provider,
            implemented=True,
            configured=True,
            healthy=True,
            capabilities=[
                IntegrationCapability(name="changed_files", read_only=True),
                IntegrationCapability(name="current_commit", read_only=True),
            ],
        )

    def changed_files(self, repo_path: str) -> list[str]:
        root = Path(repo_path).expanduser().resolve()
        if not (root / ".git").exists():
            return []
        completed = subprocess.run(  # noqa: S603 - controlled git argv
            ["git", "diff", "--name-only", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            return []
        return [line for line in completed.stdout.splitlines() if line.strip()]

    def current_commit(self, repo_path: str) -> CommitInfo | None:
        root = Path(repo_path).expanduser().resolve()
        if not (root / ".git").exists():
            return None
        sha = self._git(root, ["rev-parse", "HEAD"])
        branch = self._git(root, ["branch", "--show-current"])
        message = self._git(root, ["log", "-1", "--pretty=%s"])
        return CommitInfo(sha=sha, branch=branch, message=message) if sha else None

    def _git(self, root: Path, args: list[str]) -> str | None:
        completed = subprocess.run(  # noqa: S603 - controlled git argv
            ["git", *args], cwd=root, capture_output=True, text=True, shell=False, timeout=10, check=False
        )
        return completed.stdout.strip() if completed.returncode == 0 and completed.stdout.strip() else None


class NotImplementedSCMConnector:
    def __init__(self, provider: str) -> None:
        self.id = f"{provider}-scm"
        self.provider = provider

    def status(self) -> IntegrationStatus:
        return IntegrationStatus(
            id=self.id,
            provider=self.provider,
            implemented=False,
            configured=False,
            healthy=False,
            message="NOT_IMPLEMENTED: remote SCM API connector is not configured",
        )
