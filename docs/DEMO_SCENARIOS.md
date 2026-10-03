# Required Demo Scenario Coverage

| # | Scenario | Current status |
|---|---|---|
| 1 | Analyze repository and tell how to build it | IMPLEMENTED via `discover` + `plan` |
| 2 | Generate a CI pipeline | IMPLEMENTED |
| 3 | Build and test the application | IMPLEMENTED for sample Python app/local runner |
| 4 | Build a Docker image and publish it | PARTIAL: Docker runner adapter and image build IR exist; registry publish still NOT_IMPLEMENTED without registry adapter/credentials |
| 5 | Run security checks | IMPLEMENTED for secret scan + lightweight SBOM; advanced scanners NOT_IMPLEMENTED |
| 6 | Deploy to development | PARTIAL: deployment plan, policy, verification primitives exist; real deployment adapter NOT_IMPLEMENTED |
| 7 | Deploy to staging | PARTIAL: plan/policy generated; real deployment adapter NOT_IMPLEMENTED |
| 8 | Prepare production deployment | IMPLEMENTED as high-risk plan requiring approval |
| 9 | Production deployment requiring approval | IMPLEMENTED policy path |
| 10 | Deployment fails, diagnose/remediate | PARTIAL: failure diagnosis/remediation + rollback planning implemented; real deployment adapter NOT_IMPLEMENTED |
| 11 | Kubernetes CrashLoopBackOff | PARTIAL: kubectl runner adapter and failure classification guidance; live cluster diagnostics require configured kubectl |
| 12 | Terraform plan fails | PARTIAL: Terraform runner adapter and failure classifier guidance; live plan requires configured terraform/tofu |
| 13 | New commit affects service A, determine impact | PARTIAL: KG impact query implemented; richer file-to-service mapping future work |
| 14 | Vulnerability affects deployed dependency | PARTIAL: SBOM/security report primitives exist; vulnerability ingestion and deployed artifact graph correlation future work |
| 15 | Malicious prompt injection in repository | IMPLEMENTED test |
| 16 | User requests unauthorized production action | IMPLEMENTED policy/RBAC test |

The test suite intentionally avoids real cloud/Kubernetes/GitHub credentials and uses mock/local runners where appropriate.

## Phase 9-10 updates

- Scenario 10 now has a concrete bounded retry remediation agent for transient failures.
- External integrations now expose explicit status; unconfigured providers report `NOT_IMPLEMENTED`.
- Agent kill-switch and revocation primitives are available for safety controls.
