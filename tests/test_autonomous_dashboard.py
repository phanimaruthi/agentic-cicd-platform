from __future__ import annotations

from pathlib import Path

from agentic_cicd.core.enums import Role
from agentic_cicd.core.identity import Principal
from agentic_cicd.events.samples import sample_pull_request_event
from agentic_cicd.orchestration.control_plane import PullRequestControlPlane
from agentic_cicd.ui.autonomous_dashboard import render_autonomous_sdlc_console, write_autonomous_sdlc_console


def test_autonomous_sdlc_dashboard_renders_core_sections(tmp_path: Path) -> None:
    event = sample_pull_request_event(repo_path="samples/python_app", merged=True)
    bundle = PullRequestControlPlane().handle_pull_request(
        event,
        Principal(id="dev", roles={Role.DEVELOPER}),
        dry_run=True,
    )
    html = render_autonomous_sdlc_console(bundle)
    assert "Autonomous SDLC Control Plane" in html
    assert "Agent Orchestration" in html
    assert "Software Delivery Agent" in html
    assert "Security Testing Agent" in html
    assert "SDLC Knowledge Graph" in html
    assert "Original Agentic SDLC dashboard" in html
    output = write_autonomous_sdlc_console(tmp_path / "console.html", bundle)
    assert output.exists()
