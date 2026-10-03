"""Typed API schemas for future HTTP exposure."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import PipelineBackend, Role
from agentic_cicd.core.execution import ExecutionRecord
from agentic_cicd.core.pipeline import PipelineIR
from agentic_cicd.policies.engine import PolicyReport


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    repository_path: str = "."
    principal_id: str = "local-user"
    roles: set[Role] = Field(default_factory=lambda: {Role.DEVELOPER})
    dry_run: bool = True


class PipelineGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    repository_path: str = "."
    backend: PipelineBackend = PipelineBackend.NATIVE


class PipelineGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineIR
    rendered: str | None = None
    explanation: dict[str, object]


class PipelineValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineIR


class PipelineValidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    errors: list[dict[str, object]] = Field(default_factory=list)
    policy_report: PolicyReport | None = None


class PipelineExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineIR
    repository_path: str = "."
    dry_run: bool = True
    approved: bool = False


class PipelineExecuteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: ExecutionRecord


class PullRequestWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    payload: dict[str, object]
    repository_path: str = "."
    principal_id: str = "webhook-bot"
    roles: set[Role] = Field(default_factory=lambda: {Role.DEVELOPER})
    dry_run: bool = True
    approved: bool = False


class PullRequestWebhookResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: dict[str, object]
