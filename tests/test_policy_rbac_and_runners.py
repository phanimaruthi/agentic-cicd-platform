from __future__ import annotations

import pytest

from agentic_cicd.core.enums import ExecutionStatus, Permission, RiskLevel, Role, TaskCategory
from agentic_cicd.core.execution import ExecutionRequest
from agentic_cicd.core.identity import AgentIdentity, AuthorizationService, Principal
from agentic_cicd.core.intent import IntentParser
from agentic_cicd.core.pipeline import PipelineIR, PipelineMetadata, PipelineStage
from agentic_cicd.core.task import TaskSpec
from agentic_cicd.discovery.repository import RepositoryIntelligenceAgent
from agentic_cicd.orchestration.execution_engine import ExecutionEngine
from agentic_cicd.orchestration.planner import PipelinePlanner
from agentic_cicd.policies.engine import DefaultPolicyEngine
from agentic_cicd.runners.local import LocalShellRunner
from agentic_cicd.security.command import classify_command


def test_agent_cannot_exceed_initiating_principal_permissions() -> None:
    authz = AuthorizationService(
        AgentIdentity(permissions={Permission.EXECUTE_CI, Permission.DEPLOY_PRODUCTION})
    )
    developer = Principal(id="dev", roles={Role.DEVELOPER})
    assert Permission.EXECUTE_CI in authz.effective_permissions(developer)
    assert Permission.DEPLOY_PRODUCTION not in authz.effective_permissions(developer)


def test_unauthorized_production_deploy_is_denied() -> None:
    intent = IntentParser.parse("Deploy to production")
    bundle = RepositoryIntelligenceAgent().context_bundle(intent.id, "samples/python_app")
    principal = Principal(id="dev", roles={Role.DEVELOPER})
    planned = PipelinePlanner().plan(intent, bundle, principal)
    engine = ExecutionEngine(policy_engine=DefaultPolicyEngine(AuthorizationService()))
    record = engine.execute(
        ExecutionRequest(pipeline=planned.pipeline, repo_path="samples/python_app", dry_run=False),
        principal,
        bundle,
    )
    assert record.status == ExecutionStatus.DENIED
    assert any(decision["decision"] == "DENY" for decision in record.policy_decisions)


def test_production_deploy_for_release_engineer_requires_approval() -> None:
    intent = IntentParser.parse("Deploy to production")
    bundle = RepositoryIntelligenceAgent().context_bundle(intent.id, "samples/python_app")
    principal = Principal(id="release", roles={Role.RELEASE_ENGINEER})
    planned = PipelinePlanner().plan(intent, bundle, principal)
    record = ExecutionEngine(policy_engine=DefaultPolicyEngine(AuthorizationService())).execute(
        ExecutionRequest(pipeline=planned.pipeline, repo_path="samples/python_app", dry_run=False),
        principal,
        bundle,
    )
    assert record.status == ExecutionStatus.APPROVAL_REQUIRED


def test_command_safety_classifies_destructive_commands() -> None:
    assessment = classify_command(["terraform", "destroy", "-auto-approve"])
    assert assessment.risk == RiskLevel.DESTRUCTIVE


def test_local_runner_denies_destructive_command() -> None:
    runner = LocalShellRunner()
    dangerous = TaskSpec(
        id="destroy",
        type="terraform_destroy",
        name="Destroy",
        category=TaskCategory.INFRASTRUCTURE,
        command=["terraform", "destroy", "-auto-approve"],
        risk=RiskLevel.DESTRUCTIVE,
        side_effects=["destroy infrastructure"],
    )
    with pytest.raises(Exception):
        runner.validate(dangerous)
