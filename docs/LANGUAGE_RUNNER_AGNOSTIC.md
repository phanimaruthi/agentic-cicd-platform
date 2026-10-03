# v0.3 Language-Agnostic and Runner-Agnostic Planning

Version 0.3 introduces language-provider plugins and runner profiles.

## Language provider registry

The planner no longer needs to hard-code one language path. It asks the language registry which providers match the repository evidence, then composes typed tasks.

Implemented providers:

| Provider | Detects | Tasks |
|---|---|---|
| Python | `.py`, `pyproject.toml`, `requirements.txt`, pytest | pip install, compile check, pytest |
| Node.js | JS/TS, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, Jest/Vitest/scripts | install, lint, test, build |
| Go | `.go`, `go.mod` | `go test`, `go build` |
| Java | `.java`, Maven/Gradle metadata | Maven/Gradle test and package/build |

The generated tasks are still backend-neutral `TaskSpec` objects inside the `PipelineIR`.

## Runner profiles

Runner profiles describe conceptual runner capability sets:

- `local-python`
- `github-ubuntu-polyglot`
- `kubernetes-build-runner`

Profiles do not fake runner availability. They explain which task capabilities a runner environment could satisfy. Actual execution still uses registered runners and returns `RUNNER_UNAVAILABLE` if no real runner is available.

## CLI

Detect languages:

```powershell
python -m agentic_cicd.cli languages --repo-path samples/python_app --json
python -m agentic_cicd.cli languages --repo-path samples/node_app --json
python -m agentic_cicd.cli languages --repo-path samples/go_app --json
python -m agentic_cicd.cli languages --repo-path samples/java_maven_app --json
```

List runner profiles:

```powershell
python -m agentic_cicd.cli runner-profiles --json
```

Generate CI for any supported repo:

```powershell
python -m agentic_cicd.cli plan "Generate a CI pipeline" --repo-path samples/node_app --json
```

## Current limits

- Python path is fully exercised locally.
- Node/Go/Java pipeline generation is tested, but execution requires runners with `npm`/`go`/`mvn`/`gradle` installed.
- Missing tools produce `RUNNER_UNAVAILABLE` rather than fake success.
