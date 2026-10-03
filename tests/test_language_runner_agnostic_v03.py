from __future__ import annotations

from agentic_cicd.core.enums import Role
from agentic_cicd.core.identity import Principal
from agentic_cicd.core.intent import IntentParser
from agentic_cicd.discovery.repository import RepositoryIntelligenceAgent
from agentic_cicd.languages.registry import default_language_registry
from agentic_cicd.orchestration.planner import PipelinePlanner
from agentic_cicd.orchestration.pr_pipeline import PRPipelineFactory
from agentic_cicd.runners.profiles import RunnerProfileCatalog
from agentic_cicd.events.samples import sample_pull_request_event


def _repo(path: str):
    return RepositoryIntelligenceAgent().discover(path)


def test_language_registry_detects_python_node_go_java() -> None:
    registry = default_language_registry()
    assert registry.detect(_repo("samples/python_app"))[0].provider_id == "python"
    assert any(d.provider_id == "node" for d in registry.detect(_repo("samples/node_app")))
    assert any(d.provider_id == "go" for d in registry.detect(_repo("samples/go_app")))
    assert any(d.provider_id == "java" for d in registry.detect(_repo("samples/java_maven_app")))


def test_node_plan_contains_node_tasks_without_execution() -> None:
    intent = IntentParser.parse("Generate a CI pipeline")
    bundle = RepositoryIntelligenceAgent().context_bundle(intent.id, "samples/node_app")
    planned = PipelinePlanner().plan(intent, bundle, Principal(id="dev", roles={Role.DEVELOPER}))
    task_ids = {task.id for task in planned.pipeline.all_steps()}
    assert "node_install_dependencies" in task_ids
    assert "node_lint" in task_ids
    assert "node_unit_tests" in task_ids
    assert "node_build" in task_ids


def test_go_and_java_plans_contain_language_builds() -> None:
    for path, expected in [("samples/go_app", "go_build"), ("samples/java_maven_app", "java_build")]:
        intent = IntentParser.parse("Generate a CI pipeline")
        bundle = RepositoryIntelligenceAgent().context_bundle(intent.id, path)
        planned = PipelinePlanner().plan(intent, bundle, Principal(id="dev", roles={Role.DEVELOPER}))
        task_ids = {task.id for task in planned.pipeline.all_steps()}
        assert expected in task_ids


def test_pr_pipeline_uses_language_registry_for_node_repo() -> None:
    repo = _repo("samples/node_app")
    event = sample_pull_request_event(repo_path="samples/node_app", merged=False)
    pipeline, explanation = PRPipelineFactory().build(event, repo, actor="dev")
    task_ids = {task.id for task in pipeline.all_steps()}
    assert "node_unit_tests" in task_ids
    assert "node_build" in task_ids
    assert "Node execution requires" in " ".join(explanation.notes)


def test_runner_profiles_match_polyglot_tools() -> None:
    intent = IntentParser.parse("Generate a CI pipeline")
    bundle = RepositoryIntelligenceAgent().context_bundle(intent.id, "samples/node_app")
    planned = PipelinePlanner().plan(intent, bundle, Principal(id="dev", roles={Role.DEVELOPER}))
    profile_map = RunnerProfileCatalog().explain_for_tasks(planned.pipeline.all_steps())
    assert "github-ubuntu-polyglot" in profile_map["node_unit_tests"]
