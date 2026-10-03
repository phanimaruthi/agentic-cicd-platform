"""Optional FastAPI application factory.

FastAPI is an optional dependency. If not installed, create_app returns a structured
NOT_IMPLEMENTED error instead of pretending an API server exists.
"""

from __future__ import annotations

from typing import Any


def create_app() -> Any:
    try:
        from fastapi import FastAPI
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional dep
        raise RuntimeError(
            "NOT_IMPLEMENTED: install agentic-cicd[api] to enable the HTTP API runtime"
        ) from exc

    from agentic_cicd.api.schemas import (
        AgentRequest,
        PipelineGenerateResponse,
        PullRequestWebhookRequest,
        PullRequestWebhookResponse,
    )
    from agentic_cicd.compilers.registry import PipelineCompilerRegistry
    from agentic_cicd.core.identity import Principal
    from agentic_cicd.core.intent import IntentParser
    from agentic_cicd.discovery.repository import RepositoryIntelligenceAgent
    from agentic_cicd.events.parsers import parse_pull_request_event
    from agentic_cicd.orchestration.control_plane import PullRequestControlPlane
    from agentic_cicd.orchestration.planner import PipelinePlanner

    app = FastAPI(title="Agentic CI/CD Control Plane", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/pipelines/generate", response_model=PipelineGenerateResponse)
    def generate(request: AgentRequest) -> PipelineGenerateResponse:
        intent = IntentParser.parse(request.intent)
        bundle = RepositoryIntelligenceAgent().context_bundle(intent.id, request.repository_path)
        principal = Principal(id=request.principal_id, roles=request.roles)
        planned = PipelinePlanner().plan(intent, bundle, principal)
        rendered = PipelineCompilerRegistry().render(planned.pipeline, intent.backend)
        return PipelineGenerateResponse(
            pipeline=planned.pipeline,
            rendered=rendered,
            explanation=planned.explanation.model_dump(mode="json"),
        )

    @app.post("/webhooks/pull-request", response_model=PullRequestWebhookResponse)
    def pull_request_webhook(request: PullRequestWebhookRequest) -> PullRequestWebhookResponse:
        """Normalize a provider PR/MR webhook and run the agentic delivery flow.

        This endpoint is available only when optional API dependencies are installed.
        Real production usage still needs provider signature verification, network
        exposure, persistence, and credentials configured by the operator.
        """
        event = parse_pull_request_event(request.provider, request.payload, repo_path=request.repository_path)
        principal = Principal(id=request.principal_id, roles=request.roles)
        control_plane = PullRequestControlPlane()
        bundle = control_plane.handle_pull_request(
            event,
            principal,
            dry_run=request.dry_run,
            approved=request.approved,
        )
        return PullRequestWebhookResponse(summary=control_plane.bundle_summary(bundle))

    return app
