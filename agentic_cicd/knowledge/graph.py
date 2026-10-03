"""Relationship-oriented knowledge graph primitives."""

from __future__ import annotations

from typing import Any

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.context import RepositoryContext


class KGEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)


class KGRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraph:
    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()

    def add_entity(self, entity: KGEntity) -> None:
        self.graph.add_node(entity.id, **entity.model_dump(mode="json"))

    def add_relationship(self, relationship: KGRelationship) -> None:
        self.graph.add_edge(
            relationship.source,
            relationship.target,
            key=relationship.type,
            **relationship.model_dump(mode="json"),
        )

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        return dict(self.graph.nodes[entity_id]) if entity_id in self.graph.nodes else None

    def relationships(self, entity_id: str, relationship_type: str | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if entity_id not in self.graph:
            return results
        for _, target, key, data in self.graph.out_edges(entity_id, keys=True, data=True):
            if relationship_type is None or key == relationship_type:
                results.append({"source": entity_id, "target": target, "type": key, **data})
        return results

    def downstream_impact(self, service_id: str) -> list[str]:
        if service_id not in self.graph:
            return []
        impacted: set[str] = set()
        for _, target, key, _data in self.graph.out_edges(service_id, keys=True, data=True):
            if key in {"SERVICE_DEPENDS_ON_SERVICE", "DEPLOYMENT_TARGETS_SERVICE"}:
                impacted.add(target)
        for source, _, key, _data in self.graph.in_edges(service_id, keys=True, data=True):
            if key == "SERVICE_DEPENDS_ON_SERVICE":
                impacted.add(source)
        return sorted(impacted)

    def pipelines_for_service(self, service_id: str) -> list[str]:
        pipelines: list[str] = []
        for source, target, key, _data in self.graph.in_edges(service_id, keys=True, data=True):
            if key in {"PIPELINE_BUILDS_REPOSITORY", "DEPLOYMENT_TARGETS_SERVICE"}:
                pipelines.append(source)
        return sorted(set(pipelines))

    def ingest_repository(self, repository: RepositoryContext) -> None:
        repo_id = f"repository:{repository.name}"
        self.add_entity(
            KGEntity(id=repo_id, type="repository", name=repository.name, properties=repository.model_dump())
        )
        for service in repository.services:
            service_id = f"service:{service}"
            self.add_entity(KGEntity(id=service_id, type="service", name=service))
            self.add_relationship(
                KGRelationship(source=repo_id, target=service_id, type="REPOSITORY_CONTAINS_SERVICE")
            )
        for file in repository.changed_files:
            file_id = f"file:{file}"
            self.add_entity(KGEntity(id=file_id, type="file", name=file))
            self.add_relationship(KGRelationship(source=repo_id, target=file_id, type="COMMIT_CHANGED_FILE"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [dict(data) for _, data in self.graph.nodes(data=True)],
            "edges": [dict(data) for _, _, _, data in self.graph.edges(keys=True, data=True)],
        }
