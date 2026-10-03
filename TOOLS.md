# Tools

Tools are typed execution primitives invoked by runners or future MCP adapters. Each tool has a contract:

- name
- description
- input schema
- output schema
- permission requirements
- risk level
- side effects
- timeout
- retry behavior
- audit behavior

## Implemented local tools

| Tool | Status | Risk | Permission | Notes |
|---|---|---|---|---|
| `secret_scan` | IMPLEMENTED | SAFE | `execute_ci` | Reports file/line/rule only, never secret values |
| `generate_sbom` | IMPLEMENTED | SAFE | `execute_ci` | Lightweight local inventory; production attestations should use Syft/CycloneDX |
| `git_diff` | IMPLEMENTED | SAFE | `read_repository` | Uses `git diff --name-only HEAD` when repository is Git |

## Planned tools

- `terraform_plan`, `terraform_apply`, `terraform_destroy`
- `kubectl_get`, `kubectl_logs`, `kubectl_describe`, `kubectl_rollout`, `kubectl_rollback`
- `docker_build`, `docker_push`
- `scan_image`, `generate_production_sbom`, `sign_artifact`, `verify_attestation`
- `deploy_service`, `rollback_deployment`
- observability query tools

Unimplemented tools must return `NOT_IMPLEMENTED`/`RUNNER_UNAVAILABLE` rather than fake success.
