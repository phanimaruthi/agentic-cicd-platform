"""Execution request/result models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import ExecutionStatus, FailureCategory
from agentic_cicd.core.errors import ErrorEnvelope
from agentic_cicd.core.pipeline import PipelineIR


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    pipeline: PipelineIR
    repo_path: str = "."
    dry_run: bool = True
    approved: bool = False
    idempotency_key: str | None = None


class TaskExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    runner_id: str
    status: ExecutionStatus
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: ErrorEnvelope | None = None
    failure_category: FailureCategory | None = None


class ExecutionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str | None = None
    pipeline_id: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    results: list[TaskExecutionResult] = Field(default_factory=list)
    policy_decisions: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    audit_event_ids: list[str] = Field(default_factory=list)
    diagnosis: list[dict[str, Any]] = Field(default_factory=list)
    remediation: list[dict[str, Any]] = Field(default_factory=list)

    def mark_finished(self, status: ExecutionStatus) -> None:
        self.status = status
        self.finished_at = datetime.now(UTC)
