"""Node.js / JavaScript / TypeScript language provider."""

from __future__ import annotations

from pathlib import Path

from agentic_cicd.core.context import RepositoryContext
from agentic_cicd.core.enums import RiskLevel, TaskCategory
from agentic_cicd.core.task import RunnerCapabilityRequest, TaskSpec
from agentic_cicd.languages.base import LanguageDetection, LanguageProvider, LanguageTasks


class NodeLanguageProvider(LanguageProvider):
    id = "node"
    language = "Node.js"

    def detect(self, repository: RepositoryContext) -> LanguageDetection:
        reasons: list[str] = []
        confidence = 0.0
        if "JavaScript" in repository.languages or "TypeScript" in repository.languages:
            confidence += 0.4
            reasons.append("JavaScript/TypeScript files detected")
        if any(manager in repository.package_managers for manager in ("npm", "yarn", "pnpm")):
            confidence += 0.45
            reasons.append("Node package manager lockfile detected")
        if any(framework in repository.test_frameworks for framework in ("jest", "vitest")):
            confidence += 0.15
            reasons.append("Node test framework detected")
        return LanguageDetection(
            language=self.language,
            provider_id=self.id,
            confidence=min(confidence, 1.0),
            reasons=reasons,
            maturity="implemented" if confidence >= 0.45 else "partial",
        )

    def tasks(self, repository: RepositoryContext) -> LanguageTasks:
        detection = self.detect(repository)
        install: list[TaskSpec] = []
        quality: list[TaskSpec] = []
        test: list[TaskSpec] = []
        build: list[TaskSpec] = []
        manager = self._manager(repository)
        if manager == "npm":
            install_cmd = ["npm", "ci"]
        elif manager == "yarn":
            install_cmd = ["yarn", "install", "--frozen-lockfile"]
        elif manager == "pnpm":
            install_cmd = ["pnpm", "install", "--frozen-lockfile"]
        else:
            install_cmd = ["npm", "install"]
            manager = "npm"
        install.append(
            TaskSpec(
                id="node_install_dependencies",
                type="install_dependencies",
                name=f"Install Node dependencies with {manager}",
                category=TaskCategory.BUILD,
                command=install_cmd,
                risk=RiskLevel.LOW_RISK,
                required_capabilities=RunnerCapabilityRequest(tools={manager}),
            )
        )
        if self._script_exists(repository, "lint"):
            quality.append(
                TaskSpec(
                    id="node_lint",
                    type="lint",
                    name="Run Node lint script",
                    category=TaskCategory.TEST,
                    command=[manager, "run", "lint"],
                    risk=RiskLevel.SAFE,
                    required_capabilities=RunnerCapabilityRequest(tools={manager}),
                )
            )
        if any(framework in repository.test_frameworks for framework in ("jest", "vitest")) or self._script_exists(repository, "test"):
            test.append(
                TaskSpec(
                    id="node_unit_tests",
                    type="unit_test",
                    name="Run Node test script",
                    category=TaskCategory.TEST,
                    command=[manager, "test", "--", "--ci"] if manager == "npm" else [manager, "test"],
                    risk=RiskLevel.SAFE,
                    required_capabilities=RunnerCapabilityRequest(tools={manager}),
                )
            )
        if self._script_exists(repository, "build"):
            build.append(
                TaskSpec(
                    id="node_build",
                    type="compile",
                    name="Run Node build script",
                    category=TaskCategory.BUILD,
                    command=[manager, "run", "build"],
                    risk=RiskLevel.SAFE,
                    required_capabilities=RunnerCapabilityRequest(tools={manager}),
                )
            )
        return LanguageTasks(
            provider_id=self.id,
            detection=detection,
            install=install,
            quality=quality,
            test=test,
            build=build,
            notes=["Node execution requires the selected package manager on the runner."],
        )

    def _manager(self, repository: RepositoryContext) -> str:
        if "pnpm" in repository.package_managers:
            return "pnpm"
        if "yarn" in repository.package_managers:
            return "yarn"
        return "npm"

    def _script_exists(self, repository: RepositoryContext, script: str) -> bool:
        package_json = Path(repository.path) / "package.json"
        if not package_json.exists():
            return False
        text = package_json.read_text(encoding="utf-8", errors="ignore")
        return f'"{script}"' in text
