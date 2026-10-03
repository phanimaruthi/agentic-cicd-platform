"""Model provider implementations."""

from __future__ import annotations

from pydantic import BaseModel

from agentic_cicd.llm.base import ModelCapabilities, ModelRequest, ModelResponse, StructuredModelProvider, T


class NotConfiguredModelProvider(StructuredModelProvider):
    def __init__(self, provider: str = "not_configured", model: str = "not_configured") -> None:
        self.capabilities = ModelCapabilities(provider=provider, model=model, structured_output=False)

    def generate_structured(self, request: ModelRequest, output_type: type[T]) -> ModelResponse[T]:
        return ModelResponse(
            success=False,
            output=None,
            provider=self.capabilities.provider,
            model=self.capabilities.model,
            error="NOT_IMPLEMENTED: no structured model provider is configured",
            metadata={"task": request.task, "requested_output_type": output_type.__name__},
        )


class StaticStructuredModelProvider(StructuredModelProvider):
    """Test/deterministic provider returning a supplied Pydantic object."""

    def __init__(self, output: BaseModel, provider: str = "static", model: str = "static") -> None:
        self.output = output
        self.capabilities = ModelCapabilities(provider=provider, model=model, structured_output=True, supports_json_schema=True)

    def generate_structured(self, request: ModelRequest, output_type: type[T]) -> ModelResponse[T]:
        if not isinstance(self.output, output_type):
            return ModelResponse(
                success=False,
                provider=self.capabilities.provider,
                model=self.capabilities.model,
                error="configured static output does not match requested schema",
                metadata={"task": request.task, "requested_output_type": output_type.__name__},
            )
        return ModelResponse(
            success=True,
            output=self.output,
            provider=self.capabilities.provider,
            model=self.capabilities.model,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            metadata={"task": request.task},
        )
