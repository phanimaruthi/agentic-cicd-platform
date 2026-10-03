"""Typed task system for pipeline steps."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agentic_cicd.core.enums import RiskLevel, TaskCategory


class SecretReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    ref: str
    required: bool = True

    @field_validator("ref")
    @classmethod
    def must_be_secret_reference(cls, value: str) -> str:
        if not value.startswith("secret://"):
            raise ValueError("secret references must use secret://provider/path/key form")
        return value


class RunnerCapabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    os: set[str] = Field(default_factory=set)
    architecture: set[str] = Field(default_factory=set)
    tools: set[str] = Field(default_factory=set)
    network_access: bool | None = None
    cloud_access: bool | None = None
    docker: bool | None = None
    kubernetes: bool | None = None
    privileged: bool | None = None
    min_cpu: float | None = Field(default=None, ge=0)
    min_memory_mb: int | None = Field(default=None, ge=0)
    gpu: bool | None = None
    security_level: str | None = None
    max_cost_per_minute: float | None = Field(default=None, ge=0)


class CacheSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    paths: list[str]
    restore: bool = True
    save: bool = True


class ArtifactSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    paths: list[str]
    retention_days: int | None = Field(default=None, ge=1)


class ResourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu: float | None = Field(default=None, ge=0)
    memory_mb: int | None = Field(default=None, ge=0)
    timeout_seconds: int | None = Field(default=None, ge=1)


class TaskSpec(BaseModel):
    """First-class typed task/step.

    Commands are argv lists and never shell strings. Shell-specific renderers may render these
    later, but the control plane validates risk before execution.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    name: str
    category: TaskCategory
    runner: str | None = None
    image: str | None = None
    command: list[str] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    secrets: list[SecretReference] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactSpec] = Field(default_factory=list)
    cache: list[CacheSpec] = Field(default_factory=list)
    resources: ResourceSpec = Field(default_factory=ResourceSpec)
    timeout_seconds: int = Field(default=600, ge=1, le=86_400)
    retries: int = Field(default=0, ge=0, le=5)
    conditions: list[str] = Field(default_factory=list)
    security_context: dict[str, Any] = Field(default_factory=dict)
    failure_strategy: str = "fail_fast"
    risk: RiskLevel = RiskLevel.SAFE
    required_capabilities: RunnerCapabilityRequest = Field(default_factory=RunnerCapabilityRequest)
    depends_on: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    idempotency_key: str | None = None

    @field_validator("id")
    @classmethod
    def id_must_be_safe(cls, value: str) -> str:
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
        if not value or any(char not in allowed for char in value):
            raise ValueError("task id must be non-empty and contain only alphanumeric, _, -, .")
        return value

    @model_validator(mode="after")
    def protect_environment_secrets(self) -> "TaskSpec":
        secret_markers = ("password", "token", "secret", "key", "credential")
        for key, value in self.environment.items():
            lowered = key.lower()
            if any(marker in lowered for marker in secret_markers) and not value.startswith("secret://"):
                raise ValueError(
                    f"environment variable {key!r} appears secret-like; use SecretReference/secret://"
                )
        if self.risk in {RiskLevel.HIGH_RISK, RiskLevel.DESTRUCTIVE} and not self.side_effects:
            raise ValueError("high-risk/destructive tasks must declare side_effects")
        return self
