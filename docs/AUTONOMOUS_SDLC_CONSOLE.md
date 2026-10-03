# Autonomous SDLC Console

This console is an original enterprise-style SDLC dashboard. It intentionally does **not** copy any vendor's protected UI/trade dress, but it provides the same kind of operational output expected from an autonomous software delivery platform:

- PR/MR trigger context
- specialized agent orchestration
- typed pipeline DAG waves
- policy/RBAC decisions
- task execution matrix
- security coverage
- deployment state
- SDLC knowledge graph
- captured logs

## Run it

```bash
python -m agentic_cicd.cli ui autonomous-demo \
  --repo-path samples/python_app \
  --execute \
  --output reports/autonomous_sdlc_console.html
```

Open:

```text
reports/autonomous_sdlc_console.html
```

## Production caveat

The console is real and generated from actual local pipeline execution. Hosted GitHub/GitLab production operation still needs webhook deployment, signature verification, checkout/mirroring, and provider credentials.
