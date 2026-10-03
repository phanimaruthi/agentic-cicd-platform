# Local Development

## Environment

Copy `.env.example` to `.env` and replace `secret://...` references with your secret manager configuration, not raw committed values.

## Run tests

```bash
pytest -q
```

## Generate and run demo pipeline

```bash
python -m agentic_cicd.cli plan "Generate a CI pipeline" --repo-path samples/python_app --json
python -m agentic_cicd.cli pipeline run pipelines/sample_ci_pipeline.json --repo-path samples/python_app --dry-run
python -m agentic_cicd.cli pipeline run pipelines/sample_ci_pipeline.json --repo-path samples/python_app --execute
```

## Docker Compose

`docker-compose.yml` provides a local skeleton. It does not claim production persistence or external integrations.
