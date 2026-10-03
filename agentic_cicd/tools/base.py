"""Typed tool architecture shared by local tools and future MCP adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import Permission, RiskLevel


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permission_requirements: set[Permission] = Field(default_factory=set)
    risk_level: RiskLevel = RiskLevel.SAFE
    side_effects: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=60, ge=1)
    retry_behavior: str = "none"
    audit_behavior: str = "emit_start_and_finish"
    version: str = "0.1.0"


class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    actor: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dry_run: bool = True


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invocation_id: str
    tool_name: str
    success: bool
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TypedTool(ABC):
    definition: ToolDefinition

    @abstractmethod
    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        """Run a typed tool invocation and return structured output."""
