"""Mock runner for local tests and demos without external credentials."""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_cicd.core.enums import ExecutionStatus, FailureCategory, RiskLevel, RunnerKind
from agentic_cicd.core.execution import TaskExecutionResult
from agentic_cicd.core.task import TaskSpec
from agentic_cicd.runners.base import Runner, RunnerCapabilities, RunnerExecutionContext, RunnerHealth, result_for_dry_run


class MockRunner(Runner):
    def __init__(
        self,
        runner_id: str = "mock-runner",
        *,
        fail_tasks: set[str] | None = None,
        fail_times: dict[str, int] | None = None,
        fail_with: str = "simulated transient network failure",
    ) -> None:
        self.id = runner_id
        self.kind = RunnerKind.MOCK
        self.fail_tasks = fail_tasks or set()
        self.fail_times = dict(fail_times or {})
        self.fail_with = fail_with
        self.capabilities = RunnerCapabilities(
            tools={
                "git",
                "python",
                "pytest",
                "docker",
                "kubectl",
                "helm",
                "terraform",
                "agentic-cicd-internal",
            },
            network_access=True,
            cloud_access=True,
            docker=True,
            kubernetes=True,
            privileged=False,
            memory_mb=4096,
            cpu=2,
            max_command_risk=RiskLevel.HIGH_RISK,
        )

    def validate(self, task: TaskSpec) -> None:
        return None

    def execute(self, task: TaskSpec, context: RunnerExecutionContext) -> TaskExecutionResult:
        if context.dry_run:
            return result_for_dry_run(task, self.id)
        should_fail = task.id in self.fail_tasks
        if self.fail_times.get(task.id, 0) > 0:
            should_fail = True
            self.fail_times[task.id] -= 1
        if should_fail:
            return TaskExecutionResult(
                task_id=task.id,
                runner_id=self.id,
                status=ExecutionStatus.FAILED,
                finished_at=datetime.now(UTC),
                exit_code=1,
                stderr=self.fail_with,
                failure_category=FailureCategory.FLAKY_TRANSIENT if "transient" in self.fail_with else FailureCategory.UNKNOWN,
            )
        return TaskExecutionResult(
            task_id=task.id,
            runner_id=self.id,
            status=ExecutionStatus.SUCCEEDED,
            finished_at=datetime.now(UTC),
            exit_code=0,
            stdout=f"mock executed {task.id}",
            outputs={"mock": True},
        )

    def health_check(self) -> RunnerHealth:
        return RunnerHealth(runner_id=self.id, healthy=True, details={"kind": self.kind.value})
