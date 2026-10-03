# LLM Abstraction

The platform now includes a provider-agnostic structured model interface.

## Implemented

- `ModelCapabilities`
- `ModelRequest`
- `ModelResponse`
- `StructuredModelProvider` protocol
- `NotConfiguredModelProvider`
- `StaticStructuredModelProvider` for deterministic tests

## Policy

Business logic must not depend directly on a vendor SDK. Model output is advisory/structured input into typed planning and policy systems, not privileged execution.

## Current provider status

Real provider SDKs are **NOT_IMPLEMENTED**. When no provider is configured, the model provider returns an explicit `NOT_IMPLEMENTED` error.
