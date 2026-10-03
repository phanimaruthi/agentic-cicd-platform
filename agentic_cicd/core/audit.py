"""Audit events and sinks with secret masking."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

SECRET_PATTERN = re.compile(r"(?i)(password|token|secret|api[_-]?key|authorization|credential)")


def mask_secret_value(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, nested in value.items():
            masked[key] = "***MASKED***" if SECRET_PATTERN.search(str(key)) else mask_secret_value(nested)
        return masked
    if isinstance(value, list):
        return [mask_secret_value(item) for item in value]
    if isinstance(value, str) and value.startswith("secret://"):
        return value
    return value


def hash_inputs(data: Any) -> str:
    normalized = json.dumps(mask_secret_value(data), sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    actor: str
    actor_type: str
    action: str
    resource: str | None = None
    environment: str | None = None
    authorization: str | None = None
    policy_decision: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    inputs_hash: str | None = None
    tool: str | None = None
    runner: str | None = None
    result: str | None = None
    related_execution: str | None = None
    related_commit: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class AuditSink(Protocol):
    def emit(self, event: AuditEvent) -> str:
        ...


class InMemoryAuditSink:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> str:
        self.events.append(event)
        return event.id


class JsonlAuditSink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: AuditEvent) -> str:
        safe_event = event.model_copy(update={"context": mask_secret_value(event.context)})
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(safe_event.model_dump_json() + "\n")
        return event.id
