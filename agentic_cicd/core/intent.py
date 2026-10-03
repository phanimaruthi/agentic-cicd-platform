"""Deterministic user intent parsing.

The parser provides a typed first pass. LLM structured output can be added behind this
interface later, but free-form model prose is not used for execution decisions.
"""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import AutonomyLevel, IntentAction, PipelineBackend


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    raw_text: str
    action: IntentAction
    target: str | None = None
    environment: str | None = None
    backend: PipelineBackend = PipelineBackend.NATIVE
    dry_run: bool = True
    autonomy_level: AutonomyLevel = AutonomyLevel.DETERMINISTIC
    requested_outputs: list[str] = Field(default_factory=list)
    constraints: dict[str, str] = Field(default_factory=dict)


class IntentParser:
    """Small deterministic parser used before any optional model reasoning."""

    ENVIRONMENTS = ("production", "prod", "staging", "stage", "development", "dev", "test")

    @classmethod
    def parse(cls, text: str) -> Intent:
        normalized = " ".join(text.lower().strip().split())
        action = IntentAction.UNKNOWN
        requested_outputs: list[str] = []
        backend = PipelineBackend.NATIVE

        if any(token in normalized for token in ("impact", "blast radius", "downstream")):
            action = IntentAction.IMPACT_ANALYSIS
        elif "rollback" in normalized:
            action = IntentAction.ROLLBACK
        elif any(token in normalized for token in ("diagnose", "why failed", "failure", "crashloop")):
            action = IntentAction.DIAGNOSE
        elif "remediate" in normalized or "fix" in normalized:
            action = IntentAction.REMEDIATE
        elif "security" in normalized or "scan" in normalized or "vulnerability" in normalized:
            action = IntentAction.SECURITY_CHECKS
        elif "docker" in normalized or "image" in normalized or "publish" in normalized:
            action = IntentAction.BUILD_IMAGE
        elif "deploy" in normalized or "promote" in normalized:
            action = IntentAction.PREPARE_DEPLOYMENT if "prepare" in normalized else IntentAction.DEPLOY
        elif "pipeline" in normalized or "ci" in normalized or "workflow" in normalized:
            action = IntentAction.GENERATE_PIPELINE
        elif "build" in normalized or "test" in normalized:
            action = IntentAction.BUILD_AND_TEST
        elif "analyze" in normalized or "discover" in normalized or "how to build" in normalized:
            action = IntentAction.ANALYZE_REPOSITORY

        if "github" in normalized or "github actions" in normalized:
            backend = PipelineBackend.GITHUB_ACTIONS
        elif "gitlab" in normalized:
            backend = PipelineBackend.GITLAB_CI
        elif "jenkins" in normalized:
            backend = PipelineBackend.JENKINS

        environment = None
        for env in cls.ENVIRONMENTS:
            if env in normalized:
                environment = "production" if env == "prod" else "staging" if env == "stage" else "development" if env == "dev" else env
                break

        if "yaml" in normalized or "yml" in normalized:
            requested_outputs.append("yaml")
        if "json" in normalized:
            requested_outputs.append("json")
        if "dry run" in normalized or "dry-run" in normalized or "prepare" in normalized:
            dry_run = True
        else:
            dry_run = action in {
                IntentAction.GENERATE_PIPELINE,
                IntentAction.ANALYZE_REPOSITORY,
                IntentAction.PREPARE_DEPLOYMENT,
                IntentAction.IMPACT_ANALYSIS,
            }

        return Intent(
            raw_text=text,
            action=action,
            environment=environment,
            backend=backend,
            dry_run=dry_run,
            requested_outputs=requested_outputs,
        )
