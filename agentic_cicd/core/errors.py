"""Typed error hierarchy for structured failures."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import FailureCategory


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    category: FailureCategory = FailureCategory.UNKNOWN
    retryable: bool = False
    safe_to_retry: bool = False
    action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = Field(default_factory=lambda: str(uuid4()))


class PlatformError(Exception):
    """Base exception carrying a typed error envelope."""

    code = "PLATFORM_ERROR"
    category = FailureCategory.UNKNOWN
    retryable = False
    safe_to_retry = False

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        category: FailureCategory | None = None,
        retryable: bool | None = None,
        safe_to_retry: bool | None = None,
        action: str | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.envelope = ErrorEnvelope(
            code=code or self.code,
            message=message,
            category=category or self.category,
            retryable=self.retryable if retryable is None else retryable,
            safe_to_retry=self.safe_to_retry if safe_to_retry is None else safe_to_retry,
            action=action,
            metadata=metadata or {},
            trace_id=trace_id or str(uuid4()),
        )
        super().__init__(self.envelope.message)

    def to_dict(self) -> dict[str, Any]:
        return self.envelope.model_dump(mode="json")


class ToolExecutionError(PlatformError):
    code = "TOOL_EXECUTION_ERROR"


class PolicyDeniedError(PlatformError):
    code = "POLICY_DENIED"
    category = FailureCategory.POLICY


class AuthorizationError(PlatformError):
    code = "AUTHORIZATION_ERROR"
    category = FailureCategory.AUTHORIZATION


class RunnerUnavailableError(PlatformError):
    code = "RUNNER_UNAVAILABLE"
    category = FailureCategory.CONFIGURATION


class PipelineValidationError(PlatformError):
    code = "PIPELINE_VALIDATION_ERROR"
    category = FailureCategory.CONFIGURATION


class ContextUnavailableError(PlatformError):
    code = "CONTEXT_REQUIRED"
    category = FailureCategory.CONFIGURATION


class InfrastructureError(PlatformError):
    code = "INFRASTRUCTURE_ERROR"
    category = FailureCategory.INFRASTRUCTURE


class SecurityGateError(PlatformError):
    code = "SECURITY_GATE_ERROR"
    category = FailureCategory.SECURITY


class ApprovalRequiredError(PlatformError):
    code = "APPROVAL_REQUIRED"
    category = FailureCategory.POLICY


class DeploymentVerificationError(PlatformError):
    code = "DEPLOYMENT_VERIFICATION_ERROR"
    category = FailureCategory.DEPLOYMENT


class RemediationError(PlatformError):
    code = "REMEDIATION_ERROR"
    category = FailureCategory.UNKNOWN
