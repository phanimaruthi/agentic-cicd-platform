"""Python language provider."""

from __future__ import annotations

from agentic_cicd.core.context import RepositoryContext
from agentic_cicd.core.enums import RiskLevel, TaskCategory
from agentic_cicd.core.task import RunnerCapabilityRequest, TaskSpec
from agentic_cicd.languages.base import LanguageDetection, LanguageProvider, LanguageTasks


class PythonLanguageProvider(LanguageProvider):
    id = "python"
    language = "Python"

    def detect(self, repository: RepositoryContext) -> LanguageDetection:
        reasons: list[str] = []
        confidence = 0.0
        if "Python" in repository.languages:
            confidence += 0.45
            reasons.append("Python files detected")
        if any(manager in repository.package_managers for manager in ("pip/pyproject", "pip", "poetry", "pipenv")):
            confidence += 0.35
            reasons.append("Python package manager metadata detected")
        if "pytest" in repository.test_frameworks or "pytest" in repository.frameworks:
            confidence += 0.2
            reasons.append("pytest detected")
        return LanguageDetection(
            language=self.language,
            provider_id=self.id,
            confidence=min(confidence, 1.0),
            reasons=reasons,
            maturity="implemented",
        )

    def tasks(self, repository: RepositoryContext) -> LanguageTasks:
        detection = self.detect(repository)
        install: list[TaskSpec] = []
        quality: list[TaskSpec] = []
        test: list[TaskSpec] = []
        if any(manager in repository.package_managers for manager in ("pip/pyproject", "pip")):
            install.append(
                TaskSpec(
                    id="install_dependencies",
                    type="install_dependencies",
                    name="Install Python dependencies",
                    category=TaskCategory.BUILD,
                    command=["python", "-m", "pip", "install", "-e", "."],
                    risk=RiskLevel.LOW_RISK,
                    required_capabilities=RunnerCapabilityRequest(tools={"python"}),
                )
            )
        quality.append(
            TaskSpec(
                id="lint",
                type="lint",
                name="Python syntax/compile check",
                category=TaskCategory.TEST,
                command=["python", "-m", "compileall", "-q", "."],
                risk=RiskLevel.SAFE,
                required_capabilities=RunnerCapabilityRequest(tools={"python"}),
            )
        )
        if "pytest" in repository.test_frameworks:
            test.append(
                TaskSpec(
                    id="unit_tests",
                    type="unit_test",
                    name="Run pytest unit tests",
                    category=TaskCategory.TEST,
                    command=["python", "-m", "pytest", "-q"],
                    risk=RiskLevel.SAFE,
                    required_capabilities=RunnerCapabilityRequest(tools={"python"}),
                )
            )
        return LanguageTasks(provider_id=self.id, detection=detection, install=install, quality=quality, test=test)
