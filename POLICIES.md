# Policies

## Decisions

- `ALLOW`
- `DENY`
- `REQUIRES_APPROVAL`
- `REQUIRES_REVIEW`
- `WARN`

## Implemented baseline policies

- RBAC permission enforcement.
- Production deployments require production deploy permission.
- Production deployments require approval.
- Destructive actions are denied by default.
- High-risk actions require approval when not dry-run.
- Deployment pipelines require security scan tasks.
- Runner/image allowlist hooks.
- Secret-related repository files produce warnings.

## OPA/Rego

An OPA backend interface exists. Runtime integration is `NOT_IMPLEMENTED` until an OPA executable or HTTP endpoint is configured.
