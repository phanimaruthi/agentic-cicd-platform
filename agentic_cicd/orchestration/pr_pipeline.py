"""Pull request / merge request pipeline factory.

This module creates a real runnable local pipeline from provider-neutral PR events.
It is safe by default: PR validation runs CI/security only; merged PRs can deploy to
local development/staging/prod-simulated environments subject to policy/RBAC.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.context import RepositoryContext
from agentic_cicd.core.enums import AutonomyLevel, RiskLevel, TaskCategory
from agentic_cicd.core.pipeline import (
    ApprovalGate,
    EnvironmentSpec,
    ExecutionStrategy,
    PipelineIR,
    PipelineMetadata,
    PipelineStage,
    PipelineTrigger,
)
from agentic_cicd.core.task import ArtifactSpec, RunnerCapabilityRequest, TaskSpec
from agentic_cicd.events.models import PullRequestEvent
from agentic_cicd.languages.registry import default_language_registry


class PRPipelineExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger: str
    repository: str
    pull_request: str
    source_branch: str
    target_branch: str
    mode: str
    environment: str | None = None
    stages: list[str] = Field(default_factory=list)
    deployment: str
    approval: str | None = None
    notes: list[str] = Field(default_factory=list)


class PRPipelineFactory:
    def build(self, event: PullRequestEvent, repository: RepositoryContext, *, actor: str) -> tuple[PipelineIR, PRPipelineExplanation]:
        service = repository.services[0] if repository.services else repository.name
        version = event.commit_sha or event.id
        environment = event.requested_environment
        language_task_sets = default_language_registry().task_sets(repository)
        quality_steps: list[TaskSpec] = []
        test_steps: list[TaskSpec] = []
        build_steps: list[TaskSpec] = []
        language_notes: list[str] = []
        for task_set in language_task_sets:
            quality_steps.extend(task_set.install)
            quality_steps.extend(task_set.quality)
            test_steps.extend(task_set.test)
            build_steps.extend(task_set.build)
            language_notes.extend(task_set.notes)
        if not test_steps:
            test_steps.append(self._missing_test_step())
        quality_dependencies = ["source"] if quality_steps else []
        test_dependencies = ["quality"] if quality_steps else ["source"]
        security_dependencies = ["quality"] if quality_steps else ["source"]
        stages: list[PipelineStage] = [
            PipelineStage(id="source", name="Source intelligence", type="source", steps=[self._inspect_step()]),
            PipelineStage(
                id="quality",
                name="Quality gates",
                type="quality",
                dependencies=quality_dependencies,
                steps=quality_steps,
            ),
            PipelineStage(
                id="test",
                name="Tests",
                type="test",
                dependencies=test_dependencies,
                steps=test_steps,
            ),
            PipelineStage(
                id="build",
                name="Language builds",
                type="build",
                dependencies=["test"],
                steps=build_steps,
            ),
            PipelineStage(
                id="security",
                name="Security and supply chain",
                type="security",
                dependencies=security_dependencies,
                steps=[self._secret_scan_step(), self._sbom_step()],
            ),
            PipelineStage(
                id="package",
                name="Package artifact",
                type="package",
                dependencies=["test", "security", *( ["build"] if build_steps else [] )],
                steps=[self._package_step(service, version)],
            ),
        ]
        approvals: list[ApprovalGate] = []
        environments: list[EnvironmentSpec] = []
        notes: list[str] = []
        deployment_text = "PR validation only; no deployment requested."
        if environment:
            protected = environment == "production"
            environments.append(
                EnvironmentSpec(
                    name=environment,
                    type="production" if protected else "non-production",
                    protected=protected,
                    requires_approval=protected,
                )
            )
            if protected:
                approvals.append(
                    ApprovalGate(
                        id="production_approval",
                        name="Production deployment approval",
                        required_roles=["ReleaseEngineer", "Admin"],
                        environment="production",
                        reason="Production deployment requires explicit approval.",
                    )
                )
            stages.extend(
                [
                    PipelineStage(
                        id="deploy",
                        name=f"Deploy to {environment}",
                        type="deployment",
                        dependencies=["package"],
                        steps=[self._deploy_step(service, version, environment)],
                    ),
                    PipelineStage(
                        id="verify",
                        name=f"Verify {environment}",
                        type="verification",
                        dependencies=["deploy"],
                        steps=[self._verify_step(service, environment)],
                    ),
                ]
            )
            deployment_text = (
                f"Merged/requested deployment to {environment} using local deployment simulator."
                if environment != "preview"
                else "Preview deployment using local deployment simulator."
            )
            if protected:
                notes.append("Production deployment will stop at APPROVAL_REQUIRED unless approved by policy/RBAC.")
        if not language_task_sets:
            notes.append("No supported language provider matched this repository; generated safe fallback test/security/package tasks.")
        if language_notes:
            notes.extend(language_notes)
        pipeline = PipelineIR(
            metadata=PipelineMetadata(
                name=f"PR #{event.pr_number} agentic delivery pipeline",
                description=f"Provider-neutral pipeline for {event.provider.value} PR/MR event {event.action.value}",
                repository=repository.path,
                service=service,
                created_by=actor,
                labels={
                    "event_id": event.id,
                    "provider": event.provider.value,
                    "pr_number": event.pr_number,
                    "source_branch": event.source_branch,
                    "target_branch": event.target_branch,
                },
            ),
            triggers=[PipelineTrigger(type="pull_request", branches=[event.target_branch])],
            variables={
                "SERVICE": service,
                "VERSION": version,
                "PR_NUMBER": event.pr_number,
                "PROVIDER": event.provider.value,
            },
            stages=[stage for stage in stages if stage.steps],
            policies=["baseline-rbac", "command-safety", "secret-masking", "security-scan-required", "deployment-gates"],
            approvals=approvals,
            environments=environments,
            execution_strategy=ExecutionStrategy(mode="dag", max_parallelism=4, max_tool_calls=50),
            autonomy_level=AutonomyLevel.HUMAN_IN_THE_LOOP,
        )
        explanation = PRPipelineExplanation(
            trigger=f"{event.provider.value}:{event.action.value}",
            repository=event.repository,
            pull_request=event.pr_number,
            source_branch=event.source_branch,
            target_branch=event.target_branch,
            mode="deploy" if environment else "validate",
            environment=environment,
            stages=[stage.name for stage in pipeline.stages],
            deployment=deployment_text,
            approval=approvals[0].name if approvals else None,
            notes=notes,
        )
        return pipeline, explanation

    def _inspect_step(self) -> TaskSpec:
        return TaskSpec(
            id="inspect_repository",
            type="inspect",
            name="Inspect repository",
            category=TaskCategory.SOURCE,
            command=["python", "-m", "agentic_cicd.cli", "discover", ".", "--json"],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
        )

    def _install_step(self, repository: RepositoryContext) -> TaskSpec | None:
        if any(manager in repository.package_managers for manager in ("pip/pyproject", "pip")):
            return TaskSpec(
                id="install_dependencies",
                type="install_dependencies",
                name="Install Python dependencies",
                category=TaskCategory.BUILD,
                command=["python", "-m", "pip", "install", "-e", "."],
                risk=RiskLevel.LOW_RISK,
                required_capabilities=RunnerCapabilityRequest(tools={"python"}),
            )
        if "npm" in repository.package_managers:
            return TaskSpec(
                id="install_dependencies",
                type="install_dependencies",
                name="Install npm dependencies",
                category=TaskCategory.BUILD,
                command=["npm", "ci"],
                risk=RiskLevel.LOW_RISK,
                required_capabilities=RunnerCapabilityRequest(tools={"npm"}),
            )
        return None

    def _lint_step(self, repository: RepositoryContext) -> TaskSpec | None:
        if "Python" in repository.languages:
            return TaskSpec(
                id="lint",
                type="lint",
                name="Compile Python sources",
                category=TaskCategory.TEST,
                command=["python", "-m", "compileall", "-q", "."],
                risk=RiskLevel.SAFE,
                required_capabilities=RunnerCapabilityRequest(tools={"python"}),
            )
        if "JavaScript" in repository.languages or "TypeScript" in repository.languages:
            return TaskSpec(
                id="lint",
                type="lint",
                name="npm lint",
                category=TaskCategory.TEST,
                command=["npm", "run", "lint"],
                risk=RiskLevel.SAFE,
                required_capabilities=RunnerCapabilityRequest(tools={"npm"}),
            )
        return None

    def _test_step(self, repository: RepositoryContext) -> TaskSpec:
        if "pytest" in repository.test_frameworks:
            return TaskSpec(
                id="unit_tests",
                type="unit_test",
                name="Run pytest unit tests",
                category=TaskCategory.TEST,
                command=["python", "-m", "pytest", "-q"],
                risk=RiskLevel.SAFE,
                required_capabilities=RunnerCapabilityRequest(tools={"python"}),
            )
        return TaskSpec(
            id="test_framework_detection",
            type="test_selection",
            name="Record missing test framework",
            category=TaskCategory.TEST,
            command=["python", "-c", "print('No supported test framework detected')"],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python"}),
        )

    def _missing_test_step(self) -> TaskSpec:
        return TaskSpec(
            id="test_framework_detection",
            type="test_selection",
            name="Record missing test framework",
            category=TaskCategory.TEST,
            command=["python", "-c", "print('No supported test framework detected')"],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python"}),
        )

    def _secret_scan_step(self) -> TaskSpec:
        return TaskSpec(
            id="secret_scan",
            type="secret_scan",
            name="Secret scan",
            category=TaskCategory.SECURITY,
            command=["python", "-m", "agentic_cicd.tools.secret_scan", "."],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
        )

    def _sbom_step(self) -> TaskSpec:
        return TaskSpec(
            id="generate_sbom",
            type="sbom",
            name="Generate SBOM",
            category=TaskCategory.SECURITY,
            command=["python", "-m", "agentic_cicd.tools.sbom", "."],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
        )

    def _package_step(self, service: str, version: str) -> TaskSpec:
        output = f".agentic_cicd/artifacts/{service}.json"
        return TaskSpec(
            id="package_artifact",
            type="package",
            name="Package local artifact manifest",
            category=TaskCategory.BUILD,
            command=[
                "python",
                "-m",
                "agentic_cicd.tools.artifacts",
                "package",
                "--repo",
                ".",
                "--service",
                service,
                "--version",
                version,
                "--output",
                output,
            ],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
            artifacts=[ArtifactSpec(name="local-artifact-manifest", paths=[output])],
        )

    def _deploy_step(self, service: str, version: str, environment: str) -> TaskSpec:
        artifact = f".agentic_cicd/artifacts/{service}.json"
        protected = environment == "production"
        return TaskSpec(
            id=f"deploy_{environment}",
            type="deploy",
            name=f"Deploy {service} to {environment}",
            category=TaskCategory.DEPLOYMENT,
            command=[
                "python",
                "-m",
                "agentic_cicd.tools.deployment_simulator",
                "deploy",
                "--service",
                service,
                "--environment",
                environment,
                "--artifact",
                artifact,
                "--version",
                version,
                "--strategy",
                "rolling" if environment != "preview" else "preview",
            ],
            risk=RiskLevel.HIGH_RISK if protected else RiskLevel.MEDIUM_RISK,
            side_effects=[f"write local deployment state for {service} in {environment}"],
            required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
            depends_on=["package_artifact"],
        )

    def _verify_step(self, service: str, environment: str) -> TaskSpec:
        return TaskSpec(
            id=f"verify_{environment}",
            type="verify",
            name=f"Verify {service} in {environment}",
            category=TaskCategory.OPERATIONAL,
            command=[
                "python",
                "-m",
                "agentic_cicd.tools.deployment_simulator",
                "verify",
                "--service",
                service,
                "--environment",
                environment,
            ],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
            depends_on=[f"deploy_{environment}"],
        )
