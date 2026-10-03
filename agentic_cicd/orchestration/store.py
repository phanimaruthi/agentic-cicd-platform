"""Execution persistence interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from agentic_cicd.core.execution import ExecutionRecord


class ExecutionStore(Protocol):
    def save(self, record: ExecutionRecord) -> None:
        ...

    def get(self, execution_id: str) -> ExecutionRecord | None:
        ...

    def list(self) -> list[ExecutionRecord]:
        ...


class InMemoryExecutionStore:
    def __init__(self) -> None:
        self._records: dict[str, ExecutionRecord] = {}

    def save(self, record: ExecutionRecord) -> None:
        self._records[record.id] = record

    def get(self, execution_id: str) -> ExecutionRecord | None:
        return self._records.get(execution_id)

    def list(self) -> list[ExecutionRecord]:
        return list(self._records.values())


class JsonExecutionStore:
    def __init__(self, directory: str | Path = "logs/executions") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, record: ExecutionRecord) -> None:
        (self.directory / f"{record.id}.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")

    def get(self, execution_id: str) -> ExecutionRecord | None:
        path = self.directory / f"{execution_id}.json"
        if not path.exists():
            return None
        return ExecutionRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[ExecutionRecord]:
        return [ExecutionRecord.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(self.directory.glob("*.json"))]
