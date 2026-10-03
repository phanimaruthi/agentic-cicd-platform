"""Policy-bounded execution engine."""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_cicd.core.audit import AuditEvent, AuditSink, InMemoryAuditSink, hash_inputs
from agentic_cicd.core.context import ContextBundle
from agentic_cicd.core.enums import ExecutionStatus, PolicyDecisionType
from agentic_cicd.core.errors import PlatformError
from agentic_cicd.core.execution import ExecutionRecord, ExecutionRequest, TaskExecutionResult
from agentic_cicd.core.identity import Principal
from agentic_cicd.policies.engine import DefaultPolicyEngine, PolicyEngine
from agentic_cicd.runners.base import RunnerExecutionContext
from agentic_cicd.runners.registry import RunnerRegistry, default_runner_registry
from agentic_cicd.orchestration.failure import FailureAnalyzer, RemediationPlanner
from agentic_cicd.orchestration.store import ExecutionStore


class ExecutionEngine:
    def __init__(
        self,
        *,
        runners: RunnerRegistry | None = None,
        policy_engine: PolicyEngine | None = None,
        audit_sink: AuditSink | None = None,
        store: ExecutionStore | None = None,
    ) -> None:
        self.runners = runners or default_runner_registry()
        self.policy_engine = policy_engine or DefaultPolicyEngine(authz=__import__("agentic_cicd.core.identity", fromlist=["AuthorizationService"]).AuthorizationService())
        self.audit_sink = audit_sink or InMemoryAuditSink()
        self.store = store
        self.failure_analyzer = FailureAnalyzer()
        self.remediation_planner = RemediationPlanner()

    def execute(
        self,
        request: ExecutionRequest,
        principal: Principal,
        context: ContextBundle | None = None,
    ) -> ExecutionRecord:
        record = ExecutionRecord(request_id=request.id, pipeline_id=request.pipeline.metadata.id)
        start_event = AuditEvent(
            actor=principal.id,
            actor_type="human+agent",
            action="execution.requested",
            resource=request.pipeline.metadata.id,
            environment=",".join(env.name for env in request.pipeline.environments) or None,
            authorization="pending",
            inputs_hash=hash_inputs(request.pipeline.model_dump(mode="json")),
            related_execution=record.id,
        )
        record.audit_event_ids.append(self.audit_sink.emit(start_event))

        try:
            request.pipeline.validate_integrity()
            if len(request.pipeline.all_steps()) > request.pipeline.execution_strategy.max_tool_calls:
                raise PlatformError(
                    "pipeline exceeds max tool/task call budget",
                    metadata={
                        "steps": len(request.pipeline.all_steps()),
                        "max_tool_calls": request.pipeline.execution_strategy.max_tool_calls,
                    },
                )
            policy_report = self.policy_engine.evaluate(
                request.pipeline, principal, context, dry_run=request.dry_run
            )
            record.policy_decisions = policy_report.as_dicts()
            if policy_report.denied:
                record.mark_finished(ExecutionStatus.DENIED)
                self._audit_completion(record, principal, "execution.denied")
                self._save(record)
                return record
            if policy_report.approval_required and not (request.approved or request.dry_run):
                record.status = ExecutionStatus.APPROVAL_REQUIRED
                record.finished_at = datetime.now(UTC)
                record.approvals = [
                    decision.model_dump(mode="json")
                    for decision in policy_report.decisions
                    if decision.decision == PolicyDecisionType.REQUIRES_APPROVAL
                ]
                self._audit_completion(record, principal, "execution.approval_required")
                self._save(record)
                return record

            record.status = ExecutionStatus.RUNNING
            completed: set[str] = set()
            failed: set[str] = set()
            skipped: set[str] = set()
            steps_by_id = request.pipeline.step_by_id()
            dependency_map: dict[str, set[str]] = {step_id: set() for step_id in steps_by_id}
            for dependency, step_id in request.pipeline.dependency_edges():
                dependency_map[step_id].add(dependency)
            for task in request.pipeline.topological_steps():
                if any(dependency in failed or dependency in skipped for dependency in dependency_map[task.id]):
                    result = TaskExecutionResult(
                        task_id=task.id,
                        runner_id="none",
                        status=ExecutionStatus.SKIPPED,
                        finished_at=datetime.now(UTC),
                        stderr="Skipped because dependency failed or was skipped",
                    )
                    record.results.append(result)
                    skipped.add(task.id)
                    continue
                runner = self.runners.select(task)
                runner.validate(task)
                event_id = self.audit_sink.emit(
                    AuditEvent(
                        actor=principal.id,
                        actor_type="human+agent",
                        action="task.started",
                        resource=task.id,
                        environment=",".join(env.name for env in request.pipeline.environments) or None,
                        authorization="authorized",
                        policy_decision="ALLOW_OR_DRY_RUN",
                        inputs_hash=hash_inputs(task.model_dump(mode="json")),
                        runner=runner.id,
                        related_execution=record.id,
                    )
                )
                record.audit_event_ids.append(event_id)
                result = runner.execute(
                    task,
                    RunnerExecutionContext(
                        execution_id=record.id,
                        workdir=request.repo_path,
                        dry_run=request.dry_run,
                        approved=request.approved,
                    ),
                )
                record.results.append(result)
                self.audit_sink.emit(
                    AuditEvent(
                        actor=principal.id,
                        actor_type="runner",
                        action="task.finished",
                        resource=task.id,
                        environment=",".join(env.name for env in request.pipeline.environments) or None,
                        result=result.status.value,
                        runner=runner.id,
                        related_execution=record.id,
                        context={"exit_code": result.exit_code},
                    )
                )
                if result.status == ExecutionStatus.SUCCEEDED:
                    completed.add(task.id)
                else:
                    failed.add(task.id)
                    diagnosis = self.failure_analyzer.analyze(steps_by_id[task.id], result)
                    remediation = self.remediation_planner.plan(steps_by_id[task.id], diagnosis)
                    record.diagnosis.append(diagnosis.model_dump(mode="json"))
                    record.remediation.append(remediation.model_dump(mode="json"))
                    if task.failure_strategy == "fail_fast":
                        break
            final_status = ExecutionStatus.FAILED if failed else ExecutionStatus.SUCCEEDED
            record.mark_finished(final_status)
            self._audit_completion(record, principal, "execution.finished")
            self._save(record)
            return record
        except PlatformError as exc:
            record.results.append(
                TaskExecutionResult(
                    task_id="control-plane",
                    runner_id="control-plane",
                    status=ExecutionStatus.FAILED,
                    finished_at=datetime.now(UTC),
                    stderr=exc.envelope.message,
                    error=exc.envelope,
                    failure_category=exc.envelope.category,
                )
            )
            record.mark_finished(ExecutionStatus.FAILED)
            self._audit_completion(record, principal, "execution.failed", error=exc.to_dict())
            self._save(record)
            return record

    def _save(self, record: ExecutionRecord) -> None:
        if self.store is not None:
            self.store.save(record)

    def _audit_completion(
        self,
        record: ExecutionRecord,
        principal: Principal,
        action: str,
        error: dict[str, object] | None = None,
    ) -> None:
        self.audit_sink.emit(
            AuditEvent(
                actor=principal.id,
                actor_type="human+agent",
                action=action,
                resource=record.pipeline_id,
                result=record.status.value,
                related_execution=record.id,
                context={"error": error} if error else {},
            )
        )
