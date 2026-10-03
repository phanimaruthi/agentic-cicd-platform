# Threat Model

## Assets

- Repository source and metadata
- Pipeline plans and execution history
- Runner credentials and capabilities
- Secret references and secret provider metadata
- Audit trail
- Deployment environments

## Key threats and mitigations

| Threat | Mitigation implemented |
|---|---|
| Prompt injection in README/issues | Repository content marked untrusted; tests assert it is not instruction |
| Unsafe shell command | Commands are argv lists; local runner uses `shell=False`; command classifier |
| Destructive infrastructure command | Default policy denies destructive tasks |
| Agent privilege escalation | Effective permissions = principal ∩ agent permissions |
| Secret leakage | `secret://` references and audit masking |
| Fake deployment/test success | Execution results come from typed runners; no invented success |
| Malicious tool output | Tool output is recorded as data and does not become policy |
| Confused deputy | Policy engine evaluates principal identity and environment gates |

## Remaining risks

- Real external runners/connectors need separate hardening.
- Persistent storage and API authentication are future work.
- Supply-chain signing/attestation adapters are future work.
