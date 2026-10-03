"""Typed context engineering primitives."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentic_cicd.core.enums import TrustLevel


class ContextSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    uri: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    freshness_seconds: int | None = Field(default=None, ge=0)
    policy_relevance: list[str] = Field(default_factory=list)
    trust_level: TrustLevel = TrustLevel.EXTERNAL
    notes: str | None = None


class RepositoryContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    name: str
    is_git_repo: bool = False
    current_branch: str | None = None
    current_commit: str | None = None
    remotes: list[str] = Field(default_factory=list)
    languages: dict[str, int] = Field(default_factory=dict)
    package_managers: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    build_systems: list[str] = Field(default_factory=list)
    test_frameworks: list[str] = Field(default_factory=list)
    dockerfiles: list[str] = Field(default_factory=list)
    kubernetes_manifests: list[str] = Field(default_factory=list)
    helm_charts: list[str] = Field(default_factory=list)
    terraform_modules: list[str] = Field(default_factory=list)
    ci_configs: list[str] = Field(default_factory=list)
    documentation: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    secret_reference_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        return str(Path(value).expanduser().resolve())


class ContextBundle(BaseModel):
    """All context used by planning and policy with provenance and trust annotations."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    sources: list[ContextSource] = Field(default_factory=list)
    repository: RepositoryContext | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    policies: list[dict[str, Any]] = Field(default_factory=list)
    templates: list[dict[str, Any]] = Field(default_factory=list)
    graph_facts: list[dict[str, Any]] = Field(default_factory=list)
    rag_documents: list[dict[str, Any]] = Field(default_factory=list)
    execution_history: list[dict[str, Any]] = Field(default_factory=list)
    incidents: list[dict[str, Any]] = Field(default_factory=list)
    memory: dict[str, Any] = Field(default_factory=dict)

    def add_source(self, source: ContextSource) -> None:
        self.sources.append(source)

    def untrusted_repository_texts(self) -> list[dict[str, Any]]:
        """Return repository/RAG docs that must never be interpreted as control instructions."""
        return [
            document
            for document in self.rag_documents
            if document.get("trust_level") == TrustLevel.REPOSITORY.value
        ]
