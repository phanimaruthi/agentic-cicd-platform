"""Versioned golden-path pipeline templates."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.pipeline import PipelineIR


class TemplateParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str = "string"
    required: bool = True
    default: Any | None = None
    description: str | None = None


class PipelineTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    version: str
    description: str
    parameters: list[TemplateParameter] = Field(default_factory=list)
    tags: set[str] = Field(default_factory=set)
    approved: bool = True
    owner: str = "platform"
    pipeline: PipelineIR

    def instantiate(self, values: dict[str, Any] | None = None) -> PipelineIR:
        values = values or {}
        missing = [parameter.name for parameter in self.parameters if parameter.required and parameter.name not in values and parameter.default is None]
        if missing:
            raise ValueError(f"missing required template parameters: {missing}")
        pipeline = self.pipeline.model_copy(deep=True)
        for parameter in self.parameters:
            value = values.get(parameter.name, parameter.default)
            if value is not None:
                pipeline.variables[parameter.name.upper()] = str(value)
        pipeline.metadata.labels["template_id"] = self.id
        pipeline.metadata.labels["template_version"] = self.version
        return pipeline
