from __future__ import annotations

from pathlib import Path

from agentic_cicd.core.enums import ExecutionStatus, Role
from agentic_cicd.core.execution import ExecutionRequest
from agentic_cicd.core.identity import Principal
from agentic_cicd.deployments.rollback import RollbackPlanner
from agentic_cicd.deployments.verification import DeploymentVerificationRequest, DeploymentVerifier, HealthThreshold
from agentic_cicd.observability.providers import MockObservabilityProvider
from agentic_cicd.orchestration.execution_engine import ExecutionEngine
from agentic_cicd.orchestration.scheduler import DagScheduler
from agentic_cicd.orchestration.store import InMemoryExecutionStore, JsonExecutionStore
from agentic_cicd.templates.registry import default_template_registry
from agentic_cicd.tools.sbom import generate_sbom


def test_python_ci_template_instantiates_and_schedules_parallel_waves() -> None:
    template = default_template_registry().get("python-ci")
    pipeline = template.instantiate({"service": "sample"})
    assert pipeline.metadata.labels["template_id"] == "python-ci"
    schedule = DagScheduler().plan_waves(pipeline)
    assert schedule.waves
    wave_sets = [set(wave.task_ids) for wave in schedule.waves]
    assert any({"unit_tests", "secret_scan", "generate_sbom"}.intersection(wave) for wave in wave_sets)


def test_lightweight_sbom_finds_sample_project_metadata() -> None:
    sbom = generate_sbom("samples/python_app")
    assert Path(sbom.source).parts[-2:] == ("samples", "python_app")
    assert sbom.bom_format == "agentic-cicd-local-sbom"


def test_deployment_verifier_recommends_rollback_on_bad_health() -> None:
    provider = MockObservabilityProvider(metrics={"error_rate": 0.2, "p95_latency_ms": 900.0})
    result = DeploymentVerifier(provider).verify(
        DeploymentVerificationRequest(
            service="checkout",
            environment="production",
            thresholds=[HealthThreshold(metric="error_rate", operator="<=", value=0.01)],
        )
    )
    assert result.passed is False
    assert result.rollback_recommended is True
    plan = RollbackPlanner().plan_from_verification(result)
    assert plan.requires_approval is True
    assert plan.tasks[0].risk == "HIGH_RISK"


def test_execution_store_persists_records_in_memory_and_json(tmp_path) -> None:
    template = default_template_registry().get("python-ci")
    pipeline = template.instantiate({"service": "sample"})
    mem_store = InMemoryExecutionStore()
    record = ExecutionEngine(store=mem_store).execute(
        ExecutionRequest(pipeline=pipeline, repo_path="samples/python_app", dry_run=True),
        Principal(id="dev", roles={Role.DEVELOPER}),
        None,
    )
    assert record.status == ExecutionStatus.SUCCEEDED
    assert mem_store.get(record.id) is not None
    json_store = JsonExecutionStore(tmp_path)
    json_store.save(record)
    assert json_store.get(record.id) is not None
