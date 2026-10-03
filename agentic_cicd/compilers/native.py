"""Native JSON renderer for Pipeline IR."""

from __future__ import annotations

from agentic_cicd.core.pipeline import PipelineIR


class NativeJsonCompiler:
    def render(self, pipeline: PipelineIR) -> str:
        return pipeline.model_dump_json(indent=2)
