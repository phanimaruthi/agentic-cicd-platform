from __future__ import annotations

import pytest
from pydantic import BaseModel

from agentic_cicd.agents.inventory import AgentInventory
from agentic_cicd.core.enums import Permission
from agentic_cicd.core.identity import AgentIdentity
from agentic_cicd.integrations.registry import default_integration_registry
from agentic_cicd.integrations.scm import LocalGitConnector
from agentic_cicd.integrations.ticketing import DryRunTicketingConnector, TicketRequest
from agentic_cicd.llm.base import ModelRequest
from agentic_cicd.llm.providers import NotConfiguredModelProvider, StaticStructuredModelProvider


class ExampleOutput(BaseModel):
    value: str


def test_integration_registry_reports_not_implemented_remote_scm() -> None:
    statuses = {status.id: status for status in default_integration_registry().list()}
    assert statuses["local-git"].implemented is True
    assert statuses["github-scm"].implemented is False
    assert "NOT_IMPLEMENTED" in (statuses["github-scm"].message or "")


def test_local_git_connector_is_safe_for_non_git_repository() -> None:
    connector = LocalGitConnector()
    assert connector.changed_files("samples/python_app") == []
    assert connector.current_commit("samples/python_app") is None


def test_dry_run_ticketing_connector_never_mutates_without_real_adapter() -> None:
    connector = DryRunTicketingConnector()
    dry_run = connector.create_ticket(TicketRequest(title="Failure", description="Test failure"), dry_run=True)
    assert dry_run.created is False
    assert "DRY RUN" in dry_run.message
    real = connector.create_ticket(TicketRequest(title="Failure", description="Test failure"), dry_run=False)
    assert real.created is False
    assert "NOT_IMPLEMENTED" in real.message


def test_agent_inventory_kill_switch_and_revocation() -> None:
    inventory = AgentInventory()
    identity = AgentIdentity(id="agent-1", permissions={Permission.EXECUTE_CI}, tools={"secret_scan"})
    inventory.register(identity)
    inventory.assert_agent_enabled("agent-1")
    inventory.revoke_tool("agent-1", "secret_scan")
    inventory.revoke_permission("agent-1", Permission.EXECUTE_CI)
    record = inventory.get("agent-1")
    assert record is not None
    assert "secret_scan" not in record.identity.tools
    assert Permission.EXECUTE_CI not in record.identity.permissions
    inventory.set_kill_switch(True)
    with pytest.raises(Exception):
        inventory.assert_agent_enabled("agent-1")


def test_model_provider_abstraction_is_explicit_when_unconfigured() -> None:
    provider = NotConfiguredModelProvider()
    response = provider.generate_structured(ModelRequest(task="intent_parse"), ExampleOutput)
    assert response.success is False
    assert "NOT_IMPLEMENTED" in (response.error or "")


def test_static_structured_model_provider_returns_typed_output_for_tests() -> None:
    provider = StaticStructuredModelProvider(ExampleOutput(value="ok"))
    response = provider.generate_structured(ModelRequest(task="demo"), ExampleOutput)
    assert response.success is True
    assert response.output == ExampleOutput(value="ok")
