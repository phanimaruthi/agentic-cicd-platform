"""Local shell runner executing argv commands without invoking a shell."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from agentic_cicd.core.audit import mask_secret_value
from agentic_cicd.core.enums import ExecutionStatus, FailureCategory, RiskLevel, RunnerKind
from agentic_cicd.core.errors import PipelineValidationError, ToolExecutionError
from agentic_cicd.core.execution import TaskExecutionResult
from agentic_cicd.core.task import TaskSpec
from agentic_cicd.runners.base import Runner, RunnerCapabilities, RunnerExecutionContext, RunnerHealth, result_for_dry_run
from agentic_cicd.security.command import assert_command_allowed, classify_command


class LocalShellRunner(Runner):
    def __init__(self, runner_id: str = "local-shell", *, max_command_risk: RiskLevel = RiskLevel.LOW_RISK) -> None:
        self.id = runner_id
        self.kind = RunnerKind.LOCAL_SHELL
        self.capabilities = RunnerCapabilities(
            tools={"git", "python", "pytest", "agentic-cicd-internal"},
            network_access=False,
            max_command_risk=max_command_risk,
            timeout_limit_seconds=3600,
        )

    def validate(self, task: TaskSpec) -> None:
        if not self.capabilities.satisfies(task.required_capabilities):
            raise PipelineValidationError(
                f"runner {self.id!r} does not satisfy task capability requirements",
                metadata={"task_id": task.id, "runner_id": self.id},
            )
        if task.command:
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
            result.outputs["risk"] = assessment.risk.value
            result.outputs["risk_reasons"] = assessment.reasons
            return result

        self.validate(task)
        cwd = context.cwd
        if not cwd.exists():
            raise ToolExecutionError(
                "working directory does not exist",
                category=FailureCategory.CONFIGURATION,
                metadata={"cwd": str(cwd)},
            )
        env = os.environ.copy()
        control_plane_root = str(Path(__file__).resolve().parents[2])
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{control_plane_root}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else control_plane_root
        )
        env.update(context.environment)
        env.update({key: value for key, value in task.environment.items() if not value.startswith("secret://")})
        try:
            command = list(task.command)
            if command and command[0] in {"python", "python3"}:
                command[0] = sys.executable
            completed = subprocess.run(  # noqa: S603 - shell=False argv execution by design
                command,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                shell=False,
                timeout=task.timeout_seconds,
                check=False,
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
        except subprocess.TimeoutExpired as exc:
            return TaskExecutionResult(
                task_id=task.id,
                runner_id=self.id,
                status=ExecutionStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(UTC),
                duration_ms=int((time.monotonic() - start) * 1000),
                exit_code=None,
                stdout=str(mask_secret_value(exc.stdout or "")),
                stderr=str(mask_secret_value(exc.stderr or "timeout")),
                failure_category=FailureCategory.TIMEOUT,
            )
        except FileNotFoundError as exc:
            return TaskExecutionResult(
                task_id=task.id,
                runner_id=self.id,
                status=ExecutionStatus.FAILED,
                started_at=started,
                finished_at=datetime.now(UTC),
                duration_ms=int((time.monotonic() - start) * 1000),
                exit_code=127,
                stderr=str(exc),
                failure_category=FailureCategory.CONFIGURATION,
            )

    def health_check(self) -> RunnerHealth:
        return RunnerHealth(
            runner_id=self.id,
            healthy=Path(".").resolve().exists(),
            details={"kind": self.kind.value, "max_command_risk": self.capabilities.max_command_risk.value},
        )
