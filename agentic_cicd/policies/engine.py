"""Policy-as-code and RBAC evaluation."""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.context import ContextBundle
from agentic_cicd.core.enums import (
    AutonomyLevel,
    Permission,
    PolicyDecisionType,
    RISK_ORDER,
    RiskLevel,
    TaskCategory,
)
from agentic_cicd.core.identity import AuthorizationService, Principal
from agentic_cicd.core.pipeline import PipelineIR
from agentic_cicd.core.task import TaskSpec
from agentic_cicd.security.command import classify_command


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    policy_id: str
    decision: PolicyDecisionType
    subject: str
    reason: str
    metadata: dict[str, object] = Field(default_factory=dict)


class PolicyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[PolicyDecision] = Field(default_factory=list)

    @property
    def denied(self) -> bool:
        return any(decision.decision == PolicyDecisionType.DENY for decision in self.decisions)

    @property
    def approval_required(self) -> bool:
        return any(decision.decision == PolicyDecisionType.REQUIRES_APPROVAL for decision in self.decisions)

    @property
    def warnings(self) -> list[PolicyDecision]:
        return [decision for decision in self.decisions if decision.decision == PolicyDecisionType.WARN]

    def add(self, decision: PolicyDecision) -> None:
        self.decisions.append(decision)

    def as_dicts(self) -> list[dict[str, object]]:
        return [decision.model_dump(mode="json") for decision in self.decisions]


class PolicyEngine(Protocol):
    def evaluate(
        self,
        pipeline: PipelineIR,
        principal: Principal,
        context: ContextBundle | None = None,
        *,
        dry_run: bool = False,
    ) -> PolicyReport:
        ...


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_runners: set[str] = Field(default_factory=set)
    allowed_images: set[str] = Field(default_factory=set)
    allow_destructive: bool = False
    require_security_scan_for_deploy: bool = True
    production_requires_approval: bool = True
    max_autonomous_risk: RiskLevel = RiskLevel.MEDIUM_RISK


