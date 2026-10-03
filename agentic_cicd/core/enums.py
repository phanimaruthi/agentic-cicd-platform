"""Shared enumerations used by typed control-plane models."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """Backport-friendly string enum base."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class TrustLevel(StrEnum):
    SYSTEM = "system"
    TRUSTED_CONFIG = "trusted_config"
    ORGANIZATION = "organization"
    REPOSITORY = "repository_untrusted"
    USER = "user"
    EXTERNAL = "external_untrusted"


class RiskLevel(StrEnum):
    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    DESTRUCTIVE = "DESTRUCTIVE"


RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.SAFE: 0,
    RiskLevel.LOW_RISK: 1,
    RiskLevel.MEDIUM_RISK: 2,
    RiskLevel.HIGH_RISK: 3,
    RiskLevel.DESTRUCTIVE: 4,
}


class PolicyDecisionType(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    WARN = "WARN"


class AutonomyLevel(StrEnum):
    DETERMINISTIC = "LEVEL_1_DETERMINISTIC"
    HUMAN_IN_THE_LOOP = "LEVEL_2_HUMAN_IN_THE_LOOP"
    POLICY_BOUNDED_AUTONOMOUS = "LEVEL_3_POLICY_BOUNDED_AUTONOMOUS"


class IntentAction(StrEnum):
    ANALYZE_REPOSITORY = "analyze_repository"
    GENERATE_PIPELINE = "generate_pipeline"
    BUILD_AND_TEST = "build_and_test"
    BUILD_IMAGE = "build_image"
    SECURITY_CHECKS = "security_checks"
    DEPLOY = "deploy"
    PREPARE_DEPLOYMENT = "prepare_deployment"
    ROLLBACK = "rollback"
    DIAGNOSE = "diagnose"
    REMEDIATE = "remediate"
    IMPACT_ANALYSIS = "impact_analysis"
    UNKNOWN = "unknown"


class TaskCategory(StrEnum):
    SOURCE = "source"
    BUILD = "build"
    TEST = "test"
    SECURITY = "security"
    INFRASTRUCTURE = "infrastructure"
    KUBERNETES = "kubernetes"
    DATABASE = "database"
    DEPLOYMENT = "deployment"
    OPERATIONAL = "operational"
    APPROVAL = "approval"


class ExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    SKIPPED = "SKIPPED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DENIED = "DENIED"


class WorkflowState(StrEnum):
    RECEIVED = "RECEIVED"
    CLASSIFIED = "CLASSIFIED"
    DISCOVERING = "DISCOVERING"
    CONTEXT_READY = "CONTEXT_READY"
    PLANNING = "PLANNING"
    POLICY_CHECK = "POLICY_CHECK"
    PLAN_READY = "PLAN_READY"
    VALIDATING = "VALIDATING"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    REMEDIATING = "REMEDIATING"
    REEXECUTING = "REEXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DIAGNOSING = "DIAGNOSING"
    REMEDIATION_PLANNED = "REMEDIATION_PLANNED"


class FailureCategory(StrEnum):
    SYNTAX = "syntax"
    DEPENDENCY = "dependency"
    COMPILATION = "compilation"
    TEST = "test"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    SECRET = "secret"
    INFRASTRUCTURE = "infrastructure"
    CONTAINER = "container"
    KUBERNETES = "kubernetes"
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"
    POLICY = "policy"
    SECURITY = "security"
    FLAKY_TRANSIENT = "flaky_transient"
    CAPACITY = "capacity"
    TIMEOUT = "timeout"
    EXTERNAL_SERVICE = "external_service"
    UNKNOWN = "unknown"


class Permission(StrEnum):
    READ_REPOSITORY = "read_repository"
    WRITE_REPOSITORY = "write_repository"
    EXECUTE_CI = "execute_ci"
    EXECUTE_CD = "execute_cd"
    DEPLOY_DEVELOPMENT = "deploy_development"
    DEPLOY_STAGING = "deploy_staging"
    DEPLOY_PRODUCTION = "deploy_production"
    READ_SECRETS_METADATA = "read_secrets_metadata"
    ACCESS_SECRET = "access_secret"
    MODIFY_POLICIES = "modify_policies"
    CHANGE_RUNNER_CONFIGURATION = "change_runner_configuration"
    MODIFY_INFRASTRUCTURE = "modify_infrastructure"
    ROLLBACK = "rollback"
    CREATE_AGENTS = "create_agents"
    MODIFY_AGENT_PERMISSIONS = "modify_agent_permissions"
    APPROVE_PRODUCTION = "approve_production"


class Role(StrEnum):
    VIEWER = "Viewer"
    DEVELOPER = "Developer"
    MAINTAINER = "Maintainer"
    RELEASE_ENGINEER = "ReleaseEngineer"
    PLATFORM_ENGINEER = "PlatformEngineer"
    SECURITY_ENGINEER = "SecurityEngineer"
    ADMIN = "Admin"


class RunnerKind(StrEnum):
    LOCAL_SHELL = "local_shell"
    MOCK = "mock"
    CONTAINER = "container"
    DOCKER = "docker"
    KUBERNETES_JOB = "kubernetes_job"
    VM = "vm"
    SSH = "ssh"
    WINDOWS = "windows"
    GITHUB_ACTIONS = "github_actions"
    GITLAB = "gitlab"
    JENKINS = "jenkins"
    CLOUD_CLI = "cloud_cli"
    TERRAFORM = "terraform"
    KUBERNETES = "kubernetes"
    HELM = "helm"
    TEST = "test"
    SECURITY_SCANNER = "security_scanner"
    ARTIFACT = "artifact"
    DATABASE_MIGRATION = "database_migration"
    OBSERVABILITY = "observability"
    HTTP_API = "http_api"


class PipelineBackend(StrEnum):
    NATIVE = "native"
    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    JENKINS = "jenkins"
