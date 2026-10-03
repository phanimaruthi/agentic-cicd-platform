# Integrations

## Implemented interfaces/foundations

- Integration metadata/status model
- Integration registry
- SCM connector protocol
- Local Git connector for read-only changed files/current commit
- Dry-run ticketing connector
- Dry-run notification connector
- Explicit NOT_IMPLEMENTED remote SCM connector statuses

## Implemented local integrations

| Integration | Status | Notes |
|---|---|---|
| local-git | IMPLEMENTED | read-only local repository metadata |
| dry-run-ticketing | IMPLEMENTED | never creates real tickets; dry-run only |
| dry-run-notifications | IMPLEMENTED | never sends real notifications; dry-run only |

## Explicitly not implemented remote integrations

- GitHub API
- GitLab API
- Bitbucket API
- Jenkins runtime
- AWS/Azure/GCP
- Docker registry push
- Kubernetes live deployment mutation
- Helm live release mutation
- Terraform remote state/apply orchestration
- Jira/ServiceNow real ticket creation
- Slack/Teams/email real notifications

Unimplemented integrations report `NOT_IMPLEMENTED` rather than pretending to work.
