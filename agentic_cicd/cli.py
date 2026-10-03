"""Command line interface for local development and tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich import print as rich_print

from agentic_cicd.compilers.registry import PipelineCompilerRegistry
from agentic_cicd.core.enums import PipelineBackend, Role
from agentic_cicd.core.execution import ExecutionRequest
from agentic_cicd.core.identity import Principal
from agentic_cicd.core.intent import IntentParser
from agentic_cicd.core.pipeline import PipelineIR
from agentic_cicd.discovery.repository import RepositoryIntelligenceAgent
from agentic_cicd.orchestration.execution_engine import ExecutionEngine
from agentic_cicd.orchestration.planner import PipelinePlanner
from agentic_cicd.orchestration.scheduler import DagScheduler
from agentic_cicd.events.models import PullRequestAction, SCMProvider
from agentic_cicd.events.samples import sample_pull_request_event
from agentic_cicd.integrations.registry import default_integration_registry
from agentic_cicd.orchestration.control_plane import PullRequestControlPlane
from agentic_cicd.languages.registry import default_language_registry
from agentic_cicd.orchestration.github_delivery import GitHubPRDeliveryService
from agentic_cicd.runners.profiles import RunnerProfileCatalog
from agentic_cicd.runners.registry import default_runner_registry
from agentic_cicd.tools.registry import default_tool_registry
from agentic_cicd.ui.autonomous_dashboard import write_autonomous_sdlc_console

app = typer.Typer(help="Agentic CI/CD control plane CLI")
pipeline_app = typer.Typer(help="Pipeline operations")
execution_app = typer.Typer(help="Execution operations")
security_app = typer.Typer(help="Security operations")
integration_app = typer.Typer(help="Integration operations")
event_app = typer.Typer(help="SCM event / pull request operations")
ui_app = typer.Typer(help="Local UI/report generation")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(execution_app, name="execution")
app.add_typer(security_app, name="security")
app.add_typer(integration_app, name="integrations")
app.add_typer(event_app, name="events")
app.add_typer(ui_app, name="ui")


def _principal(role: Role = Role.DEVELOPER) -> Principal:
    return Principal(id="local-user", roles={role})


@app.command()
def discover(
    path: str = typer.Argument(".", help="Repository path"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON"),
) -> None:
    """Discover repository metadata."""
    context = RepositoryIntelligenceAgent().discover(path)
    data = context.model_dump(mode="json")
    if json_output:
        typer.echo(json.dumps(data, indent=2))
    else:
        rich_print(data)


@app.command()
def plan(
    intent_text: str,
    repo_path: str = typer.Option(".", "--repo-path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Parse intent, discover context, and produce a typed plan."""
    intent = IntentParser.parse(intent_text)
    bundle = RepositoryIntelligenceAgent().context_bundle(intent.id, repo_path)
    planned = PipelinePlanner().plan(intent, bundle, _principal())
    payload = {"intent": intent.model_dump(mode="json"), "explanation": planned.explanation.model_dump(mode="json"), "pipeline": planned.pipeline.model_dump(mode="json")}
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        rich_print(payload)


