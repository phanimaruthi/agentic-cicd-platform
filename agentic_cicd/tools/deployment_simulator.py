"""Local deployment simulator for safe end-to-end demos.

This intentionally writes local state only. It does not contact Kubernetes, cloud,
registries, or production systems.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class DeploymentState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deployment_id: str = Field(default_factory=lambda: str(uuid4()))
    service: str
    environment: str
    artifact: str
    version: str = "local"
    status: str = "healthy"
    strategy: str = "rolling"
    deployed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    health: dict[str, float | str] = Field(default_factory=lambda: {"error_rate": 0.0, "p95_latency_ms": 100.0})


def _state_file(state_dir: str | Path, service: str, environment: str) -> Path:
    return Path(state_dir).expanduser().resolve() / environment / f"{service}.json"


def deploy(
    *,
    service: str,
    environment: str,
    artifact: str,
    version: str = "local",
    state_dir: str | Path = ".agentic_cicd/deployments",
    strategy: str = "rolling",
) -> DeploymentState:
    artifact_path = Path(artifact)
    if not artifact_path.exists():
        raise FileNotFoundError(f"artifact does not exist: {artifact}")
    state = DeploymentState(
        service=service,
        environment=environment,
        artifact=str(artifact_path),
        version=version,
        strategy=strategy,
    )
    path = _state_file(state_dir, service, environment)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return state


def verify(
    *,
    service: str,
    environment: str,
    state_dir: str | Path = ".agentic_cicd/deployments",
) -> DeploymentState:
    path = _state_file(state_dir, service, environment)
    if not path.exists():
        raise FileNotFoundError(f"deployment state does not exist: {path}")
    state = DeploymentState.model_validate_json(path.read_text(encoding="utf-8"))
    if state.status != "healthy":
        raise RuntimeError(f"deployment is not healthy: {state.status}")
    return state


def rollback(
    *,
    service: str,
    environment: str,
    state_dir: str | Path = ".agentic_cicd/deployments",
) -> DeploymentState:
    path = _state_file(state_dir, service, environment)
    if not path.exists():
        raise FileNotFoundError(f"deployment state does not exist: {path}")
    state = DeploymentState.model_validate_json(path.read_text(encoding="utf-8"))
    state.status = "rolled_back"
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local deployment simulator")
    parser.add_argument("command", choices=["deploy", "verify", "rollback"])
    parser.add_argument("--service", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--artifact", default="")
    parser.add_argument("--version", default="local")
    parser.add_argument("--state-dir", default=".agentic_cicd/deployments")
    parser.add_argument("--strategy", default="rolling")
    args = parser.parse_args(argv)
    if args.command == "deploy":
        state = deploy(
            service=args.service,
            environment=args.environment,
            artifact=args.artifact,
            version=args.version,
            state_dir=args.state_dir,
            strategy=args.strategy,
        )
    elif args.command == "verify":
        state = verify(service=args.service, environment=args.environment, state_dir=args.state_dir)
    else:
        state = rollback(service=args.service, environment=args.environment, state_dir=args.state_dir)
    print(state.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
