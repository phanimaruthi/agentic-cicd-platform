# Remediation Agent

The remediation agent is policy-bounded and intentionally conservative.

## Implemented behavior

- Consumes structured `ExecutionRecord` failures.
- Re-runs `FailureAnalyzer` and `RemediationPlanner`.
- Retrieves matching runbooks from local document index when available.
- Automatically performs only bounded retry actions for safe/low/medium-risk retryable failures.
- Evaluates policy before remediation execution.
- Executes remediation through typed runners, not free-form model output.
- Emits audit events for remediation start, retry task start/finish, and remediation finish.

## Not implemented / intentionally blocked

- No automatic source code mutation.
- No automatic infrastructure apply/destroy.
- No automatic production rollback without approval.
- No fabricated resources, credentials, or environment health.

## Example safe remediation

Transient test runner failure:

1. classify as `flaky_transient`
2. generate `bounded_retry`
3. policy-check retry task
4. rerun only affected task
5. record result and audit