@pipeline_app.command("generate")
def pipeline_generate(
    intent_text: str,
    repo_path: str = typer.Option(".", "--repo-path"),
    backend: PipelineBackend = typer.Option(PipelineBackend.NATIVE, "--backend"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Generate backend-specific pipeline from IR."""
    intent = IntentParser.parse(intent_text).model_copy(update={"backend": backend})
    bundle = RepositoryIntelligenceAgent().context_bundle(intent.id, repo_path)
    planned = PipelinePlanner().plan(intent, bundle, _principal())
    rendered = PipelineCompilerRegistry().render(planned.pipeline, backend)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        typer.echo(str(output))
    else:
        typer.echo(rendered)


@pipeline_app.command("validate")
def pipeline_validate(path: Path) -> None:
    """Validate a native JSON Pipeline IR file."""
    pipeline = PipelineIR.model_validate_json(path.read_text(encoding="utf-8"))
    pipeline.validate_integrity()
    typer.echo("VALID")


@pipeline_app.command("run")
def pipeline_run(
    path: Path,
    repo_path: str = typer.Option(".", "--repo-path"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute"),
) -> None:
    """Run a native JSON Pipeline IR through typed runners."""
    pipeline = PipelineIR.model_validate_json(path.read_text(encoding="utf-8"))
    record = ExecutionEngine().execute(
        ExecutionRequest(pipeline=pipeline, repo_path=repo_path, dry_run=dry_run), _principal(), None
    )
    typer.echo(record.model_dump_json(indent=2))


@pipeline_app.command("schedule")
def pipeline_schedule(path: Path) -> None:
    """Show parallelizable DAG execution waves for a native JSON Pipeline IR."""
    pipeline = PipelineIR.model_validate_json(path.read_text(encoding="utf-8"))
    schedule = DagScheduler().plan_waves(pipeline)
    typer.echo(schedule.model_dump_json(indent=2))


@app.command("runners")
def runners(json_output: bool = typer.Option(False, "--json")) -> None:
    """List discovered local runner adapters and capabilities."""
    payload = [
        {
            "id": runner.id,
            "kind": runner.kind.value,
            "health": runner.health_check().model_dump(mode="json"),
            "capabilities": runner.capabilities.model_dump(mode="json"),
        }
        for runner in default_runner_registry().list()
    ]
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        rich_print(payload)


@app.command("runner-profiles")
def runner_profiles(json_output: bool = typer.Option(False, "--json")) -> None:
    """List conceptual runner profiles for capability-based planning."""
    payload = [profile.model_dump(mode="json") for profile in RunnerProfileCatalog().list()]
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        rich_print(payload)


@app.command("languages")
def languages(
    repo_path: str = typer.Option(".", "--repo-path", help="Repository path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Detect languages using the language-provider registry."""
    repository = RepositoryIntelligenceAgent().discover(repo_path)
    payload = default_language_registry().summary(repository)
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        rich_print(payload)


@app.command("tools")
def tools(json_output: bool = typer.Option(False, "--json")) -> None:
    """List registered typed tools and contracts."""
    payload = [definition.model_dump(mode="json") for definition in default_tool_registry().definitions()]
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        rich_print(payload)


@security_app.command("sbom")
def security_sbom(path: str = typer.Argument(".", help="Repository path")) -> None:
    """Generate a lightweight local SBOM."""
    from agentic_cicd.tools.sbom import generate_sbom

    typer.echo(generate_sbom(path).model_dump_json(indent=2))


@integration_app.command("list")
def integration_list(json_output: bool = typer.Option(False, "--json")) -> None:
    """List integration adapter status without contacting unconfigured providers."""
    payload = [status.model_dump(mode="json") for status in default_integration_registry().list()]
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        rich_print(payload)


@integration_app.command("github-pr")
def integration_github_pr(
    payload: Path = typer.Option(Path("samples/webhooks/github_pull_request_merged.json"), "--payload", help="GitHub PR webhook payload JSON"),
    repo_path: str = typer.Option("samples/python_app", "--repo-path", help="Checked-out repository path"),
    dry_run_pipeline: bool = typer.Option(True, "--dry-run-pipeline/--execute-pipeline", help="Dry-run or execute local pipeline"),
    send_status: bool = typer.Option(False, "--send-status/--status-dry-run", help="Actually update GitHub commit status if GITHUB_TOKEN is configured"),
    approved: bool = typer.Option(False, "--approved", help="Mark approval as granted"),
    role: Role = typer.Option(Role.DEVELOPER, "--role", help="Principal role"),
    report: Path = typer.Option(Path("reports/github_pr_delivery.html"), "--report", help="HTML report path"),
    target_url: Optional[str] = typer.Option(None, "--target-url", help="Commit status target URL"),
) -> None:
    """Process a GitHub PR payload through the pipeline and optionally report commit status."""
    data = json.loads(payload.read_text(encoding="utf-8"))
    result = GitHubPRDeliveryService().handle_payload(
        data,
        _principal(role),
        repo_path=repo_path,
        dry_run_pipeline=dry_run_pipeline,
        approved=approved,
        report_path=report,
        send_status=send_status,
        status_target_url=target_url,
    )
    typer.echo(json.dumps(result.summary(), indent=2))


@event_app.command("simulate-pr")
def events_simulate_pr(
    repo_path: str = typer.Option("samples/python_app", "--repo-path", help="Repository path"),
    provider: SCMProvider = typer.Option(SCMProvider.GITHUB, "--provider", help="SCM provider"),
    action: PullRequestAction = typer.Option(PullRequestAction.OPENED, "--action", help="PR action"),
    merged: bool = typer.Option(False, "--merged", help="Simulate merged PR/MR"),
    label: Optional[list[str]] = typer.Option(None, "--label", help="Labels such as deploy-staging/deploy-production"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Dry-run or execute local safe commands"),
    approved: bool = typer.Option(False, "--approved", help="Mark required approval as granted"),
    role: Role = typer.Option(Role.DEVELOPER, "--role", help="Principal role"),
    report: Path = typer.Option(Path("reports/pr_pipeline_report.html"), "--report", help="HTML report path"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON summary"),
) -> None:
    """Simulate a PR/MR event through trigger -> CI -> optional local deployment."""
    event = sample_pull_request_event(
        provider=provider,
        repo_path=repo_path,
        action=action,
        merged=merged,
        labels=label or [],
    )
    bundle = PullRequestControlPlane().handle_pull_request(
        event,
        _principal(role),
        dry_run=dry_run,
        approved=approved,
        report_path=report,
    )
    summary = PullRequestControlPlane().bundle_summary(bundle)
    if json_output:
        typer.echo(json.dumps(summary, indent=2))
    else:
        rich_print(summary)
        typer.echo(f"HTML report: {bundle.report_path}")


@ui_app.command("autonomous-demo")
def ui_autonomous_demo(
    repo_path: str = typer.Option("samples/python_app", "--repo-path", help="Repository path"),
    merged: bool = typer.Option(True, "--merged/--open-pr", help="Merged PR deploys to development; open PR validates only"),
    label: Optional[list[str]] = typer.Option(None, "--label", help="Labels such as deploy-staging/deploy-production"),
    dry_run: bool = typer.Option(False, "--dry-run/--execute", help="Dry-run or execute local safe commands"),
    approved: bool = typer.Option(False, "--approved", help="Mark approval as granted"),
    role: Role = typer.Option(Role.DEVELOPER, "--role", help="Principal role"),
    output: Path = typer.Option(Path("reports/autonomous_sdlc_console.html"), "--output", help="Dashboard HTML path"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON summary"),
) -> None:
    """Run a PR/MR pipeline and render the enterprise SDLC console."""
    event = sample_pull_request_event(
        provider=SCMProvider.GITHUB,
        repo_path=repo_path,
        action=PullRequestAction.MERGED if merged else PullRequestAction.OPENED,
        merged=merged,
        labels=label or [],
    )
    control_plane = PullRequestControlPlane()
    bundle = control_plane.handle_pull_request(
        event,
        _principal(role),
        dry_run=dry_run,
        approved=approved,
        report_path=None,
    )
    write_autonomous_sdlc_console(output, bundle)
    summary = control_plane.bundle_summary(bundle)
    summary["dashboard_path"] = str(output)
    if json_output:
        typer.echo(json.dumps(summary, indent=2))
    else:
        rich_print(summary)
        typer.echo(f"Autonomous SDLC console: {output}")


@execution_app.command("status")
def execution_status(execution_id: str) -> None:
    """Placeholder for persistent execution lookup."""
    typer.echo(f"NOT_IMPLEMENTED: persistent execution store is not configured for {execution_id}")


if __name__ == "__main__":  # pragma: no cover
    app()
