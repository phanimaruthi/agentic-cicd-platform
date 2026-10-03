# Knowledge Graph

The knowledge graph stores entities, relationships, lineage, topology, ownership, and execution facts. It is separate from RAG.

## Implemented entities

- repository
- service
- file

The model is generic and can accept additional entity types such as pipeline, stage, runner, environment, artifact, vulnerability, incident, policy, approval, secret reference, cloud account, database, migration, and feature flag.

## Implemented relationships

- `REPOSITORY_CONTAINS_SERVICE`
- `COMMIT_CHANGED_FILE`
- `SERVICE_DEPENDS_ON_SERVICE`
- `PIPELINE_BUILDS_REPOSITORY`
- `DEPLOYMENT_TARGETS_SERVICE`

## Queries

- downstream impact for a service
- pipelines for service
- outgoing relationships by type
