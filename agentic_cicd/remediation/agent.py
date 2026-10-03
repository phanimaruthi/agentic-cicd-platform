"""Policy-bounded remediation agent.

This agent does not invent fixes. It consumes structured execution results,
classifies failures, creates bounded remediation plans, evaluates policy, and can
retry only safe/automatic remediation actions through typed runners.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.audit import AuditEvent, AuditSink, InMemoryAuditSink, hash_inputs
from agentic_cicd.core.context import ContextBundle
from agentic_cicd.core.enums import ExecutionStatus, PolicyDecisionType, RiskLevel
from agentic_cicd.core.execution import ExecutionRecord, TaskExecutionResult
from agentic_cicd.core.identity import Principal
from agentic_cicd.core.pipeline import ExecutionStrategy, PipelineIR, PipelineMetadata, PipelineStage
from agentic_cicd.core.task import TaskSpec
from agentic_cicd.knowledge.rag import LocalDocumentIndex
from agentic_cicd.orchestration.failure import FailureAnalyzer, RemediationPlan, RemediationPlanner
from agentic_cicd.policies.engine import DefaultPolicyEngine, PolicyEngine
from agentic_cicd.runners.base import RunnerExecutionContext
from agentic_cicd.runners.registry import RunnerRegistry, default_runner_registry


class RemediationAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    action_id: str
    attempted: bool
    permitted: bool
    reason: str
    result: TaskExecutionResult | None = None
    policy_decisions: list[dict[str, Any]] = Field(default_factory=list)


class RemediationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineIR
    execution_record: ExecutionRecord
    repo_path: str = "."
    dry_run: bool = True
    approved: bool = False
    max_actions: int = Field(default=1, ge=1, le=5)


class RemediationOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str
    attempted: bool
    final_status: ExecutionStatus
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    diagnoses: list[dict[str, Any]] = Field(default_factory=list)
    plans: list[dict[str, Any]] = Field(default_factory=list)
    attempts: list[RemediationAttempt] = Field(default_factory=list)
    retrieved_runbooks: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str


class RemediationAgent:
    """Performs controlled remediation for failed execution records."""

    def __init__(
        self,
        *,
        runners: RunnerRegistry | None = None,
        policy_engine: PolicyEngine | None = None,
        audit_sink: AuditSink | None = None,
        document_index: LocalDocumentIndex | None = None,
    ) -> None:
        self.runners = runners or default_runner_registry()
        self.policy_engine = policy_engine or DefaultPolicyEngine(
            authz=__import__("agentic_cicd.core.identity", fromlist=["AuthorizationService"]).AuthorizationService()
        )
        self.audit_sink = audit_sink or InMemoryAuditSink()
        self.document_index = document_index or LocalDocumentIndex()
        self.failure_analyzer = FailureAnalyzer()
        self.remediation_planner = RemediationPlanner()

    def remediate(
        self,
        request: RemediationRequest,
        principal: Principal,
        context: ContextBundle | None = None,
    ) -> RemediationOutcome:
        started = datetime.now(UTC)
        task_by_id = request.pipeline.step_by_id()
        failed_results = [
            result for result in request.execution_record.results if result.status == ExecutionStatus.FAILED and result.task_id in task_by_id
        ]
        retrieved_runbooks = self._retrieve_runbooks(request, failed_results)
        diagnoses: list[dict[str, Any]] = []
        plans: list[dict[str, Any]] = []
        attempts: list[RemediationAttempt] = []
        self.audit_sink.emit(
            AuditEvent(
                actor=principal.id,
                actor_type="human+agent",
                action="remediation.requested",
                resource=request.execution_record.id,
                related_execution=request.execution_record.id,
                inputs_hash=hash_inputs(request.model_dump(mode="json")),
            )
        )

        for failed_result in failed_results[: request.max_actions]:
            task = task_by_id[failed_result.task_id]
            diagnosis = self.failure_analyzer.analyze(task, failed_result)
            plan = self.remediation_planner.plan(task, diagnosis)
            diagnoses.append(diagnosis.model_dump(mode="json"))
            plans.append(plan.model_dump(mode="json"))
            attempt = self._attempt_plan(
                task=task,
                plan=plan,
                request=request,
                principal=principal,
                context=context,
            )
            attempts.append(attempt)

        succeeded = attempts and all(
            attempt.result is not None and attempt.result.status == ExecutionStatus.SUCCEEDED for attempt in attempts if attempt.attempted
        )
        any_attempted = any(attempt.attempted for attempt in attempts)
        final_status = ExecutionStatus.SUCCEEDED if any_attempted and succeeded else ExecutionStatus.FAILED
        explanation = (
            "Automatic bounded remediation succeeded for attempted safe actions."
            if final_status == ExecutionStatus.SUCCEEDED
            else "No safe automatic remediation completed; manual review or approval is required."
        )
        outcome = RemediationOutcome(
            execution_id=request.execution_record.id,
            attempted=any_attempted,
            final_status=final_status,
            started_at=started,
            finished_at=datetime.now(UTC),
            diagnoses=diagnoses,
            plans=plans,
            attempts=attempts,
            retrieved_runbooks=retrieved_runbooks,
            explanation=explanation,
        )
        self.audit_sink.emit(
            AuditEvent(
                actor=principal.id,
                actor_type="human+agent",
                action="remediation.finished",
                resource=request.execution_record.id,
                result=outcome.final_status.value,
                related_execution=request.execution_record.id,
                context={"attempted": outcome.attempted, "attempts": len(outcome.attempts)},
            )
        )
        return outcome

    def _attempt_plan(
        self,
        *,
        task: TaskSpec,
        plan: RemediationPlan,
        request: RemediationRequest,
        principal: Principal,
        context: ContextBundle | None,
    ) -> RemediationAttempt:
        automatic_actions = [action for action in plan.actions if action.automatic]
        if not automatic_actions:
            return RemediationAttempt(
                task_id=task.id,
                action_id=plan.actions[0].id if plan.actions else "none",
                attempted=False,
                permitted=False,
                reason="plan contains no automatic remediation action",
            )
        action = automatic_actions[0]
        if action.id != "bounded_retry":
            return RemediationAttempt(
                task_id=task.id,
                action_id=action.id,
                attempted=False,
                permitted=False,
                reason="only bounded_retry automatic remediation is implemented",
            )
        if task.risk not in {RiskLevel.SAFE, RiskLevel.LOW_RISK, RiskLevel.MEDIUM_RISK}:
            return RemediationAttempt(
                task_id=task.id,
                action_id=action.id,
                attempted=False,
                permitted=False,
                reason="task risk is too high for automatic retry",
            )
        retry_task = task.model_copy(update={"depends_on": []})
        remediation_pipeline = PipelineIR(
            metadata=PipelineMetadata(
                name=f"Remediation retry for {task.id}",
                repository=request.pipeline.metadata.repository,
                service=request.pipeline.metadata.service,
                created_by=principal.id,
            ),
            stages=[PipelineStage(id="remediation", name="Remediation", type="remediation", steps=[retry_task])],
            policies=request.pipeline.policies,
            environments=request.pipeline.environments,
            execution_strategy=ExecutionStrategy(max_parallelism=1, max_tool_calls=1),
            autonomy_level=request.pipeline.autonomy_level,
        )
        policy_report = self.policy_engine.evaluate(
            remediation_pipeline, principal, context, dry_run=request.dry_run
        )
        policy_decisions = policy_report.as_dicts()
        if policy_report.denied:
            return RemediationAttempt(
                task_id=task.id,
                action_id=action.id,
                attempted=False,
                permitted=False,
                reason="policy denied remediation retry",
                policy_decisions=policy_decisions,
            )
        if policy_report.approval_required and not (request.approved or request.dry_run):
            return RemediationAttempt(
                task_id=task.id,
                action_id=action.id,
                attempted=False,
                permitted=False,
                reason="approval required for remediation retry",
                policy_decisions=policy_decisions,
            )
        runner = self.runners.select(retry_task)
        runner.validate(retry_task)
        self.audit_sink.emit(
            AuditEvent(
                actor=principal.id,
                actor_type="human+agent",
                action="remediation.retry_task.started",
                resource=retry_task.id,
                policy_decision="ALLOW_OR_DRY_RUN",
                runner=runner.id,
                related_execution=request.execution_record.id,
            )
        )
        result = runner.execute(
            retry_task,
            RunnerExecutionContext(
                execution_id=request.execution_record.id,
                workdir=request.repo_path,
                dry_run=request.dry_run,
                approved=request.approved,
            ),
        )
        self.audit_sink.emit(
            AuditEvent(
                actor=principal.id,
                actor_type="runner",
                action="remediation.retry_task.finished",
                resource=retry_task.id,
                result=result.status.value,
                runner=runner.id,
                related_execution=request.execution_record.id,
            )
        )
        return RemediationAttempt(
            task_id=task.id,
            action_id=action.id,
            attempted=True,
            permitted=True,
            reason="bounded retry executed through selected runner",
            result=result,
            policy_decisions=policy_decisions,
        )

    def _retrieve_runbooks(
        self, request: RemediationRequest, failed_results: list[TaskExecutionResult]
    ) -> list[dict[str, Any]]:
        service = request.pipeline.metadata.service or request.pipeline.metadata.name
        query = " ".join([service, *[result.task_id for result in failed_results], "failure remediation runbook"])
        return [document.model_dump(mode="json") for document in self.document_index.search(query, limit=3)]
