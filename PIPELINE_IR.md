# Pipeline IR

The Pipeline Intermediate Representation is the canonical execution plan. Backend YAML is rendered from IR and is not the primary planning output.

## Main models

- `PipelineIR`
- `PipelineMetadata`
- `PipelineTrigger`
- `EnvironmentSpec`
- `ApprovalGate`
- `ExecutionStrategy`
- `PipelineStage`
- `TaskSpec`
- `RunnerCapabilityRequest`
- `SecretReference`

## Validation

Implemented validations:

- duplicate stage/task/approval IDs
- missing stage dependencies
- missing task dependencies
- circular stage/task dependencies
- invalid approval environment references
- invalid task IDs
- raw secret-like environment values
- high-risk/destructive tasks require side-effect declaration

## DAG support

The IR supports stage and task dependencies. The current execution engine walks the DAG serially for safety; parallel execution is an extension point.
