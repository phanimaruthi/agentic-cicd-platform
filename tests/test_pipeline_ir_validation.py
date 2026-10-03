from __future__ import annotations

import pytest

from agentic_cicd.core.enums import RiskLevel, TaskCategory
from agentic_cicd.core.errors import PipelineValidationError
from agentic_cicd.core.pipeline import PipelineIR, PipelineMetadata, PipelineStage
from agentic_cicd.core.task import TaskSpec


def step(step_id: str, depends_on: list[str] | None = None) -> TaskSpec:
    return TaskSpec(
        id=step_id,
        type="unit_test",
        name=step_id,
        category=TaskCategory.TEST,
        command=["python", "-c", "print('ok')"],
        risk=RiskLevel.SAFE,
        depends_on=depends_on or [],
    )


def test_pipeline_accepts_dag_and_topological_order() -> None:
    pipeline = PipelineIR(
        metadata=PipelineMetadata(name="dag"),
        stages=[
            PipelineStage(id="build", name="Build", type="build", steps=[step("build")]),
            PipelineStage(
                id="test",
                name="Test",
                type="test",
                dependencies=["build"],
                steps=[step("unit"), step("security")],
            ),
            PipelineStage(
                id="deploy",
                name="Deploy",
                type="deploy",
                dependencies=["test"],
                steps=[step("deploy")],
            ),
        ],
    )
    assert [task.id for task in pipeline.topological_steps()][0] == "build"
    assert pipeline.dependency_edges()


def test_pipeline_rejects_duplicate_step_ids() -> None:
    with pytest.raises(PipelineValidationError):
        PipelineIR(
            metadata=PipelineMetadata(name="duplicate"),
            stages=[PipelineStage(id="s", name="Stage", type="test", steps=[step("x"), step("x")])],
        )


def test_pipeline_rejects_step_cycle() -> None:
    with pytest.raises(PipelineValidationError):
        PipelineIR(
            metadata=PipelineMetadata(name="cycle"),
            stages=[
                PipelineStage(
                    id="s",
                    name="Stage",
                    type="test",
                    steps=[step("a", ["b"]), step("b", ["a"])],
                )
            ],
        )


def test_task_rejects_raw_secret_env_value() -> None:
    with pytest.raises(ValueError):
        TaskSpec(
            id="bad_secret",
            type="lint",
            name="Bad secret",
            category=TaskCategory.TEST,
            environment={"API_TOKEN": "plain-text-token"},
        )
