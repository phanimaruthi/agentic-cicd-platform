"""Provider-agnostic structured model interface.

No business logic should depend on a vendor SDK directly. Until a provider is
configured, model calls return explicit NOT_IMPLEMENTED metadata rather than
fabricated structured output.
"""

from __future__ import annotations

from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T", bound=BaseModel)


class ModelCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    structured_output: bool = False
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    supports_tools: bool = False
    supports_json_schema: bool = False
    cost_per_1k_input_tokens: float | None = None
    cost_per_1k_output_tokens: float | None = None


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=60, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)


class ModelResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    success: bool
    output: T | None = None
    provider: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructuredModelProvider(Protocol):
    capabilities: ModelCapabilities

    def generate_structured(self, request: ModelRequest, output_type: type[T]) -> ModelResponse[T]:
        ...
