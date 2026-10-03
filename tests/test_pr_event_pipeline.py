from __future__ import annotations

import json
from pathlib import Path

from agentic_cicd.core.enums import ExecutionStatus, Role
from agentic_cicd.core.identity import Principal
from agentic_cicd.events.models import PullRequestAction, SCMProvider
from agentic_cicd.events.parsers import parse_github_pull_request, parse_gitlab_merge_request
from agentic_cicd.events.samples import sample_pull_request_event
from agentic_cicd.orchestration.control_plane import PullRequestControlPlane


def test_github_pull_request_parser_normalizes_event() -> None:
    payload = {
        "action": "opened",
        "number": 7,
        "repository": {"full_name": "org/repo", "default_branch": "main"},
        "pull_request": {
            "number": 7,
            "title": "Add feature",
            "merged": False,
            "user": {"login": "alice"},
            "head": {"ref": "feature/a", "sha": "abc"},
            "base": {"ref": "main"},
            "labels": [{"name": "ci"}],
        },
    }
    event = parse_github_pull_request(payload, repo_path="samples/python_app")
    assert event.provider == SCMProvider.GITHUB
    assert event.action == PullRequestAction.OPENED
    assert event.pr_number == "7"
    assert event.source_branch == "feature/a"


def test_gitlab_merge_request_parser_normalizes_merged_event() -> None:
    payload = {
        "object_attributes": {
            "iid": 3,
            "title": "Ship feature",
            "state": "merged",
            "source_branch": "feature/a",
            "target_branch": "main",
            "last_commit": {"id": "def"},
        },
        "project": {"path_with_namespace": "org/repo", "default_branch": "main"},
        "user": {"username": "bob"},
        "labels": [{"title": "deploy-staging"}],
    }
    event = parse_gitlab_merge_request(payload, repo_path="samples/python_app")
    assert event.provider == SCMProvider.GITLAB
    assert event.merged is True
    assert event.requested_environment == "staging"


def test_pr_opened_runs_validation_pipeline_and_no_deployment(tmp_path: Path) -> None:
    event = sample_pull_request_event(repo_path="samples/python_app", action=PullRequestAction.OPENED)
    bundle = PullRequestControlPlane().handle_pull_request(
        event,
        Principal(id="dev", roles={Role.DEVELOPER}),
        dry_run=True,
        report_path=tmp_path / "report.html",
    )
    assert bundle.execution.status == ExecutionStatus.SUCCEEDED
    assert not any(stage.type == "deployment" for stage in bundle.pipeline.stages)
    assert (tmp_path / "report.html").exists()
    assert "Agentic CI/CD Pipeline" in (tmp_path / "report.html").read_text(encoding="utf-8")


def test_merged_pr_executes_local_development_deployment(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    # Copy only the sample app source to keep deployment state isolated.
    import shutil

    shutil.copytree("samples/python_app", repo)
    event = sample_pull_request_event(repo_path=str(repo), merged=True)
    bundle = PullRequestControlPlane().handle_pull_request(
        event,
        Principal(id="dev", roles={Role.DEVELOPER}),
        dry_run=False,
        report_path=tmp_path / "deploy-report.html",
    )
    assert bundle.execution.status == ExecutionStatus.SUCCEEDED
    assert any(result.task_id == "deploy_development" for result in bundle.execution.results)
    deployment_files = list((repo / ".agentic_cicd" / "deployments" / "development").glob("*.json"))
    assert deployment_files
    state = json.loads(deployment_files[0].read_text(encoding="utf-8"))
    assert state["status"] == "healthy"
