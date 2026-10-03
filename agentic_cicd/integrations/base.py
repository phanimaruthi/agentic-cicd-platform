"""Common integration metadata and registry."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class IntegrationCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    read_only: bool = True
    mutates_external_state: bool = False
    requires_credentials: bool = False


class IntegrationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    implemented: bool
    configured: bool
    healthy: bool
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    capabilities: list[IntegrationCapability] = Field(default_factory=list)
    message: str | None = None


class Integration(Protocol):
    id: str
    provider: str

    def status(self) -> IntegrationStatus:
        ...


class IntegrationRegistry:
    def __init__(self) -> None:
        self._integrations: dict[str, Integration] = {}

    def register(self, integration: Integration) -> None:
        self._integrations[integration.id] = integration

    def list(self) -> list[IntegrationStatus]:
        return [integration.status() for integration in self._integrations.values()]

    def get(self, integration_id: str) -> Integration:
        return self._integrations[integration_id]
