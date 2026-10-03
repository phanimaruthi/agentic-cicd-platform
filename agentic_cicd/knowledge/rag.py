"""Minimal local document retrieval for unstructured docs/runbooks.

This is intentionally separate from the knowledge graph. Repository documents are marked
untrusted and returned as evidence, never as instructions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from agentic_cicd.core.enums import TrustLevel


class RetrievedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uri: str
    title: str
    excerpt: str
    score: float
    trust_level: TrustLevel = TrustLevel.REPOSITORY


class LocalDocumentIndex:
    def __init__(self) -> None:
        self._documents: list[RetrievedDocument] = []

    def index_markdown(self, root: str | Path, *, trust_level: TrustLevel = TrustLevel.REPOSITORY) -> None:
        root_path = Path(root).expanduser().resolve()
        for path in root_path.rglob("*.md"):
            if ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            title = path.stem
            excerpt = text[:2000]
            self._documents.append(
                RetrievedDocument(uri=str(path), title=title, excerpt=excerpt, score=0.0, trust_level=trust_level)
            )

    def search(self, query: str, *, limit: int = 5) -> list[RetrievedDocument]:
        tokens = {token for token in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(token) > 2}
        scored: list[RetrievedDocument] = []
        for document in self._documents:
            haystack = f"{document.title} {document.excerpt}".lower()
            score = sum(1 for token in tokens if token in haystack) / max(len(tokens), 1)
            if score > 0:
                scored.append(document.model_copy(update={"score": score}))
        scored.sort(key=lambda doc: doc.score, reverse=True)
        return scored[:limit]

    def as_context_documents(self, documents: list[RetrievedDocument]) -> list[dict[str, Any]]:
        return [doc.model_dump(mode="json") for doc in documents]
