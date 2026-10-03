"""Security scan result models and lightweight aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SecurityFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    scanner: str
    severity: str
    category: str
    title: str
    resource: str
    description: str | None = None
    remediation: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecurityScanReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanner: str
    target: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    findings: list[SecurityFinding] = Field(default_factory=list)
    passed: bool = True
    limitations: list[str] = Field(default_factory=list)

    def recompute_status(self, deny_severities: set[str] | None = None) -> None:
        deny = {severity.upper() for severity in (deny_severities or {"CRITICAL", "HIGH"})}
        self.passed = not any(finding.severity.upper() in deny for finding in self.findings)


class SecurityReportAggregator:
    def aggregate(self, reports: list[SecurityScanReport]) -> SecurityScanReport:
        findings: list[SecurityFinding] = []
        limitations: list[str] = []
        target = reports[0].target if reports else "unknown"
        for report in reports:
            findings.extend(report.findings)
            limitations.extend(report.limitations)
        aggregate = SecurityScanReport(
            scanner="aggregate",
            target=target,
            findings=findings,
            limitations=sorted(set(limitations)),
        )
        aggregate.recompute_status()
        return aggregate
