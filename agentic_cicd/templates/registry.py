"""In-memory golden-path template registry."""

from __future__ import annotations

from agentic_cicd.core.enums import RiskLevel, TaskCategory
from agentic_cicd.core.pipeline import PipelineIR, PipelineMetadata, PipelineStage, PipelineTrigger
from agentic_cicd.core.task import RunnerCapabilityRequest, TaskSpec
from agentic_cicd.templates.models import PipelineTemplate, TemplateParameter


class TemplateRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, PipelineTemplate] = {}

    def register(self, template: PipelineTemplate) -> None:
        self._templates[template.id] = template

    def get(self, template_id: str) -> PipelineTemplate:
        return self._templates[template_id]

    def list(self, *, tag: str | None = None, approved_only: bool = True) -> list[PipelineTemplate]:
        templates = list(self._templates.values())
        if approved_only:
            templates = [template for template in templates if template.approved]
        if tag:
            templates = [template for template in templates if tag in template.tags]
        return templates


def python_ci_template() -> PipelineTemplate:
    pipeline = PipelineIR(
        metadata=PipelineMetadata(name="Python CI Golden Path"),
        triggers=[PipelineTrigger(type="manual"), PipelineTrigger(type="push", branches=["main"])],
        stages=[
            PipelineStage(
                id="quality",
                name="Quality",
                type="quality",
                steps=[
                    TaskSpec(
                        id="install_dependencies",
                        type="install_dependencies",
                        name="Install dependencies",
                        category=TaskCategory.BUILD,
                        command=["python", "-m", "pip", "install", "-e", "."],
                        risk=RiskLevel.LOW_RISK,
                        required_capabilities=RunnerCapabilityRequest(tools={"python"}),
                    ),
                    TaskSpec(
                        id="lint",
                        type="lint",
                        name="Compile check",
                        category=TaskCategory.TEST,
                        command=["python", "-m", "compileall", "-q", "."],
                        risk=RiskLevel.SAFE,
                        required_capabilities=RunnerCapabilityRequest(tools={"python"}),
                    ),
                ],
            ),
            PipelineStage(
                id="test",
                name="Test",
                type="test",
                dependencies=["quality"],
                steps=[
                    TaskSpec(
                        id="unit_tests",
                        type="unit_test",
                        name="Unit tests",
                        category=TaskCategory.TEST,
                        command=["python", "-m", "pytest", "-q"],
                        risk=RiskLevel.SAFE,
                        required_capabilities=RunnerCapabilityRequest(tools={"python"}),
                    )
                ],
            ),
            PipelineStage(
                id="security",
                name="Security",
                type="security",
                dependencies=["quality"],
                steps=[
                    TaskSpec(
                        id="secret_scan",
                        type="secret_scan",
                        name="Secret scan",
                        category=TaskCategory.SECURITY,
                        command=["python", "-m", "agentic_cicd.tools.secret_scan", "."],
                        risk=RiskLevel.SAFE,
                        required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
                    ),
                    TaskSpec(
                        id="generate_sbom",
                        type="sbom",
                        name="Generate SBOM",
                        category=TaskCategory.SECURITY,
                        command=["python", "-m", "agentic_cicd.tools.sbom", "."],
                        risk=RiskLevel.SAFE,
                        required_capabilities=RunnerCapabilityRequest(tools={"python", "agentic-cicd-internal"}),
                    ),
                ],
            ),
        ],
        policies=["baseline-rbac", "command-safety", "secret-masking", "security-scan-required"],
    )
    return PipelineTemplate(
        id="python-ci",
        name="Python CI",
        version="0.1.0",
        description="Approved golden path for Python repositories using pytest.",
        parameters=[TemplateParameter(name="service", required=False, description="Service name")],
        tags={"python", "ci", "security"},
        pipeline=pipeline,
    )


def default_template_registry() -> TemplateRegistry:
    registry = TemplateRegistry()
    registry.register(python_ci_template())
    return registry