class DefaultPolicyEngine:
    """Deterministic baseline policy engine.

    This engine can be composed with external backends (for example OPA) through the
    PolicyEngine protocol. OPA execution is intentionally not faked when unavailable.
    """

    def __init__(self, authz: AuthorizationService, config: PolicyConfig | None = None) -> None:
        self.authz = authz
        self.config = config or PolicyConfig()

    def evaluate(
        self,
        pipeline: PipelineIR,
        principal: Principal,
        context: ContextBundle | None = None,
        *,
        dry_run: bool = False,
    ) -> PolicyReport:
        report = PolicyReport()
        self._evaluate_authorization(report, pipeline, principal)
        self._evaluate_risk(report, pipeline, dry_run=dry_run)
        self._evaluate_commands(report, pipeline)
        self._evaluate_runners_and_images(report, pipeline)
        self._evaluate_security_requirements(report, pipeline)
        if context and context.repository and context.repository.secret_reference_files:
            report.add(
                PolicyDecision(
                    policy_id="secrets-metadata-warning",
                    decision=PolicyDecisionType.WARN,
                    subject=context.repository.path,
                    reason="repository contains files that look secret-related; scan before publishing logs/artifacts",
                    metadata={"files": context.repository.secret_reference_files},
                )
            )
        if not report.denied and not report.approval_required:
            report.add(
                PolicyDecision(
                    policy_id="baseline-allow",
                    decision=PolicyDecisionType.ALLOW,
                    subject=pipeline.metadata.id,
                    reason="baseline deterministic policies allow this dry-run/low-risk plan",
                )
            )
        return report

    def _evaluate_authorization(
        self, report: PolicyReport, pipeline: PipelineIR, principal: Principal
    ) -> None:
        effective = self.authz.effective_permissions(principal)
        for task in pipeline.all_steps():
            required = self._permission_for_task(task, pipeline)
            if required and required not in effective:
                report.add(
                    PolicyDecision(
                        policy_id="rbac-task-permission",
                        decision=PolicyDecisionType.DENY,
                        subject=task.id,
                        reason=f"principal lacks permission {required.value}",
                        metadata={"principal": principal.id, "required": required.value},
                    )
                )
        prod_envs = [env for env in pipeline.environments if env.name == "production" or env.protected]
        if prod_envs and Permission.DEPLOY_PRODUCTION not in effective:
            report.add(
                PolicyDecision(
                    policy_id="rbac-production-deploy",
                    decision=PolicyDecisionType.DENY,
                    subject="production",
                    reason="principal is not authorized to deploy production",
                    metadata={"principal": principal.id},
                )
            )

    def _evaluate_risk(self, report: PolicyReport, pipeline: PipelineIR, *, dry_run: bool) -> None:
        for task in pipeline.all_steps():
            if task.risk == RiskLevel.DESTRUCTIVE and not self.config.allow_destructive:
                report.add(
                    PolicyDecision(
                        policy_id="destructive-denied",
                        decision=PolicyDecisionType.DENY,
                        subject=task.id,
                        reason="destructive actions are disabled by policy",
                    )
                )
            elif task.risk == RiskLevel.HIGH_RISK and not dry_run:
                report.add(
                    PolicyDecision(
                        policy_id="high-risk-approval",
                        decision=PolicyDecisionType.REQUIRES_APPROVAL,
                        subject=task.id,
                        reason="high-risk action requires human approval before execution",
                    )
                )
            elif (
                pipeline.autonomy_level == AutonomyLevel.POLICY_BOUNDED_AUTONOMOUS
                and RISK_ORDER[task.risk] > RISK_ORDER[self.config.max_autonomous_risk]
            ):
                report.add(
                    PolicyDecision(
                        policy_id="autonomy-risk-threshold",
                        decision=PolicyDecisionType.REQUIRES_APPROVAL,
                        subject=task.id,
                        reason="task risk exceeds autonomous execution threshold",
                    )
                )
        for environment in pipeline.environments:
            if environment.name == "production" and self.config.production_requires_approval:
                report.add(
                    PolicyDecision(
                        policy_id="prod-approval-required",
                        decision=PolicyDecisionType.REQUIRES_APPROVAL,
                        subject=environment.name,
                        reason="production deployment requires approval",
                    )
                )

    def _evaluate_commands(self, report: PolicyReport, pipeline: PipelineIR) -> None:
        for task in pipeline.all_steps():
            if not task.command:
                continue
            assessment = classify_command(task.command)
            if RISK_ORDER[assessment.risk] > RISK_ORDER[task.risk]:
                report.add(
                    PolicyDecision(
                        policy_id="command-risk-mismatch",
                        decision=PolicyDecisionType.WARN,
                        subject=task.id,
                        reason="declared task risk is lower than classified command risk",
                        metadata={"classified": assessment.risk.value, "declared": task.risk.value},
                    )
                )

    def _evaluate_runners_and_images(self, report: PolicyReport, pipeline: PipelineIR) -> None:
        if self.config.allowed_runners:
            for task in pipeline.all_steps():
                if task.runner and task.runner not in self.config.allowed_runners:
                    report.add(
                        PolicyDecision(
                            policy_id="runner-allowlist",
                            decision=PolicyDecisionType.DENY,
                            subject=task.id,
                            reason="task specifies a runner not allowed by policy",
                            metadata={"runner": task.runner},
                        )
                    )
        if self.config.allowed_images:
            for task in pipeline.all_steps():
                if task.image and task.image not in self.config.allowed_images:
                    report.add(
                        PolicyDecision(
                            policy_id="image-allowlist",
                            decision=PolicyDecisionType.DENY,
                            subject=task.id,
                            reason="task image is not in the approved image allowlist",
                            metadata={"image": task.image},
                        )
                    )

    def _evaluate_security_requirements(self, report: PolicyReport, pipeline: PipelineIR) -> None:
        has_deploy = any(task.category == TaskCategory.DEPLOYMENT for task in pipeline.all_steps())
        has_security = any(task.category == TaskCategory.SECURITY for task in pipeline.all_steps())
        if has_deploy and self.config.require_security_scan_for_deploy and not has_security:
            report.add(
                PolicyDecision(
                    policy_id="deploy-requires-security-scan",
                    decision=PolicyDecisionType.DENY,
                    subject=pipeline.metadata.id,
                    reason="deployment pipeline must include a security scan task",
                )
            )

    def _permission_for_task(self, task: TaskSpec, pipeline: PipelineIR) -> Permission | None:
        if task.category in {TaskCategory.BUILD, TaskCategory.TEST, TaskCategory.SECURITY, TaskCategory.SOURCE}:
            return Permission.EXECUTE_CI
        if task.category == TaskCategory.INFRASTRUCTURE:
            return Permission.MODIFY_INFRASTRUCTURE
        if task.category == TaskCategory.DEPLOYMENT:
            environment_names = {environment.name for environment in pipeline.environments}
            if "production" in environment_names:
                return Permission.DEPLOY_PRODUCTION
            if "staging" in environment_names:
                return Permission.DEPLOY_STAGING
            return Permission.DEPLOY_DEVELOPMENT
        if task.type == "rollback":
            return Permission.ROLLBACK
        return None


class OpaPolicyBackend:
    """OPA adapter placeholder that does not pretend OPA is configured.

    Wire this to `opa eval` or an OPA HTTP server in a later phase. Until configured,
    callers receive a structured NOT_IMPLEMENTED decision rather than fake compliance.
    """

    def evaluate(
        self,
        pipeline: PipelineIR,
        principal: Principal,
        context: ContextBundle | None = None,
        *,
        dry_run: bool = False,
    ) -> PolicyReport:
        return PolicyReport(
            decisions=[
                PolicyDecision(
                    policy_id="opa-backend",
                    decision=PolicyDecisionType.WARN,
                    subject=pipeline.metadata.id,
                    reason="NOT_IMPLEMENTED: OPA backend interface exists but no OPA runtime is configured",
                    metadata={"principal": principal.id, "dry_run": dry_run},
                )
            ]
        )
