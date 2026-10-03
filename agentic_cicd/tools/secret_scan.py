"""Local deterministic secret scanner.

This scanner reports file/line/rule metadata only. It does not print matched secret values.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

EXCLUDED_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "target", "__pycache__"}
PATTERNS = {
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "generic_assignment_secret": re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*=\s*['\"]?[^'\"\s]{12,}"),
    "private_key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
}


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    rule: str

    def as_dict(self) -> dict[str, object]:
        return {"file": self.file, "line": self.line, "rule": self.rule}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.stat().st_size > 1_000_000:
            continue
        yield path


def scan(root: str | Path) -> list[Finding]:
    root_path = Path(root).expanduser().resolve()
    findings: list[Finding] = []
    if not root_path.exists():
        return findings
    for path in iter_files(root_path):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for rule, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(Finding(str(path.relative_to(root_path)), line_number, rule))
    return findings


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    root = argv[0] if argv else "."
    findings = scan(root)
    print(json.dumps({"findings": [finding.as_dict() for finding in findings]}, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
