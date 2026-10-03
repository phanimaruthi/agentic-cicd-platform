# Run the autonomous SDLC dashboard demo on Windows PowerShell.
# Run from the repository root:
#   .\scripts\run_autonomous_demo.ps1

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
  Write-Host "Virtual environment not found. Run .\scripts\windows_setup.ps1 first." -ForegroundColor Red
  exit 1
}

. .\.venv\Scripts\Activate.ps1

python -m agentic_cicd.cli ui autonomous-demo --repo-path samples/python_app --execute --output reports/autonomous_sdlc_console.html

Write-Host "Demo complete. Open: reports\autonomous_sdlc_console.html" -ForegroundColor Green
