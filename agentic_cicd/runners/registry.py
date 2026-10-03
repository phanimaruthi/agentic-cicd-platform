"""Runner discovery and capability matching."""

from __future__ import annotations

from agentic_cicd.core.errors import RunnerUnavailableError
from agentic_cicd.core.task import RunnerCapabilityRequest, TaskSpec
from agentic_cicd.runners.base import Runner
import shutil

from agentic_cicd.runners.docker import DockerRunner
from agentic_cicd.runners.kubernetes import HelmRunner, KubernetesRunner
from agentic_cicd.runners.local import LocalShellRunner
from agentic_cicd.runners.mock import MockRunner
from agentic_cicd.runners.terraform import TerraformRunner


class RunnerRegistry:
    def __init__(self) -> None:
        self._runners: dict[str, Runner] = {}

    def register(self, runner: Runner) -> None:
        self._runners[runner.id] = runner

    def get(self, runner_id: str) -> Runner:
        try:
            return self._runners[runner_id]
        except KeyError as exc:
            raise RunnerUnavailableError(
                "runner is not registered", metadata={"runner_id": runner_id}
            ) from exc

    def list(self) -> list[Runner]:
        return list(self._runners.values())

    def select(self, task: TaskSpec) -> Runner:
        if task.runner:
            runner = self.get(task.runner)
            if not runner.capabilities.satisfies(task.required_capabilities):
                raise RunnerUnavailableError(
                    "specified runner does not satisfy task capabilities",
                    metadata={"task_id": task.id, "runner_id": task.runner},
                )
            return runner
        return self.select_by_capabilities(task.required_capabilities, task_id=task.id)

    def select_by_capabilities(
        self, request: RunnerCapabilityRequest, *, task_id: str | None = None
    ) -> Runner:
        candidates = [runner for runner in self._runners.values() if runner.capabilities.satisfies(request)]
        if not candidates:
            raise RunnerUnavailableError(
                "RUNNER_UNAVAILABLE",
                metadata={"task_id": task_id, "required_capabilities": request.model_dump(mode="json")},
            )
        candidates.sort(key=lambda runner: (runner.capabilities.cost_per_minute, runner.id))
        return candidates[0]


def default_runner_registry(*, include_mock: bool = False, discover_external: bool = True) -> RunnerRegistry:
    registry = RunnerRegistry()
    registry.register(LocalShellRunner())
    if discover_external:
        if shutil.which("docker"):
            registry.register(DockerRunner())
        if shutil.which("terraform"):
            registry.register(TerraformRunner(executable="terraform"))
        elif shutil.which("tofu"):
            registry.register(TerraformRunner(runner_id="opentofu-cli", executable="tofu"))
        if shutil.which("kubectl"):
            registry.register(KubernetesRunner())
        if shutil.which("helm"):
            registry.register(HelmRunner())
    if include_mock:
        registry.register(MockRunner())
    return registry
