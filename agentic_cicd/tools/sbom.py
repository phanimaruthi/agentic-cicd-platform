"""Minimal local SBOM generator for dependency inventory.

This is not a replacement for Syft/CycloneDX tooling; it provides a deterministic,
credential-free local inventory foundation and explicitly marks its output as local.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SbomComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str | None = None
    type: str = "library"
    ecosystem: str
    evidence: str


class SbomDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bom_format: str = "agentic-cicd-local-sbom"
    spec_version: str = "0.1"
    source: str
    components: list[SbomComponent] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: [
        "Local lightweight parser; use Syft/CycloneDX scanners for production attestations."
    ])


def _parse_requirement(line: str) -> tuple[str, str | None] | None:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-"):
        return None
    match = re.match(r"([A-Za-z0-9_.-]+)\s*(?:==|~=|>=|<=|>|<)?\s*([A-Za-z0-9_.!+-]+)?", line)
    if not match:
        return None
    return match.group(1), match.group(2)


def generate_sbom(root: str | Path) -> SbomDocument:
    root_path = Path(root).expanduser().resolve()
    components: list[SbomComponent] = []
    requirements = root_path / "requirements.txt"
    if requirements.exists():
        for line in requirements.read_text(encoding="utf-8", errors="ignore").splitlines():
            parsed = _parse_requirement(line)
            if parsed:
                name, version = parsed
                components.append(
                    SbomComponent(name=name, version=version, ecosystem="python", evidence="requirements.txt")
                )
    pyproject = root_path / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8", errors="ignore"))
        except tomllib.TOMLDecodeError:
            data = {}
        project = data.get("project", {}) if isinstance(data, dict) else {}
        dependency_values: list[str] = []
        if isinstance(project, dict):
            dependencies = project.get("dependencies", [])
            if isinstance(dependencies, list):
                dependency_values.extend(str(item) for item in dependencies)
            optional = project.get("optional-dependencies", {})
            if isinstance(optional, dict):
                for values in optional.values():
                    if isinstance(values, list):
                        dependency_values.extend(str(item) for item in values)
        for requirement in dependency_values:
            parsed = _parse_requirement(requirement)
            if parsed:
                name, version = parsed
                if name.lower() not in {component.name.lower() for component in components}:
                    components.append(
                        SbomComponent(name=name, version=version, ecosystem="python", evidence="pyproject.toml")
                    )
    package_json = root_path / "package.json"
    if package_json.exists():
        try:
            data: dict[str, Any] = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        for section in ("dependencies", "devDependencies"):
            dependencies = data.get(section, {})
            if isinstance(dependencies, dict):
                for name, version in dependencies.items():
                    components.append(
                        SbomComponent(name=name, version=str(version), ecosystem="npm", evidence=f"package.json:{section}")
                    )
    return SbomDocument(source=str(root_path), components=components)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    root = argv[0] if argv else "."
    print(generate_sbom(root).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
