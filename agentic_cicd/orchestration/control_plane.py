"""Event-driven CI/CD control plane orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.context import ContextBundle
from agentic_cicd.core.execution import ExecutionRecord, ExecutionRequest
from agentic_cicd.core.identity import Principal
from agentic_cicd.core.pipeline import PipelineIR
from agentic_cicd.discovery.repository import RepositoryIntelligenceAgent
from agentic_cicd.events.models import PullRequestEvent
from agentic_cicd.orchestration.execution_engine import ExecutionEngine
from agentic_cicd.orchestration.pr_pipeline import PRPipelineExplanation, PRPipelineFactory
from agentic_cicd.orchestration.scheduler import DagSchedule, DagScheduler
from agentic_cicd.policies.engine import DefaultPolicyEngine, PolicyReport
from agentic_cicd.ui.report import write_pipeline_report


class PipelineRunBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    event: PullRequestEvent
    context: ContextBundle
    pipeline: PipelineIR
    explanation: PRPipelineExplanation
    schedule: DagSchedule
    policy_report: PolicyReport
    execution: ExecutionRecord
    report_path: str | None = None
    notes: list[str] = Field(default_factory=list)


class PullRequestControlPlane:
    """Full local PR/MR event flow: trigger -> context -> plan -> policy -> execute -> report."""

    def __init__(
        self,
        *,
        discovery: RepositoryIntelligenceAgent | None = None,
        pipeline_factory: PRPipelineFactory | None = None,
        policy_engine: DefaultPolicyEngine | None = None,
        execution_engine: ExecutionEngine | None = None,
        scheduler: DagScheduler | None = None,
    ) -> None:
        self.discovery = discovery or RepositoryIntelligenceAgent()
        self.pipeline_factory = pipeline_factory or PRPipelineFactory()
        self.policy_engine = policy_engine or DefaultPolicyEngine(
            authz=__import__("agentic_cicd.core.identity", fromlist=["AuthorizationService"]).AuthorizationService()
        )
        self.execution_engine = execution_engine or ExecutionEngine(policy_engine=self.policy_engine)
        self.scheduler = scheduler or DagScheduler()

    def handle_pull_request(
        self,
        event: PullRequestEvent,
        principal: Principal,
        *,
        dry_run: bool = True,
        approved: bool = False,
        report_path: str | Path | None = None,
    ) -> PipelineRunBundle:
        context = self.discovery.context_bundle(event.id, event.repo_path)
        if context.repository and event.changed_files:
            context.repository.changed_files = event.changed_files
        if context.repository is None:
            raise RuntimeError("repository discovery did not produce repository context")
        pipeline, explanation = self.pipeline_factory.build(event, context.repository, actor=principal.id)
        schedule = self.scheduler.plan_waves(pipeline)
        policy_report = self.policy_engine.evaluate(pipeline, principal, context, dry_run=dry_run)
        execution = self.execution_engine.execute(
            ExecutionRequest(pipeline=pipeline, repo_path=event.repo_path, dry_run=dry_run, approved=approved),
            principal,
            context,
        )
        final_report_path = None
        if report_path:
            final_report_path = str(
                write_pipeline_report(
                    report_path,
                    event=event,
                    pipeline=pipeline,
                    explanation=explanation,
                    schedule=schedule,
                    policy_report=policy_report,
                    execution=execution,
                )
            )
        notes: list[str] = []
        if event.provider.value in {"github", "gitlab", "bitbucket"}:
            notes.append(
                "This run used normalized event data. Real hosted webhook/API integration requires configuring an HTTP receiver and provider credentials."
            )
        return PipelineRunBundle(
            event=event,
            context=context,
            pipeline=pipeline,
            explanation=explanation,
            schedule=schedule,
            policy_report=policy_report,
            execution=execution,
            report_path=final_report_path,
            notes=notes,
        )

    def bundle_summary(self, bundle: PipelineRunBundle) -> dict[str, Any]:
        return {
            "event": bundle.event.model_dump(mode="json"),
            "pipeline_id": bundle.pipeline.metadata.id,
            "pipeline_name": bundle.pipeline.metadata.name,
            "execution_id": bundle.execution.id,
            "status": bundle.execution.status.value,
            "stages": [stage.name for stage in bundle.pipeline.stages],
            "waves": [wave.model_dump(mode="json") for wave in bundle.schedule.waves],
            "policy_decisions": bundle.policy_report.as_dicts(),
            "results": [result.model_dump(mode="json") for result in bundle.execution.results],
            "report_path": bundle.report_path,
            "notes": bundle.notes,
        }
