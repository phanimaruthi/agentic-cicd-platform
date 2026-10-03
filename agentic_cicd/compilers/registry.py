"""Compiler registry."""

from __future__ import annotations

from agentic_cicd.compilers.github_actions import GitHubActionsCompiler
from agentic_cicd.compilers.gitlab_ci import GitLabCICompiler
from agentic_cicd.compilers.native import NativeJsonCompiler
from agentic_cicd.core.enums import PipelineBackend
from agentic_cicd.core.pipeline import PipelineIR


class PipelineCompilerRegistry:
    def render(self, pipeline: PipelineIR, backend: PipelineBackend) -> str:
        if backend == PipelineBackend.NATIVE:
            return NativeJsonCompiler().render(pipeline)
        if backend == PipelineBackend.GITHUB_ACTIONS:
            return GitHubActionsCompiler().render(pipeline)
        if backend == PipelineBackend.GITLAB_CI:
            return GitLabCICompiler().render(pipeline)
        if backend == PipelineBackend.JENKINS:
            return "NOT_IMPLEMENTED: Jenkins renderer adapter is not implemented"
        return NativeJsonCompiler().render(pipeline)
