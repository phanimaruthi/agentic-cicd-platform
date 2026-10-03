"""Runner profile catalog.

Profiles describe runner capabilities independent of a concrete adapter. They help
planning/UI explain which environments can satisfy language/tool requirements.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.task import RunnerCapabilityRequest
from agentic_cicd.runners.base import RunnerCapabilities


class RunnerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    capabilities: RunnerCapabilities
    labels: dict[str, str] = Field(default_factory=dict)

    def satisfies(self, request: RunnerCapabilityRequest) -> bool:
        return self.capabilities.satisfies(request)


class RunnerProfileCatalog:
    def __init__(self, profiles: list[RunnerProfile] | None = None) -> None:
        self.profiles = profiles or default_runner_profiles()

    def list(self) -> list[RunnerProfile]:
        return self.profiles

    def matching(self, request: RunnerCapabilityRequest) -> list[RunnerProfile]:
        return [profile for profile in self.profiles if profile.satisfies(request)]

    def explain_for_tasks(self, tasks: list) -> dict[str, list[str]]:
        explanation: dict[str, list[str]] = {}
        for task in tasks:
            explanation[task.id] = [profile.id for profile in self.matching(task.required_capabilities)]
        return explanation


def default_runner_profiles() -> list[RunnerProfile]:
    return [
        RunnerProfile(
            id="local-python",
            name="Local Python Runner",
            description="Local sandbox runner with Python tooling for repository discovery and Python CI.",
            capabilities=RunnerCapabilities(
                tools={"python", "pytest", "git", "agentic-cicd-internal"},
                network_access=False,
                memory_mb=512,
                cpu=1.0,
                security_level="sandbox",
            ),
            labels={"runner": "local", "language": "python"},
        ),
        RunnerProfile(
            id="github-ubuntu-polyglot",
            name="GitHub Ubuntu Polyglot Runner",
            description="Conceptual GitHub-hosted runner with common Python/Node/Go/Java/Docker tools.",
            capabilities=RunnerCapabilities(
                tools={"python", "pytest", "git", "npm", "node", "go", "mvn", "docker", "agentic-cicd-internal"},
                network_access=True,
                docker=True,
                memory_mb=7168,
                cpu=2.0,
                security_level="hosted-ci",
                timeout_limit_seconds=21_600,
                concurrency=20,
            ),
            labels={"runner": "github", "os": "ubuntu"},
        ),
        RunnerProfile(
            id="kubernetes-build-runner",
            name="Kubernetes Build Runner",
            description="Conceptual Kubernetes job runner for containerized builds.",
            capabilities=RunnerCapabilities(
                tools={"python", "git", "docker", "kubectl", "helm", "agentic-cicd-internal"},
                network_access=True,
                docker=True,
                kubernetes=True,
                memory_mb=4096,
                cpu=2.0,
                security_level="cluster-build",
                timeout_limit_seconds=7200,
                concurrency=10,
            ),
            labels={"runner": "kubernetes", "workload": "job"},
        ),
    ]
