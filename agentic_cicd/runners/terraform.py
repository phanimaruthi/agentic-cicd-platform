"""Terraform/OpenTofu CLI runner adapter.

The default risk threshold allows validate/fmt/plan but denies apply/destroy unless an
operator explicitly constructs a higher-risk runner and policies approve it.
"""

from __future__ import annotations

from agentic_cicd.core.enums import RiskLevel, RunnerKind
from agentic_cicd.runners.base import RunnerCapabilities
from agentic_cicd.runners.cli import SubprocessCliRunner


class TerraformRunner(SubprocessCliRunner):
    def __init__(
        self,
        runner_id: str = "terraform-cli",
        *,
        executable: str = "terraform",
        max_command_risk: RiskLevel = RiskLevel.MEDIUM_RISK,
    ) -> None:
        super().__init__(
            runner_id=runner_id,
            kind=RunnerKind.TERRAFORM,
            executable=executable,
            allowed_binaries={"terraform", "tofu", "opentofu"},
            max_command_risk=max_command_risk,
            capabilities=RunnerCapabilities(
                tools={executable, "terraform" if executable != "terraform" else executable},
                network_access=True,
                cloud_access=True,
                memory_mb=1024,
                cpu=1.0,
                timeout_limit_seconds=7200,
                security_level="iac-cli",
            ),
        )
