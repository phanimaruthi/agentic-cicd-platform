"""DAG scheduling helpers for parallelism planning."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.errors import PipelineValidationError
from agentic_cicd.core.pipeline import PipelineIR


class ExecutionWave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    task_ids: list[str] = Field(default_factory=list)


class DagSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    waves: list[ExecutionWave]
    max_parallelism: int


class DagScheduler:
    def plan_waves(self, pipeline: PipelineIR) -> DagSchedule:
        steps = pipeline.step_by_id()
        indegree: dict[str, int] = {task_id: 0 for task_id in steps}
        outgoing: dict[str, list[str]] = {task_id: [] for task_id in steps}
        for source, target in pipeline.dependency_edges():
            if source not in steps or target not in steps:
                raise PipelineValidationError("dependency edge references missing step")
            outgoing[source].append(target)
            indegree[target] += 1
        ready = sorted([task_id for task_id, degree in indegree.items() if degree == 0])
        waves: list[ExecutionWave] = []
        visited = 0
        while ready:
            current = ready[: pipeline.execution_strategy.max_parallelism]
            ready = ready[pipeline.execution_strategy.max_parallelism :]
            waves.append(ExecutionWave(index=len(waves), task_ids=current))
            visited += len(current)
            newly_ready: list[str] = []
            for task_id in current:
                for target in sorted(outgoing[task_id]):
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        newly_ready.append(target)
            ready = sorted(set(ready + newly_ready))
        if visited != len(steps):
            raise PipelineValidationError("pipeline contains circular dependencies")
        return DagSchedule(waves=waves, max_parallelism=pipeline.execution_strategy.max_parallelism)
