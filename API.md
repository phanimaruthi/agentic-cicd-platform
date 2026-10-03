# API

Typed schemas exist for the conceptual endpoints. The optional FastAPI app currently implements health and pipeline generation when `fastapi` is installed.

## Conceptual endpoints

- `POST /agent/requests`
- `POST /pipelines/generate`
- `POST /pipelines/validate`
- `POST /pipelines/execute`
- `GET /executions/{id}`
- `POST /executions/{id}/cancel`
- `POST /executions/{id}/retry`
- `POST /executions/{id}/approve`
- `POST /executions/{id}/rollback`
- `GET /executions/{id}/logs`
- `GET /knowledge/services/{id}`
- `GET /knowledge/impact`
- `GET /policies`
- `GET /runners`
- `GET /audit`
- `GET /health`

## Current status

- Typed schemas: IMPLEMENTED
- FastAPI runtime: OPTIONAL / PARTIAL
- Persistent execution store: NOT_IMPLEMENTED
- Authenticated API security: NOT_IMPLEMENTED
