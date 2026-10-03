"""Docker CLI runner adapter."""

from __future__ import annotations

from agentic_cicd.core.enums import RiskLevel, RunnerKind
from agentic_cicd.runners.base import RunnerCapabilities
from agentic_cicd.runners.cli import SubprocessCliRunner


class DockerRunner(SubprocessCliRunner):
    def __init__(self, runner_id: str = "docker-cli", *, max_command_risk: RiskLevel = RiskLevel.MEDIUM_RISK) -> None:
        super().__init__(
            runner_id=runner_id,
            kind=RunnerKind.DOCKER,
            executable="docker",
            allowed_binaries={"docker"},
            max_command_risk=max_command_risk,
            capabilities=RunnerCapabilities(
                tools={"docker"},
                network_access=True,
                docker=True,
                memory_mb=2048,
                cpu=2.0,
                timeout_limit_seconds=7200,
                security_level="host-cli",
            ),
        )
