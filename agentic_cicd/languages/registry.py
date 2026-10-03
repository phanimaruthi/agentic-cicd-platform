"""Language provider registry and task composition."""

from __future__ import annotations

from agentic_cicd.core.context import RepositoryContext
from agentic_cicd.languages.base import LanguageDetection, LanguageProvider, LanguageTasks
from agentic_cicd.languages.go import GoLanguageProvider
from agentic_cicd.languages.java import JavaLanguageProvider
from agentic_cicd.languages.node import NodeLanguageProvider
from agentic_cicd.languages.python import PythonLanguageProvider


class LanguageRegistry:
    def __init__(self, providers: list[LanguageProvider] | None = None) -> None:
        self.providers = providers or [
            PythonLanguageProvider(),
            NodeLanguageProvider(),
            GoLanguageProvider(),
            JavaLanguageProvider(),
        ]

    def detect(self, repository: RepositoryContext, *, min_confidence: float = 0.35) -> list[LanguageDetection]:
        detections = [provider.detect(repository) for provider in self.providers]
        detections = [detection for detection in detections if detection.confidence >= min_confidence]
        detections.sort(key=lambda detection: detection.confidence, reverse=True)
        return detections

    def matching_providers(self, repository: RepositoryContext, *, min_confidence: float = 0.35) -> list[LanguageProvider]:
        detections = {detection.provider_id: detection for detection in self.detect(repository, min_confidence=min_confidence)}
        providers = [provider for provider in self.providers if provider.id in detections]
        providers.sort(key=lambda provider: detections[provider.id].confidence, reverse=True)
        return providers

    def task_sets(self, repository: RepositoryContext, *, min_confidence: float = 0.35) -> list[LanguageTasks]:
        return [provider.tasks(repository) for provider in self.matching_providers(repository, min_confidence=min_confidence)]

    def summary(self, repository: RepositoryContext) -> list[dict[str, object]]:
        return [detection.model_dump(mode="json") for detection in self.detect(repository, min_confidence=0.0)]


def default_language_registry() -> LanguageRegistry:
    return LanguageRegistry()
