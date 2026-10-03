from __future__ import annotations

from agentic_cicd.core.enums import ExecutionStatus, Role, TaskCategory
from agentic_cicd.core.execution import ExecutionRequest
from agentic_cicd.core.identity import Principal
from agentic_cicd.core.pipeline import PipelineIR, PipelineMetadata, PipelineStage
from agentic_cicd.core.task import TaskSpec
from agentic_cicd.discovery.repository import RepositoryIntelligenceAgent
from agentic_cicd.knowledge.graph import KGEntity, KGRelationship, KnowledgeGraph
from agentic_cicd.orchestration.execution_engine import ExecutionEngine
from agentic_cicd.runners.mock import MockRunner
from agentic_cicd.runners.registry import RunnerRegistry


def test_failure_generates_diagnosis_and_remediation_plan() -> None:
    registry = RunnerRegistry()
    registry.register(MockRunner(fail_tasks={"unit_tests"}, fail_with="simulated transient network failure"))
    pipeline = PipelineIR(
        metadata=PipelineMetadata(name="failure-demo"),
        stages=[
            PipelineStage(
                id="test",
                name="Test",
                type="test",
                steps=[
                    TaskSpec(
                        id="unit_tests",
                        type="unit_test",
                        name="Unit tests",
                        category=TaskCategory.TEST,
                        runner="mock-runner",
                        command=["pytest"],
                    )
                ],
            )
        ],
    )
    record = ExecutionEngine(runners=registry).execute(
        ExecutionRequest(pipeline=pipeline, repo_path=".", dry_run=False),
        Principal(id="dev", roles={Role.DEVELOPER}),
        None,
    )
    assert record.status == ExecutionStatus.FAILED
    assert record.diagnosis[0]["category"] == "flaky_transient"
    assert record.remediation[0]["actions"][0]["id"] == "bounded_retry"


def test_knowledge_graph_answers_downstream_impact() -> None:
    graph = KnowledgeGraph()
    graph.add_entity(KGEntity(id="service:a", type="service", name="A"))
    graph.add_entity(KGEntity(id="service:b", type="service", name="B"))
    graph.add_relationship(
        KGRelationship(source="service:b", target="service:a", type="SERVICE_DEPENDS_ON_SERVICE")
    )
    assert graph.downstream_impact("service:a") == ["service:b"]


def test_repository_ingest_creates_service_entities() -> None:
    repo = RepositoryIntelligenceAgent().discover("samples/python_app")
    graph = KnowledgeGraph()
    graph.ingest_repository(repo)
    assert graph.get_entity("repository:python_app") is not None
    assert graph.relationships("repository:python_app", "REPOSITORY_CONTAINS_SERVICE")
