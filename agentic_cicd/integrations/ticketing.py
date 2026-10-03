"""Ticketing connector contracts."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.integrations.base import IntegrationCapability, IntegrationStatus


class TicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    labels: list[str] = Field(default_factory=list)
    severity: str | None = None


class TicketResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: bool
    id: str | None = None
    url: str | None = None
    message: str


class TicketingConnector(Protocol):
    id: str
    provider: str

    def create_ticket(self, request: TicketRequest, *, dry_run: bool = True) -> TicketResult:
        ...

    def status(self) -> IntegrationStatus:
        ...


class DryRunTicketingConnector:
    id = "dry-run-ticketing"
    provider = "generic_ticketing"

    def create_ticket(self, request: TicketRequest, *, dry_run: bool = True) -> TicketResult:
        if not dry_run:
            return TicketResult(created=False, message="NOT_IMPLEMENTED: real ticketing connector not configured")
        return TicketResult(created=False, id="dry-run", message=f"DRY RUN: would create ticket {request.title!r}")

    def status(self) -> IntegrationStatus:
        return IntegrationStatus(
            id=self.id,
            provider=self.provider,
            implemented=True,
            configured=True,
            healthy=True,
            capabilities=[IntegrationCapability(name="create_ticket_dry_run", read_only=False, mutates_external_state=False)],
        )
