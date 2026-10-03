#!/usr/bin/env bash
set -euo pipefail
if [[ ! -f .venv/bin/activate ]]; then
  echo "Virtual environment not found. Run ./scripts/unix_setup.sh first." >&2
  exit 1
fi
source .venv/bin/activate
python -m agentic_cicd.cli ui autonomous-demo --repo-path samples/python_app --execute --output reports/autonomous_sdlc_console.html
echo "Demo complete. Open: reports/autonomous_sdlc_console.html"
