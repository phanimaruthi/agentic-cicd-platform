# Testing

## Test categories currently covered

- Schema and Pipeline IR validation
- Repository discovery
- Prompt-injection handling
- Planner and compiler behavior
- Local/mock runner safety
- Docker/Terraform/Kubernetes runner validation and command risk gates
- Typed tool registry contracts and authorization
- Command risk classification
- Policy and RBAC
- Production approval flow
- Execution audit event generation
- Execution persistence stores
- Failure diagnosis and remediation planning
- Golden-path template instantiation
- DAG scheduling/wave planning
- Lightweight SBOM generation
- Deployment health verification and rollback planning
- Knowledge graph impact queries

## Commands

```bash
python -m compileall -q agentic_cicd tests
pytest -q
python -m pytest -q samples/python_app
python -m agentic_cicd.tools.secret_scan samples/python_app
python -m agentic_cicd.cli security sbom samples/python_app
python -m agentic_cicd.cli pipeline validate pipelines/sample_ci_pipeline.json
python -m agentic_cicd.cli pipeline schedule pipelines/sample_ci_pipeline.json
python -m agentic_cicd.cli pipeline run pipelines/sample_ci_pipeline.json --repo-path samples/python_app --execute
```
