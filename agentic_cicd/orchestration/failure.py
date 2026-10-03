"""Failure intelligence and bounded remediation planning."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import FailureCategory
from agentic_cicd.core.execution import TaskExecutionResult
from agentic_cicd.core.task import TaskSpec


class FailureDiagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    category: FailureCategory
    probable_root_cause: str
    confidence: float = Field(ge=0, le=1)
    retryable: bool
    evidence: list[str] = Field(default_factory=list)


class RemediationAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    risk: str
    automatic: bool
    command: list[str] = Field(default_factory=list)


class RemediationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    bounded: bool = True
    actions: list[RemediationAction] = Field(default_factory=list)
    rerun_affected_only: bool = True
    requires_approval: bool = False
    explanation: str


class FailureAnalyzer:
    def analyze(self, task: TaskSpec, result: TaskExecutionResult) -> FailureDiagnosis:
        text = f"{result.stdout}\n{result.stderr}".lower()
        evidence = [line for line in (result.stderr or result.stdout).splitlines()[:5] if line]
        if result.failure_category:
            category = result.failure_category
        elif "assert" in text or "failed" in text and "pytest" in text:
            category = FailureCategory.TEST
        elif "modulenotfounderror" in text or "no module named" in text or "not found" in text:
            category = FailureCategory.DEPENDENCY
        elif "permission denied" in text or "forbidden" in text:
            category = FailureCategory.AUTHORIZATION
        elif "unauthorized" in text or "authentication" in text:
            category = FailureCategory.AUTHENTICATION
        elif "timed out" in text or "timeout" in text:
            category = FailureCategory.TIMEOUT
        elif "connection reset" in text or "temporary failure" in text or "transient" in text:
            category = FailureCategory.FLAKY_TRANSIENT
        elif "crashloopbackoff" in text:
            category = FailureCategory.KUBERNETES
        elif "terraform" in task.type.lower() or "terraform" in " ".join(task.command).lower():
            category = FailureCategory.INFRASTRUCTURE
        else:
            category = FailureCategory.UNKNOWN
        retryable = category in {FailureCategory.NETWORK, FailureCategory.FLAKY_TRANSIENT, FailureCategory.TIMEOUT, FailureCategory.EXTERNAL_SERVICE}
        cause = {
            FailureCategory.TEST: "test assertion or test runtime failure",
            FailureCategory.DEPENDENCY: "dependency/tooling appears missing or unresolved",
            FailureCategory.AUTHORIZATION: "operation was not authorized",
            FailureCategory.AUTHENTICATION: "authentication failed or credentials are unavailable",
            FailureCategory.TIMEOUT: "task exceeded its timeout or external service was slow",
            FailureCategory.FLAKY_TRANSIENT: "transient external/network failure is likely",
            FailureCategory.KUBERNETES: "Kubernetes workload health failure detected",
            FailureCategory.INFRASTRUCTURE: "infrastructure tool reported an error",
            FailureCategory.UNKNOWN: "insufficient structured evidence to determine root cause",
        }.get(category, "failure category detected")
        confidence = 0.8 if category != FailureCategory.UNKNOWN else 0.35
        return FailureDiagnosis(
            task_id=task.id,
            category=category,
            probable_root_cause=cause,
            confidence=confidence,
            retryable=retryable,
            evidence=evidence,
        )


class RemediationPlanner:
    def plan(self, task: TaskSpec, diagnosis: FailureDiagnosis) -> RemediationPlan:
        actions: list[RemediationAction] = []
        requires_approval = False
        if diagnosis.category == FailureCategory.FLAKY_TRANSIENT:
            actions.append(
                RemediationAction(
                    id="bounded_retry",
                    description="Retry affected task once with existing idempotency key",
                    risk="LOW_RISK",
                    automatic=True,
                )
            )
        elif diagnosis.category == FailureCategory.DEPENDENCY:
            actions.append(
                RemediationAction(
                    id="restore_dependencies",
                    description="Restore dependencies using the repository's detected package manager before rerun",
                    risk="LOW_RISK",
                    automatic=False,
                )
            )
        elif diagnosis.category == FailureCategory.KUBERNETES:
            actions.append(
                RemediationAction(
                    id="inspect_kubernetes_workload",
                    description="Collect pod logs and describe output; do not mutate cluster automatically",
                    risk="SAFE",
                    automatic=False,
                )
            )
            requires_approval = True
        elif diagnosis.category == FailureCategory.INFRASTRUCTURE:
            actions.append(
                RemediationAction(
                    id="inspect_iac_diagnostics",
                    description="Parse IaC diagnostics and run validation; do not apply fabricated changes",
                    risk="SAFE",
                    automatic=False,
                )
            )
        else:
            actions.append(
                RemediationAction(
                    id="manual_review",
                    description="Manual review required; no safe deterministic remediation identified",
                    risk="SAFE",
                    automatic=False,
                )
            )
        return RemediationPlan(
            task_id=task.id,
            actions=actions,
            requires_approval=requires_approval,
            explanation="Auto-remediation is bounded and policy-gated; deterministic failures are not blindly retried.",
        )
