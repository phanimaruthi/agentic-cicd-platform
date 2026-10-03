"""Local artifact packaging simulator.

The package command writes a deterministic JSON artifact manifest with file hashes.
It is a local development/demo artifact, not a registry upload.
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

EXCLUDED_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "target", "__pycache__", ".agentic_cicd"}


class ArtifactFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    size_bytes: int


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    version: str
    source: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    files: list[ArtifactFile] = Field(default_factory=list)


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in EXCLUDED_DIRS for part in relative_parts):
            continue
        if path.stat().st_size > 2_000_000:
            continue
        yield path


def build_manifest(root: str | Path, *, service: str, version: str) -> ArtifactManifest:
    root_path = Path(root).expanduser().resolve()
    files: list[ArtifactFile] = []
    for path in _iter_files(root_path):
        content = path.read_bytes()
        files.append(
            ArtifactFile(
                path=str(path.relative_to(root_path)),
                sha256=hashlib.sha256(content).hexdigest(),
                size_bytes=len(content),
            )
        )
    return ArtifactManifest(service=service, version=version, source=str(root_path), files=files)


def package_artifact(root: str | Path, *, service: str, version: str, output: str | Path) -> ArtifactManifest:
    manifest = build_manifest(root, service=service, version=version)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package a local demo artifact manifest")
    parser.add_argument("command", choices=["package"])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--service", required=True)
    parser.add_argument("--version", default="local")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    manifest = package_artifact(args.repo, service=args.service, version=args.version, output=args.output)
    print(manifest.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
