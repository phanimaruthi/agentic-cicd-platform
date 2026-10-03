from __future__ import annotations

from agentic_cicd.core.enums import ExecutionStatus, Role, TaskCategory
from agentic_cicd.core.execution import ExecutionRequest
from agentic_cicd.core.identity import Principal
from agentic_cicd.core.pipeline import PipelineIR, PipelineMetadata, PipelineStage
from agentic_cicd.core.task import TaskSpec
from agentic_cicd.orchestration.execution_engine import ExecutionEngine
from agentic_cicd.remediation.agent import RemediationAgent, RemediationRequest
from agentic_cicd.runners.mock import MockRunner
from agentic_cicd.runners.registry import RunnerRegistry


def make_pipeline() -> PipelineIR:
    return PipelineIR(
        metadata=PipelineMetadata(name="remediation-demo", service="sample"),
        stages=[
            PipelineStage(
                id="test",
                name="Test",
                type="test",
                steps=[
                    TaskSpec(
                        id="unit_tests",
                        type="unit_test",
                        name="Unit tests",
                        category=TaskCategory.TEST,
                        runner="mock-runner",
                        command=["pytest"],
                    )
                ],
            )
        ],
    )


def test_remediation_agent_retries_transient_failure_once_and_succeeds() -> None:
    registry = RunnerRegistry()
    registry.register(MockRunner(fail_times={"unit_tests": 1}, fail_with="simulated transient network failure"))
    pipeline = make_pipeline()
    principal = Principal(id="dev", roles={Role.DEVELOPER})
    record = ExecutionEngine(runners=registry).execute(
        ExecutionRequest(pipeline=pipeline, repo_path=".", dry_run=False), principal, None
    )
    assert record.status == ExecutionStatus.FAILED

    outcome = RemediationAgent(runners=registry).remediate(
        RemediationRequest(pipeline=pipeline, execution_record=record, repo_path=".", dry_run=False),
        principal,
        None,
    )
    assert outcome.attempted is True
    assert outcome.final_status == ExecutionStatus.SUCCEEDED
    assert outcome.attempts[0].result is not None
    assert outcome.attempts[0].result.status == ExecutionStatus.SUCCEEDED


def test_remediation_agent_does_not_auto_fix_deterministic_unknown_failure() -> None:
    registry = RunnerRegistry()
    registry.register(MockRunner(fail_tasks={"unit_tests"}, fail_with="syntax error"))
    pipeline = make_pipeline()
    principal = Principal(id="dev", roles={Role.DEVELOPER})
    record = ExecutionEngine(runners=registry).execute(
        ExecutionRequest(pipeline=pipeline, repo_path=".", dry_run=False), principal, None
    )
    outcome = RemediationAgent(runners=registry).remediate(
        RemediationRequest(pipeline=pipeline, execution_record=record, repo_path=".", dry_run=False),
        principal,
        None,
    )
    assert outcome.attempted is False
    assert outcome.final_status == ExecutionStatus.FAILED
    assert outcome.attempts[0].attempted is False
