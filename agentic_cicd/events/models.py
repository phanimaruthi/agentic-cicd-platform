"""Provider-neutral SCM event models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class SCMProvider(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    GENERIC = "generic"


class PullRequestAction(str, Enum):
    OPENED = "opened"
    REOPENED = "reopened"
    SYNCHRONIZE = "synchronize"
    UPDATED = "updated"
    CLOSED = "closed"
    MERGED = "merged"
    LABELED = "labeled"
    UNKNOWN = "unknown"


class PullRequestEvent(BaseModel):
    """Provider-neutral pull/merge request event.

    Repository payloads are event data, not trusted instructions. Provider-specific
    parsers normalize payloads into this model before planning.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    provider: SCMProvider
    action: PullRequestAction
    repository: str
    repo_path: str = "."
    pr_number: str
    title: str
    author: str | None = None
    source_branch: str
    target_branch: str
    default_branch: str = "main"
    commit_sha: str | None = None
    merged: bool = False
    labels: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_event: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_pr_validation(self) -> bool:
        return self.action in {
            PullRequestAction.OPENED,
            PullRequestAction.REOPENED,
            PullRequestAction.SYNCHRONIZE,
            PullRequestAction.UPDATED,
            PullRequestAction.LABELED,
        }

    @property
    def is_merge_to_default(self) -> bool:
        return self.merged and self.target_branch in {self.default_branch, "main", "master"}

    @property
    def requested_environment(self) -> str | None:
        normalized = {label.lower().replace("_", "-") for label in self.labels}
        if "deploy-production" in normalized or "production" in normalized:
            return "production"
        if "deploy-staging" in normalized or "staging" in normalized:
            return "staging"
        if self.is_merge_to_default:
            return "development"
        if "preview" in normalized or "deploy-preview" in normalized:
            return "preview"
        return None

    @property
    def should_deploy(self) -> bool:
        return self.requested_environment is not None
