"""HTML report rendering for pipeline runs with inline CSS."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from agentic_cicd.core.enums import ExecutionStatus
from agentic_cicd.core.execution import ExecutionRecord
from agentic_cicd.core.pipeline import PipelineIR
from agentic_cicd.events.models import PullRequestEvent
from agentic_cicd.orchestration.pr_pipeline import PRPipelineExplanation
from agentic_cicd.orchestration.scheduler import DagSchedule
from agentic_cicd.policies.engine import PolicyReport


STATUS_COLORS = {
    "SUCCEEDED": "#12b981",
    "FAILED": "#ef4444",
    "DENIED": "#ef4444",
    "APPROVAL_REQUIRED": "#f59e0b",
    "RUNNING": "#3b82f6",
    "PENDING": "#64748b",
    "SKIPPED": "#94a3b8",
}


def _esc(value: Any) -> str:
    return html.escape(str(value))


def render_pipeline_report(
    *,
    event: PullRequestEvent,
    pipeline: PipelineIR,
    explanation: PRPipelineExplanation,
    schedule: DagSchedule,
    policy_report: PolicyReport,
    execution: ExecutionRecord,
) -> str:
    results = {result.task_id: result for result in execution.results}
    status = execution.status.value
    color = STATUS_COLORS.get(status, "#64748b")
    decision_items = "".join(
        f"<li><strong>{_esc(decision.decision.value)}</strong> {_esc(decision.policy_id)} — {_esc(decision.reason)}</li>"
        for decision in policy_report.decisions
    )
    wave_items = "".join(
        f"<div class='wave'><div class='wave-title'>Wave {wave.index + 1}</div><div>{''.join(f'<span class=chip>{_esc(task)}</span>' for task in wave.task_ids)}</div></div>"
        for wave in schedule.waves
    )
    stage_cards = []
    for stage in pipeline.stages:
        steps = []
        for step in stage.steps:
            result = results.get(step.id)
            step_status = result.status.value if result else "PENDING"
            step_color = STATUS_COLORS.get(step_status, "#64748b")
            detail = ""
            if result:
                detail = f"exit={result.exit_code} · runner={_esc(result.runner_id)}"
            steps.append(
                f"<div class='step'><span class='dot' style='background:{step_color}'></span>"
                f"<div><div class='step-name'>{_esc(step.name)}</div><div class='muted'>{_esc(step.id)} · {_esc(step_status)} {detail}</div></div></div>"
            )
        stage_cards.append(
            f"<section class='stage'><h3>{_esc(stage.name)}</h3><div class='muted'>{_esc(stage.type)}</div>{''.join(steps)}</section>"
        )
    logs = []
    for result in execution.results:
        output = (result.stderr or result.stdout or "").strip()
        if output:
            logs.append(
                f"<details><summary>{_esc(result.task_id)} output</summary><pre>{_esc(output[-4000:])}</pre></details>"
            )
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Agentic CI/CD Pipeline Report</title>
<style>
  :root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; }}
  body {{ margin:0; background: radial-gradient(circle at top left,#203b70 0,#0f172a 32%,#020617 100%); color:#e5e7eb; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:32px; }}
  .hero {{ padding:28px; border:1px solid rgba(148,163,184,.28); border-radius:28px; background:rgba(15,23,42,.78); box-shadow:0 24px 80px rgba(0,0,0,.35); }}
  h1 {{ margin:0 0 10px; font-size:34px; letter-spacing:-.03em; }}
  h2 {{ margin-top:28px; font-size:22px; }}
  h3 {{ margin:0 0 6px; }}
  .status {{ display:inline-flex; align-items:center; gap:8px; background:{color}; color:white; padding:8px 14px; border-radius:999px; font-weight:800; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin-top:20px; }}
  .card,.stage,.wave {{ background:rgba(15,23,42,.72); border:1px solid rgba(148,163,184,.25); border-radius:20px; padding:18px; }}
  .label {{ color:#93c5fd; font-size:12px; text-transform:uppercase; letter-spacing:.12em; font-weight:800; }}
  .value {{ font-size:18px; margin-top:5px; }}
  .muted {{ color:#94a3b8; font-size:13px; }}
  .pipeline {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; }}
  .step {{ display:flex; gap:12px; align-items:flex-start; padding:12px 0; border-top:1px solid rgba(148,163,184,.14); }}
  .step:first-of-type {{ border-top:0; }}
  .step-name {{ font-weight:800; }}
  .dot {{ width:12px; height:12px; border-radius:999px; margin-top:5px; box-shadow:0 0 0 4px rgba(255,255,255,.06); flex:0 0 auto; }}
  .chip {{ display:inline-block; padding:6px 10px; margin:5px 5px 0 0; border-radius:999px; background:#172554; border:1px solid #2563eb; color:#bfdbfe; font-size:12px; font-weight:700; }}
  .wave-title {{ font-weight:900; color:#c4b5fd; margin-bottom:8px; }}
  ul {{ line-height:1.8; }}
  pre {{ white-space:pre-wrap; overflow:auto; background:#020617; padding:14px; border-radius:14px; border:1px solid rgba(148,163,184,.2); }}
  details {{ margin:10px 0; }}
  summary {{ cursor:pointer; font-weight:800; color:#bfdbfe; }}
</style>
</head>
<body>
<div class='wrap'>
  <section class='hero'>
    <div class='status'>● {_esc(status)}</div>
    <h1>Agentic CI/CD Pipeline</h1>
    <p class='muted'>Provider-neutral PR/MR event → context discovery → typed DAG → policy gates → runner execution → verification/audit.</p>
    <div class='grid'>
      <div class='card'><div class='label'>Provider</div><div class='value'>{_esc(event.provider.value)}</div></div>
      <div class='card'><div class='label'>Pull request</div><div class='value'>#{_esc(event.pr_number)} {_esc(event.title)}</div></div>
      <div class='card'><div class='label'>Mode</div><div class='value'>{_esc(explanation.mode)}</div></div>
      <div class='card'><div class='label'>Environment</div><div class='value'>{_esc(explanation.environment or 'none')}</div></div>
    </div>
  </section>

  <h2>Execution DAG</h2>
  <div class='grid'>{wave_items}</div>

  <h2>Pipeline Stages</h2>
  <div class='pipeline'>{''.join(stage_cards)}</div>

  <h2>Policy Decisions</h2>
  <section class='card'><ul>{decision_items}</ul></section>

  <h2>Explanation</h2>
  <section class='card'>
    <p><strong>Trigger:</strong> {_esc(explanation.trigger)}</p>
    <p><strong>Branches:</strong> {_esc(explanation.source_branch)} → {_esc(explanation.target_branch)}</p>
    <p><strong>Deployment:</strong> {_esc(explanation.deployment)}</p>
    <p><strong>Approval:</strong> {_esc(explanation.approval or 'not required')}</p>
    <ul>{''.join(f'<li>{_esc(note)}</li>' for note in explanation.notes)}</ul>
  </section>

  <h2>Task Output</h2>
  <section class='card'>{''.join(logs) or '<p class=muted>No task output captured.</p>'}</section>
</div>
</body>
</html>"""


def write_pipeline_report(path: str | Path, **kwargs: Any) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_pipeline_report(**kwargs), encoding="utf-8")
    return output
