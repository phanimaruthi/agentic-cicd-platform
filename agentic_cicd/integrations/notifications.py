"""Communication/notification connector contracts."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.integrations.base import IntegrationCapability, IntegrationStatus


class NotificationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str
    subject: str
    body: str
    severity: str = "info"
    metadata: dict[str, str] = Field(default_factory=dict)


class NotificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sent: bool
    message: str


class NotificationConnector(Protocol):
    id: str
    provider: str

    def send(self, message: NotificationMessage, *, dry_run: bool = True) -> NotificationResult:
        ...

    def status(self) -> IntegrationStatus:
        ...


class DryRunNotificationConnector:
    id = "dry-run-notifications"
    provider = "generic_notifications"

    def send(self, message: NotificationMessage, *, dry_run: bool = True) -> NotificationResult:
        if not dry_run:
            return NotificationResult(sent=False, message="NOT_IMPLEMENTED: real notification connector not configured")
        return NotificationResult(sent=False, message=f"DRY RUN: would notify {message.channel}: {message.subject}")

    def status(self) -> IntegrationStatus:
        return IntegrationStatus(
            id=self.id,
            provider=self.provider,
            implemented=True,
            configured=True,
            healthy=True,
            capabilities=[IntegrationCapability(name="notify_dry_run", read_only=False, mutates_external_state=False)],
        )
