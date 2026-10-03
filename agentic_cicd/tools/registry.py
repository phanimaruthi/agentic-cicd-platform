"""Tool registry for local tools and future MCP/tool adapters."""

from __future__ import annotations

from agentic_cicd.core.enums import Permission
from agentic_cicd.core.errors import AuthorizationError, RunnerUnavailableError
from agentic_cicd.core.identity import AuthorizationService, Principal
from agentic_cicd.tools.base import ToolDefinition, ToolInvocation, ToolResult, TypedTool


class ToolRegistry:
    def __init__(self, authz: AuthorizationService | None = None) -> None:
        self._tools: dict[str, TypedTool] = {}
        self.authz = authz or AuthorizationService()

    def register(self, tool: TypedTool) -> None:
        self._tools[tool.definition.name] = tool

    def definitions(self) -> list[ToolDefinition]:
        return [tool.definition for tool in self._tools.values()]

    def get(self, name: str) -> TypedTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise RunnerUnavailableError("tool is not registered", metadata={"tool": name}) from exc

    def invoke(self, name: str, inputs: dict[str, object], principal: Principal, *, dry_run: bool = True) -> ToolResult:
        tool = self.get(name)
        for permission in tool.definition.permission_requirements:
            if permission not in self.authz.effective_permissions(principal):
                raise AuthorizationError(
                    "principal lacks tool permission",
                    metadata={"principal": principal.id, "tool": name, "permission": permission.value},
                )
        return tool.invoke(ToolInvocation(tool_name=name, inputs=inputs, actor=principal.id, dry_run=dry_run))


def default_tool_registry() -> ToolRegistry:
    from agentic_cicd.tools.local_tools import GitDiffTool, SecretScanTool, SbomTool

    registry = ToolRegistry()
    registry.register(SecretScanTool())
    registry.register(SbomTool())
    registry.register(GitDiffTool())
    return registry
