from __future__ import annotations

import pytest

from agentic_cicd.core.enums import Permission, RiskLevel, Role, TaskCategory
from agentic_cicd.core.identity import AgentIdentity, AuthorizationService, Principal
from agentic_cicd.core.task import RunnerCapabilityRequest, TaskSpec
from agentic_cicd.runners.docker import DockerRunner
from agentic_cicd.runners.kubernetes import KubernetesRunner
from agentic_cicd.runners.registry import default_runner_registry
from agentic_cicd.runners.terraform import TerraformRunner
from agentic_cicd.security.command import classify_command
from agentic_cicd.tools.registry import ToolRegistry, default_tool_registry
from agentic_cicd.tools.local_tools import SecretScanTool


def test_default_registry_does_not_include_mock_runner_by_default() -> None:
    runner_ids = {runner.id for runner in default_runner_registry(discover_external=False).list()}
    assert "mock-runner" not in runner_ids
    assert "local-shell" in runner_ids


def test_terraform_runner_denies_apply_by_default() -> None:
    runner = TerraformRunner()
    task = TaskSpec(
        id="tf_apply",
        type="terraform_apply",
        name="Terraform apply",
        category=TaskCategory.INFRASTRUCTURE,
        command=["terraform", "apply", "-auto-approve"],
        risk=RiskLevel.HIGH_RISK,
        side_effects=["mutate infrastructure"],
        required_capabilities=RunnerCapabilityRequest(tools={"terraform"}, cloud_access=True),
    )
    with pytest.raises(Exception):
        runner.validate(task)


def test_kubernetes_runner_allows_readonly_status_but_not_apply() -> None:
    runner = KubernetesRunner()
    readonly = TaskSpec(
        id="pods",
        type="kubectl_get",
        name="Get pods",
        category=TaskCategory.KUBERNETES,
        command=["kubectl", "get", "pods"],
        required_capabilities=RunnerCapabilityRequest(tools={"kubectl"}, kubernetes=True),
    )
    runner.validate(readonly)
    mutating = TaskSpec(
        id="apply",
        type="kubectl_apply",
        name="Apply manifests",
        category=TaskCategory.KUBERNETES,
        command=["kubectl", "apply", "-f", "deployment.yaml"],
        risk=RiskLevel.HIGH_RISK,
        side_effects=["mutate cluster"],
        required_capabilities=RunnerCapabilityRequest(tools={"kubectl"}, kubernetes=True),
    )
    with pytest.raises(Exception):
        runner.validate(mutating)


def test_docker_build_is_medium_risk() -> None:
    assert classify_command(["docker", "build", "-t", "app", "."]).risk == RiskLevel.MEDIUM_RISK
    runner = DockerRunner()
    task = TaskSpec(
        id="docker_build",
        type="build_container",
        name="Docker build",
        category=TaskCategory.BUILD,
        command=["docker", "build", "-t", "app", "."],
        risk=RiskLevel.MEDIUM_RISK,
        required_capabilities=RunnerCapabilityRequest(tools={"docker"}, docker=True),
    )
    runner.validate(task)


def test_tool_registry_exposes_contracts_and_enforces_permissions() -> None:
    authz = AuthorizationService(AgentIdentity(permissions={Permission.EXECUTE_CI}))
    registry = ToolRegistry(authz=authz)
    registry.register(SecretScanTool())
    viewer = Principal(id="viewer", roles={Role.VIEWER})
    with pytest.raises(Exception):
        registry.invoke("secret_scan", {"path": "samples/python_app"}, viewer)
    developer = Principal(id="developer", roles={Role.DEVELOPER})
    result = registry.invoke("secret_scan", {"path": "samples/python_app"}, developer)
    assert result.success is True
    assert result.outputs["findings"] == []


def test_default_tool_registry_contains_core_tools() -> None:
    names = {definition.name for definition in default_tool_registry().definitions()}
    assert {"secret_scan", "generate_sbom", "git_diff"}.issubset(names)
