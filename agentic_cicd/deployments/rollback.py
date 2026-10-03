"""Rollback planning for policy-gated deployment recovery."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import RiskLevel, TaskCategory
from agentic_cicd.core.task import RunnerCapabilityRequest, TaskSpec
from agentic_cicd.deployments.verification import DeploymentVerificationResult


class RollbackPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    environment: str
    reason: str
    strategy: str
    tasks: list[TaskSpec] = Field(default_factory=list)
    requires_approval: bool = True
    verification_required: bool = True


class RollbackPlanner:
    def plan_from_verification(self, result: DeploymentVerificationResult) -> RollbackPlan:
        protected = result.environment == "production"
        task = TaskSpec(
            id=f"rollback_{result.environment}",
            type="rollback",
            name=f"Rollback {result.service} in {result.environment}",
            category=TaskCategory.DEPLOYMENT,
            command=["python", "-c", "print('NOT_IMPLEMENTED: rollback adapter not configured')"],
            risk=RiskLevel.HIGH_RISK if protected else RiskLevel.MEDIUM_RISK,
            side_effects=[f"would rollback {result.service} in {result.environment}"],
            required_capabilities=RunnerCapabilityRequest(tools={"python"}),
        )
        return RollbackPlan(
            service=result.service,
            environment=result.environment,
            reason="deployment verification failed" if not result.passed else "rollback requested",
            strategy="previous_stable_artifact" if protected else "latest_known_good_or_redeploy",
            tasks=[task],
            requires_approval=protected,
            verification_required=True,
        )
