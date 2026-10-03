# Run on Windows PowerShell

## 1. Create a virtual environment and install dependencies

From the repository root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\windows_setup.ps1
```

This installs:

- pydantic
- PyYAML
- networkx
- typer
- rich
- pytest

## 2. Run the autonomous SDLC demo

```powershell
.\scripts\run_autonomous_demo.ps1
```

Or run the command manually as a single PowerShell line:

```powershell
python -m agentic_cicd.cli ui autonomous-demo --repo-path samples/python_app --execute --output reports/autonomous_sdlc_console.html
```

Open:

```text
reports\autonomous_sdlc_console.html
```

## Important PowerShell note

Do **not** use Bash-style `\` line continuations in PowerShell.

Wrong in PowerShell:

```powershell
python -m agentic_cicd.cli ui autonomous-demo \  --repo-path samples/python_app
```

Use either a single line or PowerShell backticks:

```powershell
python -m agentic_cicd.cli ui autonomous-demo `
  --repo-path samples/python_app `
  --execute `
  --output reports/autonomous_sdlc_console.html
```

## Python version note

The project was validated in this workspace with Python 3.13. If dependency wheels are not available for Python 3.14 on your machine, install Python 3.11, 3.12, or 3.13 and create the virtual environment with that version:

```powershell
py -3.13 -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```
