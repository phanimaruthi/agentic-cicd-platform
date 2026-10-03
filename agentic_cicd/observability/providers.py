"""Observability provider interfaces and deterministic mock provider."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class MetricSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    labels: dict[str, str] = Field(default_factory=dict)


class LogQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    lines: list[str] = Field(default_factory=list)
    truncated: bool = False


class TraceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    p95_latency_ms: float | None = None
    error_rate: float | None = None
    sample_count: int = 0


class ObservabilityProvider(Protocol):
    def query_metric(self, name: str, labels: dict[str, str] | None = None) -> MetricSample | None:
        ...

    def query_logs(self, query: str, limit: int = 100) -> LogQueryResult:
        ...

    def query_trace_summary(self, service: str) -> TraceSummary:
        ...


class MockObservabilityProvider:
    def __init__(self, metrics: dict[str, float] | None = None, logs: list[str] | None = None) -> None:
        self.metrics = metrics or {"error_rate": 0.0, "p95_latency_ms": 100.0, "availability": 1.0}
        self.logs = logs or []

    def query_metric(self, name: str, labels: dict[str, str] | None = None) -> MetricSample | None:
        if name not in self.metrics:
            return None
        unit = "%" if "rate" in name or name == "availability" else "ms"
        return MetricSample(name=name, value=self.metrics[name], unit=unit, labels=labels or {})

    def query_logs(self, query: str, limit: int = 100) -> LogQueryResult:
        matched = [line for line in self.logs if query.lower() in line.lower()]
        return LogQueryResult(query=query, lines=matched[:limit], truncated=len(matched) > limit)

    def query_trace_summary(self, service: str) -> TraceSummary:
        return TraceSummary(
            service=service,
            p95_latency_ms=self.metrics.get("p95_latency_ms"),
            error_rate=self.metrics.get("error_rate"),
            sample_count=1,
        )
