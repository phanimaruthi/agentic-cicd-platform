# GitHub Status Integration v0.2

Version 0.2 adds an optional GitHub commit-status adapter on top of the provider-neutral PR/MR control plane.

## What it does

- Parses GitHub pull request webhook payloads.
- Runs the typed agentic CI/CD pipeline.
- Optionally posts commit statuses back to GitHub.
- Verifies GitHub webhook signatures when a webhook secret is available.
- Never pretends to update GitHub when credentials are missing.

## Environment variables

```powershell
$env:GITHUB_TOKEN="<token with repo:status or fine-grained commit status permission>"
$env:GITHUB_WEBHOOK_SECRET="<your webhook secret>"
```

Do not commit these values.

## Local dry-run

This runs the pipeline locally and performs GitHub status updates in dry-run mode:

```powershell
python -m agentic_cicd.cli integrations github-pr `
  --payload samples/webhooks/github_pull_request_merged.json `
  --repo-path samples/python_app `
  --execute-pipeline `
  --status-dry-run `
  --role Maintainer `
  --report reports/github_pr_delivery.html
```

## Send real GitHub status

After setting `GITHUB_TOKEN`, use:

```powershell
python -m agentic_cicd.cli integrations github-pr `
  --payload samples/webhooks/github_pull_request_merged.json `
  --repo-path samples/python_app `
  --execute-pipeline `
  --send-status `
  --role Maintainer `
  --target-url https://github.com/phanimaruthi/agentic-cicd-platform/actions `
  --report reports/github_pr_delivery.html
```

If `GITHUB_TOKEN` is not set, the result says `NOT_CONFIGURED` instead of faking success.

## Production note

For a live webhook server you still need:

- HTTP deployment
- TLS
- GitHub signature validation enabled
- repository checkout/mirroring
- persistence
- provider credentials stored as secrets
