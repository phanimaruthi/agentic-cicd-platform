"""Pipeline Intermediate Representation (IR) and deterministic validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_cicd.core.enums import AutonomyLevel, RiskLevel
from agentic_cicd.core.errors import PipelineValidationError
from agentic_cicd.core.task import TaskSpec


class PipelineMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str | None = None
    repository: str | None = None
    service: str | None = None
    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    labels: dict[str, str] = Field(default_factory=dict)


class PipelineTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    branches: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)
    schedule: str | None = None


class EnvironmentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str = "generic"
    requires_approval: bool = False
    protected: bool = False
    url: str | None = None


class ApprovalGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    approvers: list[str] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    environment: str | None = None
    reason: str


class PipelineDependency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    source: str
    target: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "dag"
    max_parallelism: int = Field(default=4, ge=1)
    environment_locks: list[str] = Field(default_factory=list)
    cancel_in_progress: bool = False
    retry_transient_failures: bool = True
    max_agent_runtime_seconds: int = Field(default=3600, ge=1)
    max_tool_calls: int = Field(default=100, ge=1)
    max_model_cost_usd: float = Field(default=1.0, ge=0)
    max_pipeline_runtime_seconds: int = Field(default=7200, ge=1)


class PipelineStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    type: str
    dependencies: list[str] = Field(default_factory=list)
    steps: list[TaskSpec] = Field(default_factory=list)
    strategy: str = "sequential"
    conditions: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=1800, ge=1, le=86_400)
    failure_strategy: str = "fail_fast"


class PipelineIR(BaseModel):
    """Normalized typed Pipeline IR independent of CI/CD backend YAML."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "v1"
    metadata: PipelineMetadata
    triggers: list[PipelineTrigger] = Field(default_factory=list)
    variables: dict[str, str] = Field(default_factory=dict)
    stages: list[PipelineStage]
    policies: list[str] = Field(default_factory=list)
    approvals: list[ApprovalGate] = Field(default_factory=list)
    environments: list[EnvironmentSpec] = Field(default_factory=list)
    dependencies: list[PipelineDependency] = Field(default_factory=list)
    execution_strategy: ExecutionStrategy = Field(default_factory=ExecutionStrategy)
    autonomy_level: AutonomyLevel = AutonomyLevel.DETERMINISTIC

    @model_validator(mode="after")
    def validate_integrity(self) -> "PipelineIR":
        self._validate_unique_ids()
        self._validate_stage_dependencies()
        self._validate_step_dependencies()
        self._validate_acyclic()
        self._validate_environment_references()
        return self

    def all_steps(self) -> list[TaskSpec]:
        return [step for stage in self.stages for step in stage.steps]

    def stage_by_id(self) -> dict[str, PipelineStage]:
        return {stage.id: stage for stage in self.stages}

    def step_by_id(self) -> dict[str, TaskSpec]:
        return {step.id: step for step in self.all_steps()}

    def max_risk(self) -> RiskLevel:
        order = {RiskLevel.SAFE: 0, RiskLevel.LOW_RISK: 1, RiskLevel.MEDIUM_RISK: 2, RiskLevel.HIGH_RISK: 3, RiskLevel.DESTRUCTIVE: 4}
        current = RiskLevel.SAFE
        for step in self.all_steps():
            if order[step.risk] > order[current]:
                current = step.risk
        return current

    def dependency_edges(self) -> list[tuple[str, str]]:
        """Return edges as (dependency, step) including stage-level dependencies."""
        edges: list[tuple[str, str]] = []
        stages = self.stage_by_id()
        for stage in self.stages:
            for step in stage.steps:
                edges.extend((dependency, step.id) for dependency in step.depends_on)
                for stage_dependency in stage.dependencies:
                    for dependency_step in stages[stage_dependency].steps:
                        edges.append((dependency_step.id, step.id))
        return edges

    def topological_steps(self) -> list[TaskSpec]:
        steps = self.step_by_id()
        indegree: dict[str, int] = {step_id: 0 for step_id in steps}
        outgoing: dict[str, list[str]] = {step_id: [] for step_id in steps}
        for source, target in self.dependency_edges():
            outgoing[source].append(target)
            indegree[target] += 1
        ready = sorted([step_id for step_id, degree in indegree.items() if degree == 0])
        ordered: list[str] = []
        while ready:
            step_id = ready.pop(0)
            ordered.append(step_id)
            for target in sorted(outgoing[step_id]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
                    ready.sort()
        if len(ordered) != len(steps):
            raise PipelineValidationError("pipeline contains circular step dependencies")
        return [steps[step_id] for step_id in ordered]

    def _validate_unique_ids(self) -> None:
        stage_ids = [stage.id for stage in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise PipelineValidationError("duplicate stage identifiers are not allowed")
        step_ids = [step.id for step in self.all_steps()]
        if len(step_ids) != len(set(step_ids)):
            raise PipelineValidationError("duplicate step/task identifiers are not allowed")
        approval_ids = [approval.id for approval in self.approvals]
        if len(approval_ids) != len(set(approval_ids)):
            raise PipelineValidationError("duplicate approval gate identifiers are not allowed")

    def _validate_stage_dependencies(self) -> None:
        stage_ids = set(self.stage_by_id())
        for stage in self.stages:
            missing = set(stage.dependencies) - stage_ids
            if missing:
                raise PipelineValidationError(
                    f"stage {stage.id!r} depends on missing stages {sorted(missing)!r}",
                    metadata={"stage": stage.id, "missing": sorted(missing)},
                )

    def _validate_step_dependencies(self) -> None:
        step_ids = set(self.step_by_id())
        for step in self.all_steps():
            missing = set(step.depends_on) - step_ids
            if missing:
                raise PipelineValidationError(
                    f"step {step.id!r} depends on missing steps {sorted(missing)!r}",
                    metadata={"step": step.id, "missing": sorted(missing)},
                )

    def _validate_acyclic(self) -> None:
        self.topological_steps()
        stage_ids = set(self.stage_by_id())
        indegree: dict[str, int] = {stage_id: 0 for stage_id in stage_ids}
        outgoing: dict[str, list[str]] = {stage_id: [] for stage_id in stage_ids}
        for stage in self.stages:
            for dependency in stage.dependencies:
                outgoing[dependency].append(stage.id)
                indegree[stage.id] += 1
        ready = [stage_id for stage_id, degree in indegree.items() if degree == 0]
        visited = 0
        while ready:
            stage_id = ready.pop()
            visited += 1
            for target in outgoing[stage_id]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
        if visited != len(stage_ids):
            raise PipelineValidationError("pipeline contains circular stage dependencies")

    def _validate_environment_references(self) -> None:
        environment_names = {environment.name for environment in self.environments}
        for approval in self.approvals:
            if approval.environment and approval.environment not in environment_names:
                raise PipelineValidationError(
                    f"approval {approval.id!r} references missing environment {approval.environment!r}",
                    metadata={"approval": approval.id, "environment": approval.environment},
                )
