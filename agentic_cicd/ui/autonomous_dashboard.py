"""Original enterprise SDLC dashboard renderer.

The design is inspired by common autonomous SDLC platform patterns, but it is not a
copy of any vendor's protected UI/trade dress. It renders our actual typed pipeline,
policy, execution, and deployment data into a polished standalone HTML console.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Iterable

from agentic_cicd.core.enums import ExecutionStatus
from agentic_cicd.core.execution import TaskExecutionResult
from agentic_cicd.events.models import PullRequestEvent
from agentic_cicd.orchestration.control_plane import PipelineRunBundle


STATUS_COLORS = {
    "SUCCEEDED": "#18d399",
    "FAILED": "#ff5c7a",
    "DENIED": "#ff5c7a",
    "APPROVAL_REQUIRED": "#ffb020",
    "RUNNING": "#5aa7ff",
    "PENDING": "#8fa3bf",
    "SKIPPED": "#64748b",
    "COMPLETED": "#18d399",
    "WARN": "#ffb020",
    "NOT_CONFIGURED": "#a78bfa",
}


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _status_class(status: str) -> str:
    return status.lower().replace("_", "-")


def _by_id(results: Iterable[TaskExecutionResult]) -> dict[str, TaskExecutionResult]:
    return {result.task_id: result for result in results}


def _group_status(results: dict[str, TaskExecutionResult], task_ids: list[str], *, approval_required: bool = False) -> str:
    if approval_required:
        return "APPROVAL_REQUIRED"
    selected = [results[task_id] for task_id in task_ids if task_id in results]
    if not selected:
        return "PENDING"
    if any(result.status == ExecutionStatus.FAILED for result in selected):
        return "FAILED"
    if any(result.status == ExecutionStatus.SKIPPED for result in selected):
        return "SKIPPED"
    if all(result.status == ExecutionStatus.SUCCEEDED for result in selected):
        return "SUCCEEDED"
    return "RUNNING"


def _duration_ms(results: list[TaskExecutionResult]) -> int:
    return sum(result.duration_ms or 0 for result in results)


def _agent_cards(bundle: PipelineRunBundle) -> list[dict[str, str]]:
    results = _by_id(bundle.execution.results)
    approval_required = bundle.execution.status == ExecutionStatus.APPROVAL_REQUIRED
    return [
        {
            "name": "Repository Intelligence Agent",
            "domain": "Context",
            "status": _group_status(results, ["inspect_repository"], approval_required=approval_required),
            "thought": "Mapping repository topology, languages, tests, services, and changed files.",
            "outcome": "Repository context captured with provenance and untrusted-content boundaries.",
        },
        {
            "name": "Software Delivery Agent",
            "domain": "Build + Test",
            "status": _group_status(results, ["install_dependencies", "lint", "unit_tests"], approval_required=approval_required),
            "thought": "Selecting the safest build/test path from discovered repository evidence.",
            "outcome": "Quality gates executed through typed runners; no model output was executed directly.",
        },
        {
            "name": "Security Testing Agent",
            "domain": "Security",
            "status": _group_status(results, ["secret_scan", "generate_sbom"], approval_required=approval_required),
            "thought": "Verifying that required checks ran and supply-chain inventory exists.",
            "outcome": "Secret scan and local SBOM completed where permitted; advanced scanners show as not configured.",
        },
        {
            "name": "Release / Deployment Agent",
            "domain": "Delivery",
            "status": _group_status(results, ["package_artifact", "deploy_development", "deploy_staging", "deploy_production"], approval_required=approval_required),
            "thought": "Evaluating environment gates, blast radius, artifact, rollback, and verification requirements.",
            "outcome": bundle.explanation.deployment,
        },
        {
            "name": "SRE Verification Agent",
            "domain": "Health",
            "status": _group_status(results, ["verify_development", "verify_staging", "verify_production"], approval_required=approval_required),
            "thought": "Comparing observed deployment state against required health signals.",
            "outcome": "Health verification is local/simulated unless an observability provider is configured.",
        },
        {
            "name": "Governance Agent",
            "domain": "Policy",
            "status": "APPROVAL_REQUIRED" if approval_required else "SUCCEEDED" if not bundle.policy_report.denied else "DENIED",
            "thought": "Enforcing RBAC, environment gates, command risk, and deployment approvals.",
            "outcome": "Policy decisions are auditable and independent of model reasoning.",
        },
    ]


def _render_agent_cards(bundle: PipelineRunBundle) -> str:
    cards = []
    for index, card in enumerate(_agent_cards(bundle), start=1):
        status = card["status"]
        color = STATUS_COLORS.get(status, "#8fa3bf")
        cards.append(
            f"""
            <article class="agent-card">
              <div class="agent-head">
                <div class="agent-icon">{index}</div>
                <div><h3>{_esc(card['name'])}</h3><p>{_esc(card['domain'])}</p></div>
                <span class="status-pill" style="--status:{color}">{_esc(status)}</span>
              </div>
              <div class="thinking"><span class="pulse"></span><strong>Thinking</strong><p>{_esc(card['thought'])}</p></div>
              <div class="agent-outcome">{_esc(card['outcome'])}</div>
            </article>
            """
        )
    return "".join(cards)


def _render_pipeline_graph(bundle: PipelineRunBundle) -> str:
    columns = []
    for wave in bundle.schedule.waves:
        chips = "".join(f"<span>{_esc(task_id)}</span>" for task_id in wave.task_ids)
        columns.append(f"<div class='graph-wave'><b>Wave {wave.index + 1}</b><div>{chips}</div></div>")
    return "".join(columns)


def _render_stage_table(bundle: PipelineRunBundle) -> str:
    results = _by_id(bundle.execution.results)
    rows = []
    for stage in bundle.pipeline.stages:
        for task in stage.steps:
            result = results.get(task.id)
            status = result.status.value if result else "PENDING"
            color = STATUS_COLORS.get(status, "#8fa3bf")
            runner = result.runner_id if result else "not selected"
            exit_code = "—" if result is None or result.exit_code is None else str(result.exit_code)
            rows.append(
                f"<tr><td>{_esc(stage.name)}</td><td>{_esc(task.name)}</td><td><span class='mini-status' style='--status:{color}'>{_esc(status)}</span></td><td>{_esc(runner)}</td><td>{_esc(exit_code)}</td><td>{_esc(task.risk.value)}</td></tr>"
            )
    return "".join(rows)


def _render_policy(bundle: PipelineRunBundle) -> str:
    items = []
    for decision in bundle.policy_report.decisions:
        color = STATUS_COLORS.get(decision.decision.value, "#8fa3bf")
        items.append(
            f"<li><span class='mini-status' style='--status:{color}'>{_esc(decision.decision.value)}</span><strong>{_esc(decision.policy_id)}</strong><p>{_esc(decision.reason)}</p></li>"
        )
    return "".join(items)


def _render_security_matrix(bundle: PipelineRunBundle) -> str:
    results = _by_id(bundle.execution.results)
    checks = [
        ("Secret scan", "secret_scan", "Implemented", "Repository secret-like pattern scan"),
        ("SBOM", "generate_sbom", "Implemented", "Local dependency inventory"),
        ("SAST", None, "NOT_CONFIGURED", "Adapter interface planned; no fake scan result"),
        ("Container scan", None, "NOT_CONFIGURED", "Requires Trivy/Snyk/etc. connector"),
        ("Artifact signing", None, "NOT_CONFIGURED", "Requires signing/provenance connector"),
    ]
    rows = []
    for name, task_id, fallback, description in checks:
        status = results[task_id].status.value if task_id and task_id in results else fallback
        color = STATUS_COLORS.get(status, "#a78bfa")
        rows.append(
            f"<tr><td>{_esc(name)}</td><td><span class='mini-status' style='--status:{color}'>{_esc(status)}</span></td><td>{_esc(description)}</td></tr>"
        )
    return "".join(rows)


def _render_knowledge_graph(bundle: PipelineRunBundle) -> str:
    event = bundle.event
    service = bundle.pipeline.metadata.service or "service"
    environment = bundle.explanation.environment or "validation-only"
    artifact = "artifact manifest" if any(result.task_id == "package_artifact" for result in bundle.execution.results) else "artifact planned"
    nodes = [
        (70, 90, "PR/MR", f"#{event.pr_number}"),
        (230, 90, "Commit", event.commit_sha or "local"),
        (390, 90, "Repository", event.repository),
        (550, 90, "Service", service),
        (710, 90, "Pipeline", bundle.pipeline.metadata.name),
        (390, 230, "Artifact", artifact),
        (550, 230, "Environment", environment),
        (710, 230, "Audit", bundle.execution.status.value),
    ]
    edges = [
        (130, 90, 170, 90),
        (290, 90, 330, 90),
        (450, 90, 490, 90),
        (610, 90, 650, 90),
        (550, 124, 430, 196),
        (450, 230, 490, 230),
        (610, 230, 650, 230),
    ]
    edge_svg = "".join(f"<line x1='{a}' y1='{b}' x2='{c}' y2='{d}' />" for a, b, c, d in edges)
    node_svg = "".join(
        f"<g><rect x='{x-58}' y='{y-34}' width='116' height='68' rx='16'/><text x='{x}' y='{y-6}'>{_esc(title)}</text><text class='sub' x='{x}' y='{y+17}'>{_esc(label)[:20]}</text></g>"
        for x, y, title, label in nodes
    )
    return f"<svg class='kg' viewBox='0 0 790 300' role='img'>{edge_svg}{node_svg}</svg>"


def _render_logs(bundle: PipelineRunBundle) -> str:
    details = []
    for result in bundle.execution.results:
        output = (result.stderr or result.stdout or "").strip()
        if output:
            details.append(
                f"<details><summary>{_esc(result.task_id)} output</summary><pre>{_esc(output[-3000:])}</pre></details>"
            )
    return "".join(details) or "<p class='muted'>No task output captured.</p>"


def render_autonomous_sdlc_console(bundle: PipelineRunBundle) -> str:
    event = bundle.event
    status = bundle.execution.status.value
    status_color = STATUS_COLORS.get(status, "#8fa3bf")
    total_tasks = sum(len(stage.steps) for stage in bundle.pipeline.stages)
    passed = sum(1 for result in bundle.execution.results if result.status == ExecutionStatus.SUCCEEDED)
    duration = _duration_ms(bundle.execution.results)
    decisions = len(bundle.policy_report.decisions)
    deployment_target = bundle.explanation.environment or "none"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Autonomous SDLC Control Plane</title>
<style>
:root {{
  --bg:#050816; --panel:rgba(13,18,38,.78); --panel2:rgba(20,28,55,.86); --line:rgba(148,163,184,.2);
  --text:#eef4ff; --muted:#8ea2c6; --blue:#6aa8ff; --violet:#9b7cff; --green:#18d399; --pink:#ff5caa;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; color:var(--text); min-height:100vh; background:
  radial-gradient(circle at 15% -10%, rgba(82,110,255,.42), transparent 34%),
  radial-gradient(circle at 85% 10%, rgba(255,92,170,.25), transparent 30%),
  linear-gradient(135deg,#050816 0%,#08111f 45%,#0f172a 100%); }}
.shell {{ display:grid; grid-template-columns:270px 1fr; min-height:100vh; }}
.sidebar {{ padding:28px 22px; border-right:1px solid var(--line); background:rgba(2,6,23,.52); backdrop-filter:blur(20px); position:sticky; top:0; height:100vh; }}
.brand {{ display:flex; gap:12px; align-items:center; margin-bottom:30px; }}
.logo {{ width:42px; height:42px; border-radius:14px; background:linear-gradient(135deg,var(--blue),var(--violet),var(--pink)); box-shadow:0 0 35px rgba(106,168,255,.45); }}
.brand h1 {{ font-size:17px; margin:0; letter-spacing:-.02em; }}
.brand p {{ margin:2px 0 0; color:var(--muted); font-size:12px; }}
.nav a {{ display:flex; align-items:center; gap:10px; padding:12px 14px; border-radius:14px; color:#cbd5e1; text-decoration:none; margin:7px 0; }}
.nav a.active,.nav a:hover {{ background:rgba(106,168,255,.13); color:white; }}
.main {{ padding:28px; }}
.hero {{ border:1px solid var(--line); border-radius:30px; padding:28px; background:linear-gradient(135deg,rgba(19,33,68,.85),rgba(12,17,34,.78)); box-shadow:0 26px 80px rgba(0,0,0,.32); overflow:hidden; position:relative; }}
.hero:after {{ content:""; position:absolute; right:-120px; top:-120px; width:340px; height:340px; background:radial-gradient(circle,rgba(106,168,255,.28),transparent 70%); }}
.hero-top {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-start; position:relative; z-index:1; }}
.eyebrow {{ color:#93c5fd; font-size:12px; text-transform:uppercase; letter-spacing:.16em; font-weight:900; }}
.hero h2 {{ font-size:42px; line-height:1; letter-spacing:-.055em; margin:10px 0 12px; max-width:760px; }}
.hero p {{ color:#b6c4dc; max-width:780px; line-height:1.6; }}
.status-big {{ display:inline-flex; align-items:center; gap:10px; padding:10px 16px; border-radius:999px; background:{status_color}; color:#04111f; font-weight:950; box-shadow:0 0 35px color-mix(in srgb,{status_color},transparent 55%); }}
.metrics {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:14px; margin-top:22px; position:relative; z-index:1; }}
.metric {{ background:rgba(2,6,23,.44); border:1px solid var(--line); border-radius:20px; padding:16px; }}
.metric b {{ display:block; font-size:23px; margin-top:4px; }}
.metric span {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.12em; }}
.section-title {{ display:flex; justify-content:space-between; align-items:end; margin:30px 0 14px; }}
.section-title h2 {{ margin:0; font-size:24px; letter-spacing:-.03em; }}
.muted {{ color:var(--muted); }}
.agent-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; }}
.agent-card,.panel {{ background:var(--panel); border:1px solid var(--line); border-radius:24px; padding:18px; box-shadow:0 18px 50px rgba(0,0,0,.22); }}
.agent-head {{ display:flex; gap:12px; align-items:flex-start; }}
.agent-icon {{ width:38px; height:38px; border-radius:13px; background:linear-gradient(135deg,rgba(106,168,255,.95),rgba(155,124,255,.95)); display:grid; place-items:center; font-weight:950; }}
.agent-head h3 {{ margin:0; font-size:16px; }}
.agent-head p {{ margin:3px 0 0; color:var(--muted); font-size:12px; }}
.status-pill,.mini-status {{ margin-left:auto; border-radius:999px; padding:6px 10px; background:color-mix(in srgb,var(--status),transparent 82%); color:var(--status); border:1px solid color-mix(in srgb,var(--status),transparent 55%); font-size:11px; font-weight:950; }}
.thinking {{ margin:16px 0; padding:14px; background:rgba(106,168,255,.08); border:1px solid rgba(106,168,255,.16); border-radius:18px; }}
.thinking p {{ margin:7px 0 0; color:#cbd5e1; font-size:13px; line-height:1.5; }}
.pulse {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--green); margin-right:8px; box-shadow:0 0 0 6px rgba(24,211,153,.13); }}
.agent-outcome {{ color:#dbeafe; font-size:13px; line-height:1.55; }}
.two-col {{ display:grid; grid-template-columns:1.12fr .88fr; gap:16px; }}
.pipeline-graph {{ display:flex; gap:14px; align-items:stretch; overflow:auto; padding-bottom:6px; }}
.graph-wave {{ min-width:170px; border-radius:18px; padding:14px; background:rgba(15,23,42,.72); border:1px solid var(--line); position:relative; }}
.graph-wave:not(:last-child):after {{ content:"→"; position:absolute; right:-13px; top:42%; color:#93c5fd; font-weight:900; }}
.graph-wave b {{ color:#bfdbfe; }}
.graph-wave span {{ display:block; margin-top:8px; padding:8px 10px; border-radius:12px; background:rgba(106,168,255,.09); border:1px solid rgba(106,168,255,.17); color:#e0f2fe; font-size:12px; }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ text-align:left; border-bottom:1px solid rgba(148,163,184,.13); padding:12px 8px; font-size:13px; vertical-align:top; }}
th {{ color:#93c5fd; font-size:11px; text-transform:uppercase; letter-spacing:.12em; }}
.policy-list {{ margin:0; padding:0; list-style:none; }}
.policy-list li {{ padding:13px 0; border-bottom:1px solid rgba(148,163,184,.13); }}
.policy-list strong {{ margin-left:8px; }}
.policy-list p {{ margin:7px 0 0; color:var(--muted); line-height:1.45; }}
.kg {{ width:100%; min-height:260px; }}
.kg line {{ stroke:#5073be; stroke-width:2; stroke-dasharray:5 5; }}
.kg rect {{ fill:rgba(15,23,42,.88); stroke:rgba(106,168,255,.42); }}
.kg text {{ fill:#e0f2fe; font-size:12px; text-anchor:middle; font-weight:850; }}
.kg .sub {{ fill:#93a4bd; font-size:10px; font-weight:600; }}
.chat {{ border-radius:24px; padding:18px; background:linear-gradient(135deg,rgba(106,168,255,.12),rgba(155,124,255,.08)); border:1px solid rgba(106,168,255,.18); }}
.chat .q {{ color:white; font-weight:850; }}
.chat .a {{ margin-top:12px; color:#c7d2fe; line-height:1.6; }}
pre {{ white-space:pre-wrap; overflow:auto; background:#020617; padding:14px; border-radius:16px; border:1px solid rgba(148,163,184,.2); max-height:320px; }}
details {{ margin:10px 0; }} summary {{ cursor:pointer; color:#bfdbfe; font-weight:900; }}
.footer {{ margin:30px 0 10px; color:#7d8da8; text-align:center; font-size:12px; }}
@media (max-width:1100px) {{ .shell {{ grid-template-columns:1fr; }} .sidebar {{ position:relative; height:auto; }} .metrics,.agent-grid,.two-col {{ grid-template-columns:1fr; }} .hero-top {{ flex-direction:column; }} }}
</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="brand"><div class="logo"></div><div><h1>Agentic SDLC</h1><p>Autonomous delivery control plane</p></div></div>
    <nav class="nav">
      <a class="active" href="#overview">✦ Overview</a>
      <a href="#agents">🤖 Agents</a>
      <a href="#pipeline">⚙ Pipeline</a>
      <a href="#governance">🛡 Governance</a>
      <a href="#knowledge">◎ Knowledge Graph</a>
      <a href="#logs">▣ Logs</a>
    </nav>
  </aside>
  <main class="main">
    <section id="overview" class="hero">
      <div class="hero-top">
        <div>
          <div class="eyebrow">AI platform for the autonomous SDLC</div>
          <h2>Ship every pull request through governed agentic delivery.</h2>
          <p>Provider-neutral trigger from {_esc(event.provider.value)} PR/MR #{_esc(event.pr_number)}. The control plane discovered context, built a typed DAG, evaluated policy, selected runners, executed tasks, and verified delivery state.</p>
        </div>
        <div class="status-big">● {_esc(status)}</div>
      </div>
      <div class="metrics">
        <div class="metric"><span>Tasks passed</span><b>{passed}/{total_tasks}</b></div>
        <div class="metric"><span>Policy decisions</span><b>{decisions}</b></div>
        <div class="metric"><span>Environment</span><b>{_esc(deployment_target)}</b></div>
        <div class="metric"><span>Runner time</span><b>{duration}ms</b></div>
        <div class="metric"><span>Autonomy</span><b>Level 2</b></div>
      </div>
    </section>

    <div id="agents" class="section-title"><div><h2>Agent Orchestration</h2><p class="muted">Specialized agents reason, but typed tools and policies execute.</p></div></div>
    <section class="agent-grid">{_render_agent_cards(bundle)}</section>

    <div id="pipeline" class="section-title"><div><h2>Pipeline Mechanism</h2><p class="muted">DAG waves expose parallelism while preserving dependencies.</p></div></div>
    <section class="panel"><div class="pipeline-graph">{_render_pipeline_graph(bundle)}</div></section>

    <div class="two-col" style="margin-top:16px;">
      <section class="panel"><h2>Execution Matrix</h2><table><thead><tr><th>Stage</th><th>Task</th><th>Status</th><th>Runner</th><th>Exit</th><th>Risk</th></tr></thead><tbody>{_render_stage_table(bundle)}</tbody></table></section>
      <section id="governance" class="panel"><h2>Risk + Governance</h2><ul class="policy-list">{_render_policy(bundle)}</ul></section>
    </div>

    <div class="two-col" style="margin-top:16px;">
      <section class="panel"><h2>Security Coverage</h2><table><thead><tr><th>Control</th><th>Status</th><th>Evidence</th></tr></thead><tbody>{_render_security_matrix(bundle)}</tbody></table></section>
      <section class="panel"><h2>Ask the SDLC Agent</h2><div class="chat"><div class="q">What happened in this delivery?</div><div class="a">The system validated PR #{_esc(event.pr_number)}, ran build/test/security tasks, produced an artifact manifest, {_esc(bundle.explanation.deployment.lower())} Policy outcome: {_esc(status)}. No external credentials or unimplemented provider actions were fabricated.</div></div></section>
    </div>

    <div id="knowledge" class="section-title"><div><h2>SDLC Knowledge Graph</h2><p class="muted">Lineage from PR to artifact, environment, and audit outcome.</p></div></div>
    <section class="panel">{_render_knowledge_graph(bundle)}</section>

    <div id="logs" class="section-title"><div><h2>Execution Logs</h2><p class="muted">Outputs are captured as data and secret-masked where applicable.</p></div></div>
    <section class="panel">{_render_logs(bundle)}</section>

    <div class="footer">Original Agentic SDLC dashboard. Similar enterprise concepts, not a copy of any vendor UI.</div>
  </main>
</div>
</body>
</html>"""


def write_autonomous_sdlc_console(path: str | Path, bundle: PipelineRunBundle) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_autonomous_sdlc_console(bundle), encoding="utf-8")
    return output
