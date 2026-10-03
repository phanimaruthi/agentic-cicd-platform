#!/usr/bin/env bash
set -euo pipefail
python --version
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest -q
printf '\nSetup complete. Activate with: source .venv/bin/activate\n'
