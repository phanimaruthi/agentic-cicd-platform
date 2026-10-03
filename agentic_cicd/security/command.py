"""Deterministic command risk classification and validation."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field

from agentic_cicd.core.enums import RISK_ORDER, RiskLevel
from agentic_cicd.core.errors import PolicyDeniedError


@dataclass(frozen=True)
class CommandAssessment:
    command: list[str]
    risk: RiskLevel
    reasons: list[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        return shlex.join(self.command)


SAFE_BINARIES = {
    "git",
    "python",
    "python3",
    "pytest",
    "ruff",
    "mypy",
    "npm",
    "node",
    "go",
    "java",
    "mvn",
    "gradle",
    "grep",
    "find",
    "ls",
    "cat",
    "echo",
}

SHELL_CONTROL_TOKENS = {";", "&&", "||", "|", "`", "$(", ">", ">>", "<"}


def _contains_control_token(token: str) -> bool:
    return any(control in token for control in SHELL_CONTROL_TOKENS)


def classify_command(command: list[str]) -> CommandAssessment:
    if not command:
        return CommandAssessment(command=command, risk=RiskLevel.SAFE, reasons=["no command"])

    lowered = [part.lower() for part in command]
    binary = lowered[0]
    reasons: list[str] = []
    risk = RiskLevel.SAFE

    if any(_contains_control_token(part) for part in command):
        risk = RiskLevel.MEDIUM_RISK
        reasons.append("contains shell control characters; argv execution prevents shell expansion")

    if binary in {"rm", "shred"} and any(part in {"-rf", "-fr", "/", "/*"} for part in lowered[1:]):
        risk = RiskLevel.DESTRUCTIVE
        reasons.append("recursive or root deletion command")
    elif binary in {"terraform", "tofu", "opentofu"}:
        if "destroy" in lowered:
            risk = RiskLevel.DESTRUCTIVE
            reasons.append("terraform/opentofu destroy")
        elif "apply" in lowered:
            risk = max_risk(risk, RiskLevel.HIGH_RISK)
            reasons.append("terraform/opentofu apply mutates infrastructure")
        elif "plan" in lowered:
            risk = max_risk(risk, RiskLevel.MEDIUM_RISK)
            reasons.append("terraform/opentofu plan can expose infrastructure metadata")
    elif binary == "kubectl":
        if any(word in lowered for word in ("delete", "drain", "cordon", "uncordon", "scale", "patch", "apply")):
            risk = max_risk(risk, RiskLevel.HIGH_RISK)
            reasons.append("kubectl mutation")
        else:
            risk = max_risk(risk, RiskLevel.SAFE)
    elif binary == "helm":
        if any(word in lowered for word in ("upgrade", "install", "rollback", "uninstall")):
            risk = max_risk(risk, RiskLevel.HIGH_RISK)
            reasons.append("helm release mutation")
        elif any(word in lowered for word in ("template", "lint")):
            risk = max_risk(risk, RiskLevel.SAFE)
    elif binary == "docker":
        if any(word in lowered for word in ("push", "login", "run")):
            risk = max_risk(risk, RiskLevel.MEDIUM_RISK)
            reasons.append("docker command with registry/runtime side effects")
        elif "build" in lowered:
            risk = max_risk(risk, RiskLevel.MEDIUM_RISK)
            reasons.append("docker build executes untrusted build context")
    elif binary in {"aws", "az", "gcloud"}:
        if any(word in lowered for word in ("delete", "terminate", "destroy", "remove")):
            risk = RiskLevel.DESTRUCTIVE
            reasons.append("cloud delete/destroy operation")
        elif any(word in lowered for word in ("create", "update", "put", "apply", "deploy")):
            risk = max_risk(risk, RiskLevel.HIGH_RISK)
            reasons.append("cloud mutation")
        else:
            risk = max_risk(risk, RiskLevel.MEDIUM_RISK)
            reasons.append("cloud read may expose sensitive metadata")
    elif binary in {"psql", "mysql", "mongosh"}:
        joined = " ".join(lowered)
        if "drop database" in joined or "drop table" in joined or "truncate" in joined:
            risk = RiskLevel.DESTRUCTIVE
            reasons.append("database destructive statement")
        else:
            risk = max_risk(risk, RiskLevel.MEDIUM_RISK)
            reasons.append("database command")
    elif binary not in SAFE_BINARIES:
        risk = max_risk(risk, RiskLevel.LOW_RISK)
        reasons.append("unknown binary; requires runner/tool policy")

    if not reasons:
        reasons.append("recognized safe/low-impact command")

    return CommandAssessment(command=command, risk=risk, reasons=reasons)


def max_risk(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    return left if RISK_ORDER[left] >= RISK_ORDER[right] else right


def assert_command_allowed(command: list[str], maximum: RiskLevel) -> CommandAssessment:
    assessment = classify_command(command)
    if RISK_ORDER[assessment.risk] > RISK_ORDER[maximum]:
        raise PolicyDeniedError(
            "command risk exceeds allowed runner threshold",
            metadata={
                "command": assessment.display,
                "risk": assessment.risk.value,
                "maximum": maximum.value,
                "reasons": assessment.reasons,
            },
        )
    return assessment
