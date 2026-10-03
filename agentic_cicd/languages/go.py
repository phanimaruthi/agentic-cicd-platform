"""Go language provider."""

from __future__ import annotations

from agentic_cicd.core.context import RepositoryContext
from agentic_cicd.core.enums import RiskLevel, TaskCategory
from agentic_cicd.core.task import RunnerCapabilityRequest, TaskSpec
from agentic_cicd.languages.base import LanguageDetection, LanguageProvider, LanguageTasks


class GoLanguageProvider(LanguageProvider):
    id = "go"
    language = "Go"

    def detect(self, repository: RepositoryContext) -> LanguageDetection:
        reasons: list[str] = []
        confidence = 0.0
        if "Go" in repository.languages:
            confidence += 0.55
            reasons.append("Go files detected")
        if "go modules" in repository.package_managers or "go" in repository.build_systems:
            confidence += 0.45
            reasons.append("go.mod/build metadata detected")
        return LanguageDetection(
            language=self.language,
            provider_id=self.id,
            confidence=min(confidence, 1.0),
            reasons=reasons,
            maturity="implemented" if confidence >= 0.55 else "partial",
        )

    def tasks(self, repository: RepositoryContext) -> LanguageTasks:
        detection = self.detect(repository)
        return LanguageTasks(
            provider_id=self.id,
            detection=detection,
            test=[
                TaskSpec(
                    id="go_unit_tests",
                    type="unit_test",
                    name="Run Go tests",
                    category=TaskCategory.TEST,
                    command=["go", "test", "./..."],
                    risk=RiskLevel.SAFE,
                    required_capabilities=RunnerCapabilityRequest(tools={"go"}),
                )
            ],
            build=[
                TaskSpec(
                    id="go_build",
                    type="compile",
                    name="Build Go modules",
                    category=TaskCategory.BUILD,
                    command=["go", "build", "./..."],
                    risk=RiskLevel.SAFE,
                    required_capabilities=RunnerCapabilityRequest(tools={"go"}),
                )
            ],
        )
