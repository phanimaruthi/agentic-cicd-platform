"""Inventory of active agents and kill-switch controls."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import Permission
from agentic_cicd.core.errors import AuthorizationError
from agentic_cicd.core.identity import AgentIdentity


class AgentInventoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: AgentIdentity
    rate_limit_per_minute: int = Field(default=60, ge=0)
    disabled_reason: str | None = None
    resource_usage: dict[str, float] = Field(default_factory=dict)


class AgentInventory:
    def __init__(self) -> None:
        self._records: dict[str, AgentInventoryRecord] = {}
        self.kill_switch_enabled = False

    def register(self, identity: AgentIdentity, *, rate_limit_per_minute: int = 60) -> None:
        self._records[identity.id] = AgentInventoryRecord(
            identity=identity, rate_limit_per_minute=rate_limit_per_minute
        )

    def get(self, agent_id: str) -> AgentInventoryRecord | None:
        return self._records.get(agent_id)

    def list(self) -> list[AgentInventoryRecord]:
        return list(self._records.values())

    def heartbeat(self, agent_id: str, *, current_execution: str | None = None) -> None:
        record = self._require(agent_id)
        record.identity.heartbeat_at = datetime.now(UTC)
        record.identity.current_execution = current_execution
        record.identity.status = "active" if record.identity.enabled else "disabled"

    def disable(self, agent_id: str, reason: str) -> None:
        record = self._require(agent_id)
        record.identity.enabled = False
        record.identity.status = "disabled"
        record.disabled_reason = reason

    def enable(self, agent_id: str) -> None:
        if self.kill_switch_enabled:
            raise AuthorizationError("global kill switch is enabled; cannot enable agent")
        record = self._require(agent_id)
        record.identity.enabled = True
        record.identity.status = "active"
        record.disabled_reason = None

    def revoke_tool(self, agent_id: str, tool: str) -> None:
        record = self._require(agent_id)
        record.identity.tools.discard(tool)

    def revoke_permission(self, agent_id: str, permission: Permission) -> None:
        record = self._require(agent_id)
        record.identity.permissions.discard(permission)

    def set_kill_switch(self, enabled: bool, reason: str = "global operator control") -> None:
        self.kill_switch_enabled = enabled
        if enabled:
            for record in self._records.values():
                record.identity.enabled = False
                record.identity.status = "disabled"
                record.disabled_reason = reason

    def assert_agent_enabled(self, agent_id: str) -> None:
        record = self._require(agent_id)
        if self.kill_switch_enabled:
            raise AuthorizationError("global agent kill switch is enabled", metadata={"agent_id": agent_id})
        if not record.identity.enabled:
            raise AuthorizationError(
                "agent is disabled",
                metadata={"agent_id": agent_id, "reason": record.disabled_reason},
            )

    def _require(self, agent_id: str) -> AgentInventoryRecord:
        record = self._records.get(agent_id)
        if record is None:
            raise AuthorizationError("agent is not registered", metadata={"agent_id": agent_id})
        return record
