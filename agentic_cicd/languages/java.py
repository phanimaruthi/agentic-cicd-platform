"""Java/Maven/Gradle language provider."""

from __future__ import annotations

from pathlib import Path

from agentic_cicd.core.context import RepositoryContext
from agentic_cicd.core.enums import RiskLevel, TaskCategory
from agentic_cicd.core.task import RunnerCapabilityRequest, TaskSpec
from agentic_cicd.languages.base import LanguageDetection, LanguageProvider, LanguageTasks


class JavaLanguageProvider(LanguageProvider):
    id = "java"
    language = "Java"

    def detect(self, repository: RepositoryContext) -> LanguageDetection:
        reasons: list[str] = []
        confidence = 0.0
        if "Java" in repository.languages:
            confidence += 0.5
            reasons.append("Java files detected")
        if "maven" in repository.package_managers or "maven" in repository.build_systems:
            confidence += 0.3
            reasons.append("Maven metadata detected")
        if "gradle" in repository.package_managers or "gradle" in repository.build_systems:
            confidence += 0.3
            reasons.append("Gradle metadata detected")
        return LanguageDetection(
            language=self.language,
            provider_id=self.id,
            confidence=min(confidence, 1.0),
            reasons=reasons,
            maturity="implemented" if confidence >= 0.5 else "partial",
        )

    def tasks(self, repository: RepositoryContext) -> LanguageTasks:
        detection = self.detect(repository)
        root = Path(repository.path)
        if (root / "pom.xml").exists() or "maven" in repository.package_managers:
            tool = "mvn"
            test_cmd = ["mvn", "-B", "test"]
            build_cmd = ["mvn", "-B", "package", "-DskipTests"]
            label = "Maven"
        else:
            tool = "gradle"
            test_cmd = ["gradle", "test"]
            build_cmd = ["gradle", "build", "-x", "test"]
            label = "Gradle"
        return LanguageTasks(
            provider_id=self.id,
            detection=detection,
            test=[
                TaskSpec(
                    id="java_unit_tests",
                    type="unit_test",
                    name=f"Run {label} tests",
                    category=TaskCategory.TEST,
                    command=test_cmd,
                    risk=RiskLevel.SAFE,
                    required_capabilities=RunnerCapabilityRequest(tools={tool}),
                )
            ],
            build=[
                TaskSpec(
                    id="java_build",
                    type="compile",
                    name=f"Run {label} package/build",
                    category=TaskCategory.BUILD,
                    command=build_cmd,
                    risk=RiskLevel.SAFE,
                    required_capabilities=RunnerCapabilityRequest(tools={tool}),
                )
            ],
        )
