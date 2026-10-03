"""Kubernetes and Helm CLI runner adapters."""

from __future__ import annotations

from agentic_cicd.core.enums import RiskLevel, RunnerKind
from agentic_cicd.runners.base import RunnerCapabilities
from agentic_cicd.runners.cli import SubprocessCliRunner


class KubernetesRunner(SubprocessCliRunner):
    def __init__(self, runner_id: str = "kubectl-cli", *, max_command_risk: RiskLevel = RiskLevel.SAFE) -> None:
        super().__init__(
            runner_id=runner_id,
            kind=RunnerKind.KUBERNETES,
            executable="kubectl",
            allowed_binaries={"kubectl"},
            max_command_risk=max_command_risk,
            capabilities=RunnerCapabilities(
                tools={"kubectl"},
                network_access=True,
                kubernetes=True,
                memory_mb=512,
                cpu=1.0,
                timeout_limit_seconds=3600,
                security_level="cluster-readonly" if max_command_risk == RiskLevel.SAFE else "cluster-mutation",
            ),
        )


class HelmRunner(SubprocessCliRunner):
    def __init__(self, runner_id: str = "helm-cli", *, max_command_risk: RiskLevel = RiskLevel.SAFE) -> None:
        super().__init__(
            runner_id=runner_id,
            kind=RunnerKind.HELM,
            executable="helm",
            allowed_binaries={"helm"},
            max_command_risk=max_command_risk,
            capabilities=RunnerCapabilities(
                tools={"helm"},
                network_access=True,
                kubernetes=True,
                memory_mb=512,
                cpu=1.0,
                timeout_limit_seconds=3600,
                security_level="helm-readonly" if max_command_risk == RiskLevel.SAFE else "helm-mutation",
            ),
        )
