from __future__ import annotations

import yaml

from agentic_cicd.compilers.github_actions import GitHubActionsCompiler
from agentic_cicd.core.enums import ExecutionStatus, IntentAction, Role
from agentic_cicd.core.execution import ExecutionRequest
from agentic_cicd.core.identity import Principal
from agentic_cicd.core.intent import IntentParser
from agentic_cicd.discovery.repository import RepositoryIntelligenceAgent
from agentic_cicd.orchestration.execution_engine import ExecutionEngine
from agentic_cicd.orchestration.planner import PipelinePlanner


def plan_for(text: str):
    intent = IntentParser.parse(text)
    bundle = RepositoryIntelligenceAgent().context_bundle(intent.id, "samples/python_app")
    principal = Principal(id="dev", roles={Role.DEVELOPER})
    return PipelinePlanner().plan(intent, bundle, principal), bundle, principal


def test_intent_parser_detects_pipeline_generation() -> None:
    intent = IntentParser.parse("Generate a CI pipeline with GitHub Actions")
    assert intent.action == IntentAction.GENERATE_PIPELINE


def test_ci_plan_contains_security_and_tests() -> None:
    planned, _bundle, _principal = plan_for("Generate a CI pipeline")
    task_ids = {task.id for task in planned.pipeline.all_steps()}
    assert "secret_scan" in task_ids
    assert "unit_tests" in task_ids
    planned.pipeline.validate_integrity()


def test_github_actions_compiler_renders_valid_yaml() -> None:
    planned, _bundle, _principal = plan_for("Generate a CI pipeline")
    rendered = GitHubActionsCompiler().render(planned.pipeline)
    parsed = yaml.safe_load(rendered)
    assert parsed["jobs"]
    assert "security" in parsed["jobs"]


def test_execution_engine_dry_run_executes_mock_pipeline() -> None:
    planned, bundle, principal = plan_for("Generate a CI pipeline")
    record = ExecutionEngine().execute(
        ExecutionRequest(pipeline=planned.pipeline, repo_path="samples/python_app", dry_run=True),
        principal,
        bundle,
    )
    assert record.status == ExecutionStatus.SUCCEEDED
    assert record.audit_event_ids
    assert all(result.status == ExecutionStatus.SUCCEEDED for result in record.results)
