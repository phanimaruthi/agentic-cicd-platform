# Windows PowerShell setup for the Agentic CI/CD demo.
# Run from the repository root:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\scripts\windows_setup.ps1

$ErrorActionPreference = "Stop"

Write-Host "[agentic-cicd] Python version:" -ForegroundColor Cyan
python --version

if (-not (Test-Path ".venv")) {
  Write-Host "[agentic-cicd] Creating virtual environment .venv" -ForegroundColor Cyan
  python -m venv .venv
}

Write-Host "[agentic-cicd] Activating virtual environment" -ForegroundColor Cyan
. .\.venv\Scripts\Activate.ps1

Write-Host "[agentic-cicd] Upgrading pip" -ForegroundColor Cyan
python -m pip install --upgrade pip

Write-Host "[agentic-cicd] Installing dependencies" -ForegroundColor Cyan
python -m pip install -r requirements-dev.txt

Write-Host "[agentic-cicd] Verifying imports" -ForegroundColor Cyan
python - <<'PY'
import pydantic, yaml, networkx, typer, rich
print('dependencies ok')
PY

Write-Host "[agentic-cicd] Running tests" -ForegroundColor Cyan
python -m pytest -q

Write-Host "[agentic-cicd] Setup complete. To activate later run:" -ForegroundColor Green
Write-Host "  . .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
