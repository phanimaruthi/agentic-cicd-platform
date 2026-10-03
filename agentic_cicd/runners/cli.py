"""Generic subprocess-backed CLI runner adapters.

These adapters are intentionally conservative. They execute argv commands with
`shell=False`, enforce binary allowlists and command risk limits, and report
RUNNER_UNAVAILABLE when the underlying executable is missing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from agentic_cicd.core.audit import mask_secret_value
from agentic_cicd.core.enums import ExecutionStatus, FailureCategory, RiskLevel, RunnerKind
from agentic_cicd.core.errors import PipelineValidationError, RunnerUnavailableError
from agentic_cicd.core.execution import TaskExecutionResult
from agentic_cicd.core.task import TaskSpec
from agentic_cicd.runners.base import Runner, RunnerCapabilities, RunnerExecutionContext, RunnerHealth, result_for_dry_run
from agentic_cicd.security.command import assert_command_allowed, classify_command


class SubprocessCliRunner(Runner):
    """Base class for concrete CLI runners such as Docker/Terraform/kubectl."""

    def __init__(
        self,
        *,
        runner_id: str,
        kind: RunnerKind,
        executable: str,
        capabilities: RunnerCapabilities,
        allowed_binaries: set[str],
        max_command_risk: RiskLevel,
    ) -> None:
        self.id = runner_id
        self.kind = kind
        self.executable = executable
        self.allowed_binaries = allowed_binaries
        self.capabilities = capabilities.model_copy(update={"max_command_risk": max_command_risk})

    @property
    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    def validate(self, task: TaskSpec) -> None:
        if not self.capabilities.satisfies(task.required_capabilities):
            raise PipelineValidationError(
                f"runner {self.id!r} does not satisfy task capability requirements",
                metadata={"task_id": task.id, "runner_id": self.id},
            )
        if not task.command:
            return
        binary = Path(task.command[0]).name
        if binary not in self.allowed_binaries:
            raise PipelineValidationError(
                "task command binary is not allowed for this runner",
                metadata={
                    "task_id": task.id,
                    "runner_id": self.id,
                    "binary": binary,
                    "allowed": sorted(self.allowed_binaries),
                },
            )
        assert_command_allowed(task.command, self.capabilities.max_command_risk)
        if task.timeout_seconds > self.capabilities.timeout_limit_seconds:
            raise PipelineValidationError(
                "task timeout exceeds runner timeout limit",
                metadata={"task_id": task.id, "timeout": task.timeout_seconds},
            )

    def execute(self, task: TaskSpec, context: RunnerExecutionContext) -> TaskExecutionResult:
        started = datetime.now(UTC)
        start = time.monotonic()
        assessment = classify_command(task.command)
        if context.dry_run or not task.command:
            result = result_for_dry_run(task, self.id)
            result.outputs.update(
                {
                    "runner_available": self.available,
                    "executable": self.executable,
                    "risk": assessment.risk.value,
                    "risk_reasons": assessment.reasons,
                }
            )
            return result
        self.validate(task)
        if not self.available:
            raise RunnerUnavailableError(
                "RUNNER_UNAVAILABLE",
                metadata={"runner_id": self.id, "executable": self.executable, "task_id": task.id},
            )
        cwd = context.cwd
        if not cwd.exists():
            return TaskExecutionResult(
                task_id=task.id,
                runner_id=self.id,
                status=ExecutionStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(UTC),
                duration_ms=int((time.monotonic() - start) * 1000),
                exit_code=None,
                stderr=f"working directory does not exist: {cwd}",
                failure_category=FailureCategory.CONFIGURATION,
            )
        env = os.environ.copy()
        env.update(context.environment)
        env.update({key: value for key, value in task.environment.items() if not value.startswith("secret://")})
        try:
            completed = subprocess.run(  # noqa: S603 - shell=False argv execution by design
                task.command,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                shell=False,
                timeout=task.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return TaskExecutionResult(
                task_id=task.id,
                runner_id=self.id,
                status=ExecutionStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(UTC),
                duration_ms=int((time.monotonic() - start) * 1000),
                stdout=str(mask_secret_value(exc.stdout or "")),
                stderr=str(mask_secret_value(exc.stderr or "timeout")),
                failure_category=FailureCategory.TIMEOUT,
            )
        status = ExecutionStatus.SUCCEEDED if completed.returncode == 0 else ExecutionStatus.FAILED
        return TaskExecutionResult(
            task_id=task.id,
            runner_id=self.id,
            status=status,
            started_at=started,
            finished_at=datetime.now(UTC),
            duration_ms=int((time.monotonic() - start) * 1000),
            exit_code=completed.returncode,
            stdout=str(mask_secret_value(completed.stdout)),
            stderr=str(mask_secret_value(completed.stderr)),
            outputs={"risk": assessment.risk.value, "risk_reasons": assessment.reasons},
        )

    def health_check(self) -> RunnerHealth:
        return RunnerHealth(
            runner_id=self.id,
            healthy=self.available,
            details={
                "kind": self.kind.value,
                "executable": self.executable,
                "available": self.available,
                "max_command_risk": self.capabilities.max_command_risk.value,
            },
        )
