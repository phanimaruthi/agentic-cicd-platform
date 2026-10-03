"""GitHub Actions renderer for Pipeline IR.

Planning logic never lives here; this module only renders a validated IR.
"""

from __future__ import annotations

import shlex
from typing import Any

import yaml

from agentic_cicd.core.pipeline import PipelineIR


class GitHubActionsCompiler:
    def render(self, pipeline: PipelineIR) -> str:
        jobs: dict[str, Any] = {}
        for stage in pipeline.stages:
            steps: list[dict[str, Any]] = [{"name": "Checkout", "uses": "actions/checkout@v4"}]
            for task in stage.steps:
                step: dict[str, Any] = {"name": task.name}
                if task.command:
                    step["run"] = shlex.join(task.command)
                else:
                    step["run"] = f"echo {shlex.quote('No command for ' + task.id)}"
                if task.environment:
                    step["env"] = task.environment
                if task.timeout_seconds:
                    step["timeout-minutes"] = max(1, task.timeout_seconds // 60)
                steps.append(step)
            jobs[stage.id] = {
                "name": stage.name,
                "runs-on": "ubuntu-latest",
                "needs": stage.dependencies or None,
                "timeout-minutes": max(1, stage.timeout_seconds // 60),
                "steps": steps,
            }
            if jobs[stage.id]["needs"] is None:
                del jobs[stage.id]["needs"]
        workflow: dict[str, Any] = {
            "name": pipeline.metadata.name,
            "on": self._render_triggers(pipeline),
            "permissions": {"contents": "read"},
            "jobs": jobs,
        }
        return yaml.safe_dump(workflow, sort_keys=False)

    def _render_triggers(self, pipeline: PipelineIR) -> dict[str, Any]:
        rendered: dict[str, Any] = {"workflow_dispatch": {}}
        for trigger in pipeline.triggers:
            if trigger.type == "push":
                rendered["push"] = {"branches": trigger.branches or ["main"]}
                if trigger.paths:
                    rendered["push"]["paths"] = trigger.paths
            elif trigger.type == "pull_request":
                rendered["pull_request"] = {"branches": trigger.branches or ["main"]}
            elif trigger.type == "schedule" and trigger.schedule:
                rendered.setdefault("schedule", []).append({"cron": trigger.schedule})
        return rendered
