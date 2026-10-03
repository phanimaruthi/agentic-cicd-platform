"""Language provider contract.

Language providers convert repository evidence into typed CI tasks. They do not
execute tools directly and they do not assume a runner; each task declares the
capabilities it needs so the runner registry can select an execution backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.context import RepositoryContext
from agentic_cicd.core.task import TaskSpec


class LanguageDetection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str
    provider_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    maturity: Literal["implemented", "partial", "not_implemented"] = "partial"


class LanguageTasks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    detection: LanguageDetection
    install: list[TaskSpec] = Field(default_factory=list)
    quality: list[TaskSpec] = Field(default_factory=list)
    test: list[TaskSpec] = Field(default_factory=list)
    build: list[TaskSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def all_tasks(self) -> list[TaskSpec]:
        return [*self.install, *self.quality, *self.test, *self.build]


class LanguageProvider(ABC):
    id: str
    language: str

    @abstractmethod
    def detect(self, repository: RepositoryContext) -> LanguageDetection:
        """Return detection confidence based on repository evidence."""

    @abstractmethod
    def tasks(self, repository: RepositoryContext) -> LanguageTasks:
        """Return typed install/quality/test/build tasks for this language."""
