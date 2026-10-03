# GitHub Integration Guide

This repository is ready to push to GitHub. It includes:

- local agentic CI/CD control plane code
- tests
- sample Python app
- PR/MR event simulation
- local deployment simulator
- autonomous SDLC dashboard
- GitHub Actions validation workflow

## 1. Create a GitHub repository

Create an empty repo in GitHub, for example:

```text
https://github.com/<your-org>/agentic-cicd-platform.git
```

Do not initialize it with a README because this local repo already has one.

## 2. Push this local repo

From the project root:

```powershell
git remote add origin https://github.com/<your-org>/agentic-cicd-platform.git
git branch -M main
git push -u origin main
```

If using SSH:

```powershell
git remote add origin git@github.com:<your-org>/agentic-cicd-platform.git
git branch -M main
git push -u origin main
```

## 3. GitHub Actions workflow

The included workflow lives at:

```text
.github/workflows/agentic-cicd-local-demo.yml
```

It runs on:

- pull request
- push to main/master
- manual workflow dispatch

It performs:

1. Python setup
2. dependency install
3. full test suite
4. dry-run PR-to-development agentic pipeline simulation
5. HTML report artifact upload

## 4. Connecting your application repository

There are two recommended approaches:

### Option A: Put this platform in the same repo

Copy the `agentic_cicd/`, `tests/`, `scripts/`, and `.github/workflows/` folders into your application repo and adjust `--repo-path .`.

### Option B: Keep this as a platform repo

Use it as a control-plane repository. Your application repo sends webhooks to this platform's API endpoint once deployed:

```text
POST /webhooks/pull-request
```

Production use still requires:

- webhook signature verification
- provider credentials
- checkout/mirroring of the application repository
- real deployment target configuration

## 5. Local check before pushing

```powershell
python -m pytest -q
python -m agentic_cicd.cli ui autonomous-demo --repo-path samples/python_app --execute --output reports/autonomous_sdlc_console.html
```

Open:

```text
reports\autonomous_sdlc_console.html
```
