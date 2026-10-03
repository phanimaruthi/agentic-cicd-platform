"""Deterministic planning from intent + context into typed Pipeline IR."""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from agentic_cicd.core.context import ContextBundle, RepositoryContext
from agentic_cicd.core.enums import AutonomyLevel, IntentAction, RiskLevel, TaskCategory
from agentic_cicd.core.errors import ContextUnavailableError
from agentic_cicd.core.identity import Principal
from agentic_cicd.core.intent import Intent
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
from agentic_cicd.languages.registry import default_language_registry


class PlanExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str | None = None
    environment: str | None = None
    change: str
    dependencies: list[str] = Field(default_factory=list)
    pipeline: list[str] = Field(default_factory=list)
    runner: str
    security_checks: list[str] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)
    blast_radius: str
    rollback: str
    verification: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class PlannedPipeline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineIR
    explanation: PlanExplanation


class PipelinePlanner:
    """Constructs deterministic typed plans; no backend YAML is generated here."""

    def plan(self, intent: Intent, context: ContextBundle, principal: Principal) -> PlannedPipeline:
        if not context.repository:
            raise ContextUnavailableError("repository context is required for planning")
        repository = context.repository
        if intent.action == IntentAction.ANALYZE_REPOSITORY:
            return self._analysis_plan(intent, repository, principal)
        if intent.action == IntentAction.SECURITY_CHECKS:
            return self._security_plan(intent, repository, principal)
        if intent.action == IntentAction.BUILD_IMAGE:
            return self._image_plan(intent, repository, principal)
        if intent.action in {IntentAction.DEPLOY, IntentAction.PREPARE_DEPLOYMENT}:
            return self._deployment_plan(intent, repository, principal)
        if intent.action == IntentAction.IMPACT_ANALYSIS:
            return self._impact_plan(intent, repository, principal)
        return self._ci_plan(intent, repository, principal)

    def _analysis_plan(self, intent: Intent, repository: RepositoryContext, principal: Principal) -> PlannedPipeline:
        inspect = TaskSpec(
            id="inspect_repository",
            type="inspect",
            name="Inspect repository",
            category=TaskCategory.SOURCE,
            command=["python", "-m", "agentic_cicd.cli", "discover", ".", "--json"],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
        )
        pipeline = self._base_pipeline(
            name="Repository analysis",
            repository=repository,
            principal=principal,
            stages=[PipelineStage(id="analysis", name="Repository analysis", type="analysis", steps=[inspect])],
            intent=intent,
        )
        explanation = self._explain(pipeline, intent, repository, change="Analyze repository build/test metadata")
        return PlannedPipeline(pipeline=pipeline, explanation=explanation)

    def _ci_plan(self, intent: Intent, repository: RepositoryContext, principal: Principal) -> PlannedPipeline:
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
            test_steps.append(
                TaskSpec(
                    id="test_framework_detection",
                    type="test_selection",
                    name="Record missing test framework",
                    category=TaskCategory.TEST,
                    command=["python", "-c", "print('No supported test framework detected')"],
                    risk=RiskLevel.SAFE,
                    required_capabilities=RunnerCapabilityRequest(tools={"python"}),
                )
            )
        quality_dependencies = ["source"] if quality_steps else []
        test_dependencies = ["quality"] if quality_steps else ["source"]
        security_dependencies = ["quality"] if quality_steps else ["source"]
        stages = [
            PipelineStage(id="source", name="Source and discovery", type="source", steps=[self._repo_inspect_step(repository)]),
            PipelineStage(id="quality", name="Quality checks", type="quality", dependencies=quality_dependencies, steps=quality_steps),
            PipelineStage(id="test", name="Tests", type="test", dependencies=test_dependencies, steps=test_steps),
            PipelineStage(id="build", name="Build", type="build", dependencies=["test"], steps=build_steps),
            PipelineStage(id="security", name="Security", type="security", dependencies=security_dependencies, steps=[self._secret_scan_step(repository), self._sbom_step(repository)]),
        ]
        stages = [stage for stage in stages if stage.steps]
        pipeline = self._base_pipeline(
            name="Generated CI pipeline",
            repository=repository,
            principal=principal,
            stages=stages,
            intent=intent,
        )
        explanation = self._explain(pipeline, intent, repository, change="Generate and validate language-agnostic CI pipeline")
        explanation.risks.extend(language_notes)
        if not language_task_sets:
            explanation.risks.append("No supported language provider matched this repository; generated a safe discovery/security skeleton.")
        else:
            explanation.dependencies.extend([task_set.detection.language for task_set in language_task_sets])
        return PlannedPipeline(pipeline=pipeline, explanation=explanation)

    def _security_plan(self, intent: Intent, repository: RepositoryContext, principal: Principal) -> PlannedPipeline:
        steps = [self._repo_inspect_step(repository), self._secret_scan_step(repository), self._sbom_step(repository)]
        if repository.dockerfiles:
            steps.append(
                TaskSpec(
                    id="container_scan_prepare",
                    type="container_scan",
                    name="Prepare container scan (tool availability check)",
                    category=TaskCategory.SECURITY,
                    command=["python", "-c", "print('NOT_IMPLEMENTED: real container scanner adapter not configured')"],
                    risk=RiskLevel.SAFE,
                    required_capabilities=RunnerCapabilityRequest(tools={"python"}),
                )
            )
        pipeline = self._base_pipeline(
            name="Security checks",
            repository=repository,
            principal=principal,
            stages=[PipelineStage(id="security", name="Security checks", type="security", steps=steps)],
            intent=intent,
        )
        explanation = self._explain(pipeline, intent, repository, change="Run repository security checks")
        return PlannedPipeline(pipeline=pipeline, explanation=explanation)

    def _image_plan(self, intent: Intent, repository: RepositoryContext, principal: Principal) -> PlannedPipeline:
        if not repository.dockerfiles:
            raise ContextUnavailableError("Docker image build requested but no Dockerfile was discovered")
        build = TaskSpec(
            id="docker_build",
            type="build_container",
            name="Build Docker image",
            category=TaskCategory.BUILD,
            command=["docker", "build", "-t", f"{repository.name}:local", "-f", repository.dockerfiles[0], "."],
            risk=RiskLevel.MEDIUM_RISK,
            required_capabilities=RunnerCapabilityRequest(docker=True, tools={"docker"}),
            artifacts=[ArtifactSpec(name="container-image", paths=[f"oci://local/{repository.name}:local"])],
        )
        scan = self._secret_scan_step(repository)
        pipeline = self._base_pipeline(
            name="Docker image build",
            repository=repository,
            principal=principal,
            stages=[
                PipelineStage(id="security", name="Pre-build security", type="security", steps=[scan]),
                PipelineStage(id="image", name="Container build", type="build", dependencies=["security"], steps=[build]),
            ],
            intent=intent,
        )
        explanation = self._explain(pipeline, intent, repository, change="Build local Docker image; publishing requires registry configuration")
        explanation.risks.append("Image publishing is NOT_IMPLEMENTED without registry and credentials configuration")
        return PlannedPipeline(pipeline=pipeline, explanation=explanation)

    def _deployment_plan(self, intent: Intent, repository: RepositoryContext, principal: Principal) -> PlannedPipeline:
        environment = intent.environment or "development"
        protected = environment == "production"
        verify = TaskSpec(
            id="verify_artifact_and_context",
            type="verify",
            name="Verify artifact/environment context",
            category=TaskCategory.OPERATIONAL,
            command=["python", "-c", f"print('verify deployment context for {environment}')"],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python"}),
        )
        security = self._secret_scan_step(repository)
        deploy = TaskSpec(
            id=f"deploy_{environment}",
            type="deploy",
            name=f"Deploy to {environment}",
            category=TaskCategory.DEPLOYMENT,
            command=["python", "-c", f"print('NOT_IMPLEMENTED: no concrete deployment adapter configured for {environment}')"],
            risk=RiskLevel.HIGH_RISK if protected else RiskLevel.MEDIUM_RISK,
            required_capabilities=RunnerCapabilityRequest(tools={"python"}),
            side_effects=[f"would deploy {repository.name} to {environment}"],
            depends_on=["verify_artifact_and_context"],
        )
        health = TaskSpec(
            id=f"verify_{environment}_health",
            type="verify",
            name=f"Verify {environment} health",
            category=TaskCategory.OPERATIONAL,
            command=["python", "-c", "print('NOT_IMPLEMENTED: health provider not configured')"],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python"}),
            depends_on=[deploy.id],
        )
        approvals = []
        if protected:
            approvals.append(
                ApprovalGate(
                    id="production_approval",
                    name="Production approval",
                    required_roles=["ReleaseEngineer", "Admin"],
                    environment="production",
                    reason="Production deployment requires explicit human approval and health/rollback verification",
                )
            )
        pipeline = self._base_pipeline(
            name=f"Prepare deployment to {environment}",
            repository=repository,
            principal=principal,
            stages=[
                PipelineStage(id="preflight", name="Preflight", type="validation", steps=[verify, security]),
                PipelineStage(id="deploy", name="Deployment", type="deployment", dependencies=["preflight"], steps=[deploy]),
                PipelineStage(id="verify", name="Post-deployment verification", type="verification", dependencies=["deploy"], steps=[health]),
            ],
            intent=intent,
            environments=[
                EnvironmentSpec(
                    name=environment,
                    type="production" if protected else "non-production",
                    protected=protected,
                    requires_approval=protected,
                )
            ],
            approvals=approvals,
        )
        explanation = self._explain(pipeline, intent, repository, change=f"Prepare deployment to {environment}")
        if protected:
            explanation.approvals.append("Production approval by ReleaseEngineer/Admin")
            explanation.risks.append("Production deployment is high risk and blocked until approval")
        explanation.rollback = "Rollback adapter is NOT_IMPLEMENTED until a concrete deployment backend is configured"
        return PlannedPipeline(pipeline=pipeline, explanation=explanation)

    def _impact_plan(self, intent: Intent, repository: RepositoryContext, principal: Principal) -> PlannedPipeline:
        step = TaskSpec(
            id="impact_analysis",
            type="diff",
            name="Determine changed files and impacted services",
            category=TaskCategory.SOURCE,
            command=["python", "-c", f"print({repository.changed_files!r})"],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python"}),
        )
        pipeline = self._base_pipeline(
            name="Impact analysis",
            repository=repository,
            principal=principal,
            stages=[PipelineStage(id="impact", name="Impact analysis", type="analysis", steps=[step])],
            intent=intent,
        )
        explanation = self._explain(pipeline, intent, repository, change="Analyze changed files and service impact")
        explanation.dependencies.extend(repository.services)
        return PlannedPipeline(pipeline=pipeline, explanation=explanation)

    def _base_pipeline(
        self,
        *,
        name: str,
        repository: RepositoryContext,
        principal: Principal,
        stages: list[PipelineStage],
        intent: Intent,
        environments: list[EnvironmentSpec] | None = None,
        approvals: list[ApprovalGate] | None = None,
    ) -> PipelineIR:
        return PipelineIR(
            metadata=PipelineMetadata(
                id=str(uuid4()),
                name=name,
                repository=repository.path,
                service=repository.services[0] if repository.services else repository.name,
                created_by=principal.id,
            ),
            triggers=[PipelineTrigger(type="manual"), PipelineTrigger(type="push", branches=["main", "master"])],
            variables={"REPOSITORY_NAME": repository.name},
            stages=stages,
            policies=["baseline-rbac", "command-safety", "secret-masking", "deployment-gates"],
            approvals=approvals or [],
            environments=environments or [],
            execution_strategy=ExecutionStrategy(mode="dag", max_parallelism=4),
            autonomy_level=intent.autonomy_level,
        )

    def _repo_inspect_step(self, repository: RepositoryContext) -> TaskSpec:
        return TaskSpec(
            id="inspect_repository",
            type="inspect",
            name="Inspect repository",
            category=TaskCategory.SOURCE,
            command=["python", "-m", "agentic_cicd.cli", "discover", ".", "--json"],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
        )

    def _secret_scan_step(self, repository: RepositoryContext) -> TaskSpec:
        return TaskSpec(
            id="secret_scan",
            type="secret_scan",
            name="Secret scan",
            category=TaskCategory.SECURITY,
            command=["python", "-m", "agentic_cicd.tools.secret_scan", "."],
            risk=RiskLevel.SAFE,
            required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
        )

    def _sbom_step(self, repository: RepositoryContext) -> TaskSpec:
        return TaskSpec(
            id="generate_sbom",
            type="sbom",
            name="Generate lightweight SBOM",
            category=TaskCategory.SECURITY,
            command=["python", "-m", "agentic_cicd.tools.sbom", "."],
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
                name="Python syntax/compile check",
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
                command=["npm", "run", "lint", "--", "--max-warnings=0"],
                risk=RiskLevel.SAFE,
                required_capabilities=RunnerCapabilityRequest(tools={"npm"}),
            )
        return None

    def _compile_step(self, repository: RepositoryContext) -> TaskSpec | None:
        if "Go" in repository.languages:
            return TaskSpec(
                id="compile",
                type="compile",
                name="Go build",
                category=TaskCategory.BUILD,
                command=["go", "build", "./..."],
                risk=RiskLevel.SAFE,
                required_capabilities=RunnerCapabilityRequest(tools={"go"}),
            )
        if "Java" in repository.languages:
            return TaskSpec(
                id="compile",
                type="compile",
                name="Maven package",
                category=TaskCategory.BUILD,
                command=["mvn", "-B", "package", "-DskipTests"],
                risk=RiskLevel.SAFE,
                required_capabilities=RunnerCapabilityRequest(tools={"mvn"}),
            )
        return None

    def _unit_test_step(self, repository: RepositoryContext) -> TaskSpec | None:
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
        if "jest" in repository.test_frameworks or "vitest" in repository.test_frameworks:
            return TaskSpec(
                id="unit_tests",
                type="unit_test",
                name="Run npm tests",
                category=TaskCategory.TEST,
                command=["npm", "test", "--", "--ci"],
                risk=RiskLevel.SAFE,
                required_capabilities=RunnerCapabilityRequest(tools={"npm"}),
            )
        if "go test" in repository.test_frameworks:
            return TaskSpec(
                id="unit_tests",
                type="unit_test",
                name="Run Go tests",
                category=TaskCategory.TEST,
                command=["go", "test", "./..."],
                risk=RiskLevel.SAFE,
                required_capabilities=RunnerCapabilityRequest(tools={"go"}),
            )
        return None

    def _explain(
        self, pipeline: PipelineIR, intent: Intent, repository: RepositoryContext, *, change: str
    ) -> PlanExplanation:
        security_checks = [step.name for step in pipeline.all_steps() if step.category == TaskCategory.SECURITY]
        verification = [step.name for step in pipeline.all_steps() if step.type == "verify"]
        risks: list[str] = []
        if repository.secret_reference_files:
            risks.append("Repository contains secret-like files; outputs must be masked and scans are required")
        if any(stage.type == "deployment" for stage in pipeline.stages):
            risks.append("Deployment adapter is not configured; generated task is a non-mutating placeholder until configured")
        return PlanExplanation(
            target=pipeline.metadata.service,
            environment=intent.environment,
            change=change,
            dependencies=repository.package_managers + repository.build_systems,
            pipeline=[stage.name for stage in pipeline.stages],
            runner="selected later by capability matching",
            security_checks=security_checks,
            approvals=[approval.name for approval in pipeline.approvals],
            blast_radius="Derived from repository services and knowledge graph; local repository scope in this phase",
            rollback="No concrete deployment backend configured; rollback is NOT_IMPLEMENTED for real deployments",
            verification=verification,
            risks=risks,
        )
