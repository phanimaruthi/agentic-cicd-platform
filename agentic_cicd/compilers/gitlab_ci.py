"""GitLab CI renderer for Pipeline IR."""

from __future__ import annotations

import shlex
from typing import Any

import yaml

from agentic_cicd.core.pipeline import PipelineIR


class GitLabCICompiler:
    def render(self, pipeline: PipelineIR) -> str:
        document: dict[str, Any] = {"stages": [stage.id for stage in pipeline.stages]}
        for stage in pipeline.stages:
            for task in stage.steps:
                job_name = f"{stage.id}_{task.id}"
                document[job_name] = {
                    "stage": stage.id,
                    "script": [shlex.join(task.command) if task.command else f"echo 'No command for {task.id}'"],
                    "timeout": f"{task.timeout_seconds}s",
                }
                if task.environment:
                    document[job_name]["variables"] = task.environment
                if task.depends_on:
                    document[job_name]["needs"] = task.depends_on
        return yaml.safe_dump(document, sort_keys=False)
