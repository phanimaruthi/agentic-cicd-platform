"""RBAC identities, roles, and authorization boundaries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.enums import Permission, Role
from agentic_cicd.core.errors import AuthorizationError

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VIEWER: {Permission.READ_REPOSITORY},
    Role.DEVELOPER: {
        Permission.READ_REPOSITORY,
        Permission.WRITE_REPOSITORY,
        Permission.EXECUTE_CI,
        Permission.DEPLOY_DEVELOPMENT,
    },
    Role.MAINTAINER: {
        Permission.READ_REPOSITORY,
        Permission.WRITE_REPOSITORY,
        Permission.EXECUTE_CI,
        Permission.EXECUTE_CD,
        Permission.DEPLOY_DEVELOPMENT,
        Permission.DEPLOY_STAGING,
        Permission.ROLLBACK,
        Permission.READ_SECRETS_METADATA,
    },
    Role.RELEASE_ENGINEER: {
        Permission.READ_REPOSITORY,
        Permission.EXECUTE_CI,
        Permission.EXECUTE_CD,
        Permission.DEPLOY_DEVELOPMENT,
        Permission.DEPLOY_STAGING,
        Permission.DEPLOY_PRODUCTION,
        Permission.APPROVE_PRODUCTION,
        Permission.ROLLBACK,
        Permission.READ_SECRETS_METADATA,
    },
    Role.PLATFORM_ENGINEER: {
        Permission.READ_REPOSITORY,
        Permission.WRITE_REPOSITORY,
        Permission.EXECUTE_CI,
        Permission.EXECUTE_CD,
        Permission.DEPLOY_DEVELOPMENT,
        Permission.DEPLOY_STAGING,
        Permission.MODIFY_INFRASTRUCTURE,
        Permission.CHANGE_RUNNER_CONFIGURATION,
        Permission.ROLLBACK,
        Permission.READ_SECRETS_METADATA,
    },
    Role.SECURITY_ENGINEER: {
        Permission.READ_REPOSITORY,
        Permission.EXECUTE_CI,
        Permission.READ_SECRETS_METADATA,
        Permission.MODIFY_POLICIES,
    },
    Role.ADMIN: set(Permission),
}


class Principal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    roles: set[Role] = Field(default_factory=lambda: {Role.VIEWER})
    team: str | None = None
    explicit_permissions: set[Permission] = Field(default_factory=set)

    @property
    def permissions(self) -> set[Permission]:
        computed: set[Permission] = set(self.explicit_permissions)
        for role in self.roles:
            computed.update(ROLE_PERMISSIONS.get(role, set()))
        return computed


class AgentIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = "agentic-cicd-control-plane"
    version: str = "0.1.0"
    model: str | None = None
    owner: str = "platform"
    enabled: bool = True
    permissions: set[Permission] = Field(default_factory=lambda: set(Permission))
    tools: set[str] = Field(default_factory=set)
    environment: str = "local"
    status: str = "active"
    heartbeat_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_action: str | None = None
    current_execution: str | None = None


class AuthorizationService:
    """Ensures the agent never exceeds the initiating principal's permissions."""

    def __init__(self, agent_identity: AgentIdentity | None = None) -> None:
        self.agent_identity = agent_identity or AgentIdentity()

    def effective_permissions(self, principal: Principal) -> set[Permission]:
        return principal.permissions.intersection(self.agent_identity.permissions)

    def has_permission(self, principal: Principal, permission: Permission) -> bool:
        return permission in self.effective_permissions(principal)

    def require(self, principal: Principal, permission: Permission, resource: str | None = None) -> None:
        if not self.has_permission(principal, permission):
            raise AuthorizationError(
                f"Principal {principal.id!r} lacks permission {permission.value!r}",
                metadata={"principal": principal.id, "permission": permission.value, "resource": resource},
            )

    def require_any(
        self, principal: Principal, permissions: Iterable[Permission], resource: str | None = None
    ) -> None:
        if not any(self.has_permission(principal, permission) for permission in permissions):
            raise AuthorizationError(
                f"Principal {principal.id!r} lacks all required permissions",
                metadata={
                    "principal": principal.id,
                    "permissions": [permission.value for permission in permissions],
                    "resource": resource,
                },
            )
