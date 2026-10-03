# Security

## Security model

The platform treats the LLM as a reasoning component, not a trusted execution engine. Real actions must flow through typed tasks, policies, runner selection, command safety, and audit.

## Implemented controls

- Repository files are untrusted; README text is never interpreted as agent instruction.
- Commands are represented as argv lists.
- Local runner uses `subprocess.run(..., shell=False)`.
- Command classifier detects destructive/high-risk operations.
- Destructive operations are denied by policy by default.
- High-risk operations require approval when not dry-run.
- RBAC prevents the agent from exceeding the initiating principal's permissions.
- Secrets use `secret://provider/path/key` references.
- Secret-like audit/log fields are masked.
- Prompt-injection tests are included.
- Secret scanner reports only file/line/rule metadata, never secret values.

## Secrets policy

Never commit credentials. `.env.example` contains references, not values.

## Not implemented yet

- Real secret provider adapters.
- KMS-backed encryption at rest.
- Signed provenance/attestation integration.
- Container image scanner adapter.
- SLSA verification adapter.
