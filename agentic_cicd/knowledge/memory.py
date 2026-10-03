"""Structured short-term and long-term memory."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_pipeline_id: str | None = None
    current_failures: list[dict[str, Any]] = Field(default_factory=list)
    current_plan: dict[str, Any] = Field(default_factory=dict)
    current_environment: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrganizationalMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    common_failures: list[dict[str, Any]] = Field(default_factory=list)
    successful_remediations: list[dict[str, Any]] = Field(default_factory=list)
    deployment_patterns: list[dict[str, Any]] = Field(default_factory=list)
    preferred_templates: list[dict[str, Any]] = Field(default_factory=list)
    team_standards: list[dict[str, Any]] = Field(default_factory=list)
    architecture_decisions: list[dict[str, Any]] = Field(default_factory=list)
    historical_outcomes: list[dict[str, Any]] = Field(default_factory=list)

    def record_execution_outcome(self, outcome: dict[str, Any]) -> None:
        self.historical_outcomes.append({**outcome, "recorded_at": datetime.now(UTC).isoformat()})
