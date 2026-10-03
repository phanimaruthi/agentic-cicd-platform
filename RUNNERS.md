# Runners

## Runner contract

A runner exposes:

- `id`
- `kind`
- `capabilities`
- `validate(task)`
- `execute(task, context)`
- `health_check()`
- optional cancel/log/output collection

## Implemented runners

| Runner | Status | Notes |
|---|---|---|
| Local shell | IMPLEMENTED | argv execution, `shell=False`, max risk threshold |
| Mock | IMPLEMENTED | deterministic tests/demos only; not auto-registered by default |
| Docker CLI | IMPLEMENTED | adapter around `docker`; build/push/run are policy/risk-gated; registered only if `docker` exists |
| Terraform/OpenTofu CLI | IMPLEMENTED | default allows fmt/validate/plan-class risk only; apply/destroy denied unless explicitly configured and policy-approved |
| Kubernetes kubectl CLI | IMPLEMENTED | default read-only risk threshold; mutations denied unless explicitly configured and policy-approved |
| Helm CLI | IMPLEMENTED | default lint/template risk threshold; release mutations denied unless explicitly configured and policy-approved |
| Kubernetes Job | NOT_IMPLEMENTED | future remote execution adapter |
| SSH/VM/Windows | NOT_IMPLEMENTED | future adapters |
| HTTP/API | NOT_IMPLEMENTED | future connector |

## Capability matching

The planner declares required capabilities on each task. The registry selects a runner whose capabilities satisfy the request; individual tasks do not hard-code runner choice unless explicitly required.

## Safety note

The default registry intentionally does **not** include the mock runner. Tests can explicitly register it, but normal execution should return `RUNNER_UNAVAILABLE` rather than fake success when a real capability is missing.
