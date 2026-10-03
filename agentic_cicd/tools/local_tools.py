"""Concrete local typed tools."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from agentic_cicd.core.enums import Permission, RiskLevel
from agentic_cicd.tools.base import ToolDefinition, ToolInvocation, ToolResult, TypedTool
from agentic_cicd.tools.sbom import generate_sbom
from agentic_cicd.tools.secret_scan import scan


class SecretScanTool(TypedTool):
    definition = ToolDefinition(
        name="secret_scan",
        description="Scan repository files for secret-like patterns without printing secret values.",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        output_schema={"type": "object", "properties": {"findings": {"type": "array"}}},
        permission_requirements={Permission.EXECUTE_CI},
        risk_level=RiskLevel.SAFE,
    )

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        started = datetime.now(UTC)
        findings = [finding.as_dict() for finding in scan(str(invocation.inputs.get("path", ".")))]
        return ToolResult(
            invocation_id=invocation.id,
            tool_name=self.definition.name,
            success=not findings,
            outputs={"findings": findings},
            started_at=started,
            finished_at=datetime.now(UTC),
        )


class SbomTool(TypedTool):
    definition = ToolDefinition(
        name="generate_sbom",
        description="Generate a lightweight local dependency inventory/SBOM.",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        output_schema={"type": "object", "properties": {"components": {"type": "array"}}},
        permission_requirements={Permission.EXECUTE_CI},
        risk_level=RiskLevel.SAFE,
    )

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        started = datetime.now(UTC)
        sbom = generate_sbom(str(invocation.inputs.get("path", ".")))
        return ToolResult(
            invocation_id=invocation.id,
            tool_name=self.definition.name,
            success=True,
            outputs=sbom.model_dump(mode="json"),
            started_at=started,
            finished_at=datetime.now(UTC),
        )


class GitDiffTool(TypedTool):
    definition = ToolDefinition(
        name="git_diff",
        description="Return changed files using git diff --name-only without mutating the repository.",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        output_schema={"type": "object", "properties": {"changed_files": {"type": "array"}}},
        permission_requirements={Permission.READ_REPOSITORY},
        risk_level=RiskLevel.SAFE,
    )

    def invoke(self, invocation: ToolInvocation) -> ToolResult:
        started = datetime.now(UTC)
        path = Path(str(invocation.inputs.get("path", "."))).expanduser().resolve()
        if not (path / ".git").exists():
            return ToolResult(
                invocation_id=invocation.id,
                tool_name=self.definition.name,
                success=True,
                outputs={"changed_files": [], "note": "path is not a git repository"},
                started_at=started,
                finished_at=datetime.now(UTC),
            )
        completed = subprocess.run(  # noqa: S603 - controlled argv, shell=False
            ["git", "diff", "--name-only", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            shell=False,
            timeout=10,
            check=False,
        )
        return ToolResult(
            invocation_id=invocation.id,
            tool_name=self.definition.name,
            success=completed.returncode == 0,
            outputs={"changed_files": [line for line in completed.stdout.splitlines() if line.strip()]},
            error=None if completed.returncode == 0 else {"stderr": completed.stderr, "exit_code": completed.returncode},
            started_at=started,
            finished_at=datetime.now(UTC),
        )
