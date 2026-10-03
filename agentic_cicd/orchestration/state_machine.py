"""Explicit workflow state transition model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import WorkflowState
from agentic_cicd.core.errors import PlatformError

ALLOWED_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
    WorkflowState.RECEIVED: {WorkflowState.CLASSIFIED},
    WorkflowState.CLASSIFIED: {WorkflowState.DISCOVERING},
    WorkflowState.DISCOVERING: {WorkflowState.CONTEXT_READY, WorkflowState.FAILED},
    WorkflowState.CONTEXT_READY: {WorkflowState.PLANNING},
    WorkflowState.PLANNING: {WorkflowState.POLICY_CHECK, WorkflowState.FAILED},
    WorkflowState.POLICY_CHECK: {WorkflowState.PLAN_READY, WorkflowState.APPROVAL_REQUIRED, WorkflowState.FAILED},
    WorkflowState.PLAN_READY: {WorkflowState.VALIDATING},
    WorkflowState.VALIDATING: {WorkflowState.EXECUTING, WorkflowState.APPROVAL_REQUIRED, WorkflowState.FAILED},
    WorkflowState.APPROVAL_REQUIRED: {WorkflowState.EXECUTING, WorkflowState.FAILED},
    WorkflowState.EXECUTING: {WorkflowState.VERIFYING, WorkflowState.DIAGNOSING, WorkflowState.FAILED},
    WorkflowState.VERIFYING: {WorkflowState.COMPLETED, WorkflowState.DIAGNOSING, WorkflowState.FAILED},
    WorkflowState.DIAGNOSING: {WorkflowState.REMEDIATION_PLANNED, WorkflowState.FAILED},
    WorkflowState.REMEDIATION_PLANNED: {WorkflowState.POLICY_CHECK, WorkflowState.REMEDIATING},
    WorkflowState.REMEDIATING: {WorkflowState.REEXECUTING, WorkflowState.FAILED},
    WorkflowState.REEXECUTING: {WorkflowState.VERIFYING, WorkflowState.FAILED},
    WorkflowState.COMPLETED: set(),
    WorkflowState.FAILED: set(),
}


class WorkflowStateMachine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: WorkflowState = WorkflowState.RECEIVED
    history: list[WorkflowState] = Field(default_factory=lambda: [WorkflowState.RECEIVED])

    def transition(self, target: WorkflowState) -> None:
        if target not in ALLOWED_TRANSITIONS[self.state]:
            raise PlatformError(
                "invalid workflow state transition",
                metadata={"from": self.state.value, "to": target.value},
            )
        self.state = target
        self.history.append(target)
