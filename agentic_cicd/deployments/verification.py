"""Deployment health verification using typed observability signals."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.observability.providers import ObservabilityProvider


class HealthThreshold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    operator: Literal["<=", ">=", "<", ">", "=="]
    value: float


class DeploymentVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    environment: str
    deployment_id: str | None = None
    thresholds: list[HealthThreshold] = Field(
        default_factory=lambda: [
            HealthThreshold(metric="error_rate", operator="<=", value=0.01),
            HealthThreshold(metric="p95_latency_ms", operator="<=", value=500.0),
        ]
    )
    required_log_queries: list[str] = Field(default_factory=list)


class VerificationCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    observed: float | str | None = None
    expected: str
    details: dict[str, object] = Field(default_factory=dict)


class DeploymentVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    environment: str
    verified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    passed: bool
    checks: list[VerificationCheckResult] = Field(default_factory=list)
    rollback_recommended: bool = False


def _compare(left: float, operator: str, right: float) -> bool:
    if operator == "<=":
        return left <= right
    if operator == ">=":
        return left >= right
    if operator == "<":
        return left < right
    if operator == ">":
        return left > right
    if operator == "==":
        return left == right
    return False


class DeploymentVerifier:
    def __init__(self, provider: ObservabilityProvider) -> None:
        self.provider = provider

    def verify(self, request: DeploymentVerificationRequest) -> DeploymentVerificationResult:
        checks: list[VerificationCheckResult] = []
        for threshold in request.thresholds:
            sample = self.provider.query_metric(
                threshold.metric,
                labels={"service": request.service, "environment": request.environment},
            )
            if sample is None:
                checks.append(
                    VerificationCheckResult(
                        name=threshold.metric,
                        passed=False,
                        observed=None,
                        expected=f"metric must exist and be {threshold.operator} {threshold.value}",
                        details={"reason": "metric unavailable"},
                    )
                )
                continue
            checks.append(
                VerificationCheckResult(
                    name=threshold.metric,
                    passed=_compare(sample.value, threshold.operator, threshold.value),
                    observed=sample.value,
                    expected=f"{threshold.operator} {threshold.value}",
                    details={"unit": sample.unit},
                )
            )
        for query in request.required_log_queries:
            logs = self.provider.query_logs(query, limit=10)
            checks.append(
                VerificationCheckResult(
                    name=f"logs:{query}",
                    passed=not logs.lines,
                    observed=f"{len(logs.lines)} matching log lines",
                    expected="0 error log matches",
                    details={"truncated": logs.truncated},
                )
            )
        passed = all(check.passed for check in checks)
        return DeploymentVerificationResult(
            service=request.service,
            environment=request.environment,
            passed=passed,
            checks=checks,
            rollback_recommended=not passed,
        )
