"""Default integration registry."""

from __future__ import annotations

from agentic_cicd.integrations.base import IntegrationRegistry
from agentic_cicd.integrations.github import GitHubClient
from agentic_cicd.integrations.notifications import DryRunNotificationConnector
from agentic_cicd.integrations.scm import LocalGitConnector, NotImplementedSCMConnector
from agentic_cicd.integrations.ticketing import DryRunTicketingConnector


def default_integration_registry() -> IntegrationRegistry:
    registry = IntegrationRegistry()
    registry.register(LocalGitConnector())
    registry.register(GitHubClient())
    registry.register(NotImplementedSCMConnector("github"))
    registry.register(NotImplementedSCMConnector("gitlab"))
    registry.register(NotImplementedSCMConnector("bitbucket"))
    registry.register(DryRunTicketingConnector())
    registry.register(DryRunNotificationConnector())
    return registry
