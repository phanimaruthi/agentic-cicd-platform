"""Runner abstraction for execution plane adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import ExecutionStatus, RiskLevel, RunnerKind
from agentic_cicd.core.execution import TaskExecutionResult
from agentic_cicd.core.task import RunnerCapabilityRequest, TaskSpec


class RunnerCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    os: str = "linux"
    architecture: str = "x86_64"
    tools: set[str] = Field(default_factory=set)
    network_access: bool = False
    cloud_access: bool = False
    docker: bool = False
    kubernetes: bool = False
    privileged: bool = False
    cpu: float = 1.0
    memory_mb: int = 512
    gpu: bool = False
    security_level: str = "sandbox"
    cost_per_minute: float = 0.0
    timeout_limit_seconds: int = 3600
    concurrency: int = 1
    max_command_risk: RiskLevel = RiskLevel.LOW_RISK

    def satisfies(self, request: RunnerCapabilityRequest) -> bool:
        if request.os and self.os not in request.os:
            return False
        if request.architecture and self.architecture not in request.architecture:
            return False
        if request.tools and not request.tools.issubset(self.tools):
            return False
        for field_name in ("network_access", "cloud_access", "docker", "kubernetes", "privileged", "gpu"):
            requested = getattr(request, field_name)
            if requested is not None and getattr(self, field_name) != requested:
                return False
        if request.min_cpu is not None and self.cpu < request.min_cpu:
            return False
        if request.min_memory_mb is not None and self.memory_mb < request.min_memory_mb:
            return False
        if request.security_level is not None and self.security_level != request.security_level:
            return False
        if request.max_cost_per_minute is not None and self.cost_per_minute > request.max_cost_per_minute:
            return False
        return True


class RunnerHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runner_id: str
    healthy: bool
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)


class RunnerExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str
    workdir: str = "."
    dry_run: bool = True
    environment: dict[str, str] = Field(default_factory=dict)
    approved: bool = False

    @property
    def cwd(self) -> Path:
        return Path(self.workdir).expanduser().resolve()


class Runner(ABC):
    id: str
    kind: RunnerKind
    capabilities: RunnerCapabilities

    @abstractmethod
    def validate(self, task: TaskSpec) -> None:
        """Validate a task can be executed by this runner."""

    @abstractmethod
    def execute(self, task: TaskSpec, context: RunnerExecutionContext) -> TaskExecutionResult:
        """Execute a task and return structured output."""

    @abstractmethod
    def health_check(self) -> RunnerHealth:
        """Return runner health."""

    def cancel(self, execution_id: str) -> bool:
        return False

    def collect_logs(self, execution_id: str) -> str:
        return ""

    def collect_outputs(self, execution_id: str) -> dict[str, Any]:
        return {}


def result_for_dry_run(task: TaskSpec, runner_id: str) -> TaskExecutionResult:
    return TaskExecutionResult(
        task_id=task.id,
        runner_id=runner_id,
        status=ExecutionStatus.SUCCEEDED,
        finished_at=datetime.now(UTC),
        duration_ms=0,
        exit_code=0,
        stdout=f"DRY RUN: {task.name}",
        outputs={"dry_run": True, "command": task.command},
    )
