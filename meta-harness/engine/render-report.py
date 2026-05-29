#!/usr/bin/env python3
"""render-report.py — Generate human-facing meta-review report (v0.3).

Two-layer report: rule findings + semantic judgements + candidate repairs
+ prediction contracts + contract replay + experience signals + recommended next patch.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter


CATEGORY_ORDER = [
    "token_waste",
    "ai_guidance_gap",
    "delivery_quality_risk",
    "missing_evaluator_coverage",
    "tool_efficiency_risk",
    "runtime_observability_risk",
]

CATEGORY_LABELS = {
    "token_waste": "Token Waste Findings",
    "ai_guidance_gap": "AI Guidance Gaps",
    "delivery_quality_risk": "Delivery Quality Risks",
    "missing_evaluator_coverage": "Missing Evaluator Coverage",
    "tool_efficiency_risk": "Tool Efficiency Risks",
    "runtime_observability_risk": "Runtime Observability Risks",
}

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_findings_section(findings: list[dict], category: str) -> str:
    cat_findings = [f for f in findings if f.get("category") == category]
    cat_findings.sort(key=lambda f: SEVERITY_ORDER.get(f.get("severity", "medium"), 1))

    if not cat_findings:
        return f"### {CATEGORY_LABELS.get(category, category)}\n\nNo findings in this category.\n"

    lines = [f"### {CATEGORY_LABELS.get(category, category)}\n"]
    for f in cat_findings:
        sev = f.get("severity", "medium").upper()
        lines.append(f"**[{sev}]** {f.get('title', 'Untitled finding')}")
        lines.append(f"- Evidence: {f.get('evidence', 'N/A')[:200]}")
        lines.append(f"- Files: {', '.join(f.get('evidence_files', []))}")
        lines.append(f"- Action: {f.get('proposed_action', 'N/A')}")
        lines.append(f"- Gap type: {f.get('gap_type', 'N/A')}")
        lines.append("")
    return "\n".join(lines)


def infer_run_id_from_path(path: str) -> str:
    parts = Path(path).parts
    for part in parts:
        if part.startswith("run-"):
            return part
    return ""


def render_current_run_tool_status(signals_dir: Path, findings: list[dict]) -> str:
    logs = load_json(signals_dir / "automation_logs.json") or []
    run_metrics = load_json(signals_dir / "run_metrics.json") or []
    lines = ["### Current Run Tool Status\n"]

    if not logs and not run_metrics:
        lines.append("No automation role logs or run metrics were collected.\n")
        return "\n".join(lines)

    latest_metric = None
    if run_metrics:
        latest_metric = sorted(
            run_metrics,
            key=lambda r: (r.get("latest_mtime", 0), r.get("run_id", "")),
            reverse=True,
        )[0]

    latest_run = latest_metric.get("run_id", "") if latest_metric else logs[0].get("run_id", "")
    latest_logs = [log for log in logs if log.get("run_id") == latest_run]
    current_error_windows = sum(len(log.get("error_windows", []) or []) for log in latest_logs)
    current_tool_error_count = int(latest_metric.get("tool_error_count", 0)) if latest_metric else current_error_windows
    current_tool_findings = []
    historical_tool_findings = []
    for finding in findings:
        if finding.get("category") != "tool_efficiency_risk":
            continue
        evidence_runs = {infer_run_id_from_path(path) for path in finding.get("evidence_files", [])}
        if latest_run in evidence_runs:
            current_tool_findings.append(finding)
        else:
            historical_tool_findings.append(finding)

    lines.append(f"- Latest run: `{latest_run}`")
    lines.append(f"- Latest run role logs collected: {len(latest_logs)}")
    lines.append(f"- Latest run tool-error windows: {current_error_windows}")
    if latest_metric:
        lines.append(f"- Latest run raw tool-error count: {current_tool_error_count}")
    if current_error_windows == 0 and current_tool_error_count == 0 and not current_tool_findings:
        lines.append("- Status: **CURRENT PASS** - no tool-output errors detected in the latest run.")
    else:
        lines.append("- Status: **CURRENT FAIL** - latest run still has tool-output errors or tool-efficiency findings.")

    if historical_tool_findings:
        lines.append(f"- Historical sampled tool findings: {len(historical_tool_findings)}")
        lines.append("- Interpretation: sampled older logs still contain tool debt; do not treat this alone as latest-run failure.")
    else:
        lines.append("- Historical sampled tool findings: 0")

    latest_content = "\n".join(log.get("content", "") for log in latest_logs)
    if "--SpecFile" in latest_content:
        lines.append("- Uses `new_task_brief.py --SpecFile`: yes")
    if "--Task <NNN>" in latest_content or "new_review_draft.py --Task" in latest_content:
        lines.append("- Uses `new_review_draft.py --Task <NNN>` guidance: yes")
    lines.append("")
    return "\n".join(lines)


def format_duration_ms(duration_ms: int | float) -> str:
    return f"{float(duration_ms) / 1000:.1f}s"


def render_runtime_profile(signals_dir: Path) -> str:
    trace = load_json(signals_dir / "runtime_trace.json") or {}
    lines = ["### Runtime Profile\n"]

    if not trace or not trace.get("phase_summary"):
        lines.append("No runtime trace collected yet.\n")
        return "\n".join(lines)

    lines.append(f"- Latest traced run: `{trace.get('latest_run_id', '')}`")
    lines.append(f"- Runs analyzed: {trace.get('runs_analyzed', 0)}")
    lines.append(f"- Total traced duration: {format_duration_ms(trace.get('total_duration_ms', 0))}")
    lines.append("")

    critical_path = trace.get("critical_path", []) or []
    if critical_path:
        lines.append("Critical path:")
        for span in critical_path[:5]:
            lines.append(
                f"- {span.get('phase', 'unknown')} "
                f"({span.get('round_id', '')}/{span.get('role', '')}): "
                f"{format_duration_ms(span.get('duration_ms', 0))}, status={span.get('status', 'unknown')}"
            )
        lines.append("")

    phase_summary = trace.get("phase_summary", {}) or {}
    if phase_summary:
        lines.append("Phase summary:")
        for phase, summary in sorted(
            phase_summary.items(),
            key=lambda item: int(item[1].get("total_duration_ms", 0)),
            reverse=True,
        ):
            lines.append(
                f"- {phase}: total={format_duration_ms(summary.get('total_duration_ms', 0))}, "
                f"max={format_duration_ms(summary.get('max_duration_ms', 0))}, "
                f"spans={summary.get('span_count', 0)}, "
                f"failures={summary.get('failure_count', 0)}, "
                f"timeouts={summary.get('timeout_count', 0)}"
            )
    lines.append("")
    return "\n".join(lines)


def render_semantic_judgement(semantic_summary: dict, findings: list[dict]) -> str:
    """Render semantic judgement section."""
    lines = ["### Semantic Judgement\n"]

    if not semantic_summary or not semantic_summary.get("verdicts"):
        lines.append("No semantic triage results. (Rule-only mode)\n")
        return "\n".join(lines)

    verdict_counts = Counter(v.get("semantic_verdict", "unknown") for v in semantic_summary["verdicts"])
    mode = semantic_summary.get("mode", "unknown")
    lines.append(f"Mode: {mode} | Total packets: {semantic_summary.get('total_packets', 0)}\n")

    for vtype in ["true_positive", "false_positive", "benign_exception", "needs_human_review"]:
        count = verdict_counts.get(vtype, 0)
        if count > 0:
            label = vtype.replace("_", " ").title()
            lines.append(f"- **{label}**: {count}")

            # List findings in this verdict class
            for v in semantic_summary["verdicts"]:
                if v.get("semantic_verdict") == vtype:
                    reason = v.get("reason", "")[:150]
                    lines.append(f"  - {v.get('finding_id', '?')}: {reason}")

    lines.append("")
    return "\n".join(lines)


def render_token_budget(meta_root: Path) -> str:
    lines = ["### Token Budget\n"]
    manifest = load_json(meta_root / "evidence-packets" / "latest" / "manifest.json") or {}
    budget = manifest.get("token_budget", {}) or {}
    if not budget:
        lines.append("No evidence-packet token budget recorded yet.\n")
        return "\n".join(lines)

    lines.append(f"- Rule findings before packet budget: {budget.get('input_findings', manifest.get('total_findings', 0))}")
    lines.append(f"- Findings after duplicate-shape collapse: {budget.get('deduped_findings', manifest.get('total_packets', 0))}")
    lines.append(f"- Semantic calls planned: {budget.get('semantic_calls_planned', manifest.get('total_packets', 0))}")
    lines.append(f"- Duplicate semantic calls saved: {budget.get('semantic_calls_saved', 0)}")
    if budget.get("packet_limit_saved", 0):
        lines.append(f"- Packet-limit calls skipped: {budget.get('packet_limit_saved', 0)}")

    duplicate_groups = budget.get("duplicate_groups", []) or []
    if duplicate_groups:
        lines.append("")
        lines.append("Collapsed duplicate groups:")
        for group in duplicate_groups[:5]:
            lines.append(
                f"- {group.get('representative_finding_id', 'unknown')}: "
                f"{group.get('duplicates', 0)} duplicate(s)"
            )
    lines.append("")
    return "\n".join(lines)


def render_proposals_section(proposals_summary: dict, candidate_dir: Path, rejected_dir: Path) -> str:
    lines = ["### Candidate Repairs\n"]

    if not proposals_summary or proposals_summary.get("total_proposals", 0) == 0:
        lines.append("No candidate proposals generated.\n")
        return "\n".join(lines)

    lines.append(f"Total proposals: {proposals_summary.get('total_proposals', 0)} from {proposals_summary.get('total_findings', 0)} findings\n")

    by_state = proposals_summary.get("proposals_by_state", {})
    for state in ["candidate_semantic_supported", "candidate_rule_only", "candidate_needs_human_review", "rejected_false_positive", "rejected_benign_exception"]:
        count = by_state.get(state, 0)
        if count > 0:
            label = state.replace("_", " ").title()
            lines.append(f"- **{label}**: {count}")

    lines.append("")
    lines.append("Proposal files:")
    for pf in proposals_summary.get("proposal_files", []):
        p = Path(pf)
        parent = "candidate" if "candidate" in str(p) else "rejected"
        lines.append(f"- [{p.name}](../../proposals/{parent}/{p.name})")
    lines.append("")
    return "\n".join(lines)


def get_actionable_proposals(proposals_summary: dict | None) -> list[dict]:
    if not proposals_summary:
        return []
    return proposals_summary.get("actionable_proposals", []) or []


def render_prediction_contracts(findings_path: Path, proposals_summary: dict | None = None) -> str:
    findings = load_json(findings_path) or []
    lines = ["### Prediction Contracts\n"]

    actionable = get_actionable_proposals(proposals_summary)
    if proposals_summary is not None:
        if not actionable:
            lines.append("No actionable findings, no prediction contracts.\n")
            return "\n".join(lines)
        for prop in actionable:
            contract = prop.get("prediction_contract", {}) or {}
            lines.append(f"**{prop.get('proposal_id', 'proposal')}**")
            lines.append(f"- Expected: {contract.get('expected_future_behavior', prop.get('proposed_change', 'N/A'))}")
            lines.append(f"- Signal: {contract.get('measurable_signal', 'N/A')}")
            lines.append(f"- Replay: {contract.get('replay_or_eval', 'N/A')}")
            lines.append("")
        return "\n".join(lines)

    if not findings:
        lines.append("No findings, no prediction contracts.\n")
        return "\n".join(lines)

    seen = set()
    for cat in CATEGORY_ORDER:
        cat_findings = [f for f in findings if f.get("category") == cat]
        for f in cat_findings:
            fid = f.get("id", "")
            if fid in seen:
                continue
            seen.add(fid)
            lines.append(f"**{f.get('title', fid)}**")
            lines.append(f"- Expected: {f.get('proposed_action', 'N/A')}")
            lines.append(f"- Signal: Reduced finding count in '{cat}' category")
            lines.append(f"- Replay: Re-run meta-review after 5 new tasks")
            lines.append("")
    return "\n".join(lines)


def render_contract_replay(meta_root: Path) -> str:
    """Render contract replay section."""
    lines = ["### Contract Replay\n"]

    replay_latest = load_json(meta_root / "replays" / "results" / "replay-latest.json")
    if not replay_latest or not replay_latest.get("results"):
        lines.append("No contract replay results yet. Run replay-contracts.py after a second meta-review cycle.\n")
        return "\n".join(lines)

    results = replay_latest["results"]
    verdict_counts = Counter(r["verdict"] for r in results)

    lines.append(f"Contracts replayed: {len(results)}\n")
    for v in ["improved", "unchanged", "regressed", "inconclusive"]:
        count = verdict_counts.get(v, 0)
        if count > 0:
            lines.append(f"- **{v.title()}**: {count}")

    lines.append("")
    for r in results:
        run_window = ""
        if r.get("run_metric_window"):
            baseline = ", ".join(r["run_metric_window"].get("baseline_runs", []))
            current = ", ".join(r["run_metric_window"].get("current_runs", []))
            run_window = f" [{baseline} -> {current}]"
        lines.append(f"- {r['proposal_id']}: {r['metric_name']} {r['baseline_value']} -> {r['current_value']} ({r['relative_change']:+.0%}) = **{r['verdict'].upper()}**{run_window}")

    lines.append("")
    return "\n".join(lines)


def load_contract_replay_results(meta_root: Path) -> list[dict]:
    replay_latest = load_json(meta_root / "replays" / "results" / "replay-latest.json")
    if not replay_latest:
        return []
    return replay_latest.get("results", []) or []


def render_evolution_signals(meta_root: Path) -> str:
    """Render experience archive and proposal scoring signals."""
    lines = ["### Evolution Signals\n"]

    summary = load_json(meta_root / "experience" / "latest" / "summary.json")
    scores = load_json(meta_root / "experience" / "latest" / "evolution-scores.json") or []
    if not summary:
        lines.append("No experience archive yet. Run build_experience_archive.py after signal collection.\n")
        return "\n".join(lines)

    lines.append(f"Experience records: {summary.get('experience_records', 0)}")
    lines.append(f"Proposals scored: {summary.get('proposals_scored', 0)}")
    status_counts = summary.get("task_status_counts", {})
    if status_counts:
        rendered = ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
        lines.append(f"Task states: {rendered}")
    lines.append("")

    if not scores:
        lines.append("No scored proposals yet.\n")
        return "\n".join(lines)

    lines.append("Top proposal scores:")
    for score in scores[:5]:
        lines.append(
            f"- {score.get('proposal_id', 'unknown')}: score={score.get('evolution_score', 0)} "
            f"surface={score.get('target_surface', 'unknown')} state={score.get('promotion_state', 'unknown')}"
        )
    lines.append("")
    return "\n".join(lines)


def render_recommended_patch(
    findings: list[dict],
    proposals_summary: dict,
    semantic_summary: dict,
    replay_results: list[dict] | None = None,
) -> str:
    lines = ["### Recommended Next Patch\n"]

    if not findings:
        lines.append("No findings to patch. Harness appears healthy.\n")
        return "\n".join(lines)

    actionable = get_actionable_proposals(proposals_summary)
    if proposals_summary is not None and not actionable:
        lines.append("No actionable findings. Current findings were rejected or marked benign by semantic triage.\n")
        return "\n".join(lines)

    replay_results = replay_results or []
    regressed = [r for r in replay_results if r.get("verdict") == "regressed"]
    if regressed and actionable:
        actionable_by_id = {p.get("proposal_id"): p for p in actionable}
        best_replay = sorted(
            regressed,
            key=lambda r: r.get("relative_change", 0),
            reverse=True,
        )[0]
        best = actionable_by_id.get(best_replay.get("proposal_id"))
        if best:
            lines.append("**Priority: REGRESSED CONTRACT**")
            lines.append(f"- Proposal: {best.get('proposal_id', 'unknown')}")
            lines.append(f"- Category: {best.get('target_surface', '')}")
            lines.append(f"- Action: {best.get('proposed_change', 'N/A')}")
            lines.append(
                f"- Replay: {best_replay.get('metric_name', 'metric')} "
                f"{best_replay.get('baseline_value')} -> {best_replay.get('current_value')} "
                f"({best_replay.get('relative_change', 0):+.0%})"
            )
            rationale = best.get("rationale", "")
            if rationale:
                lines.append(f"- Rationale: {rationale}")
            lines.append("")
            return "\n".join(lines)

    if actionable:
        state_priority = {
            "candidate_semantic_supported": 0,
            "candidate_needs_human_review": 1,
            "candidate_rule_only": 2,
        }
        best = sorted(
            actionable,
            key=lambda p: state_priority.get(p.get("promotion_state", ""), 99),
        )[0]
        lines.append(f"**Priority: {best.get('promotion_state', 'candidate').replace('_', ' ').upper()}**")
        lines.append(f"- Proposal: {best.get('proposal_id', 'unknown')}")
        lines.append(f"- Category: {best.get('target_surface', '')}")
        lines.append(f"- Action: {best.get('proposed_change', 'N/A')}")
        rationale = best.get("rationale", "")
        if rationale:
            lines.append(f"- Rationale: {rationale}")
        lines.append("")
        return "\n".join(lines)

    # Prefer semantic-supported findings first
    if semantic_summary and semantic_summary.get("verdicts"):
        tp = [v for v in semantic_summary["verdicts"] if v.get("semantic_verdict") == "true_positive"]
        if tp:
            best = tp[0]
            # Find matching finding
            matching = [f for f in findings if f.get("id") == best.get("finding_id")]
            if matching:
                f = matching[0]
                lines.append(f"**Priority: SEMANTIC CONFIRMED** — {f.get('title', 'Unknown')}")
                lines.append(f"- Category: {f.get('category', '')}")
                lines.append(f"- Action: {best.get('recommended_action', f.get('proposed_action', 'N/A'))}")
                lines.append(f"- Semantic reason: {best.get('reason', '')}")
                lines.append("")
                return "\n".join(lines)

    # Fall back to highest severity rule finding
    for cat in CATEGORY_ORDER:
        cat_findings = [f for f in findings if f.get("category") == cat and f.get("severity") == "high"]
        if cat_findings:
            best = cat_findings[0]
            lines.append(f"**Priority: HIGH** — {best.get('title', 'Unknown')}")
            lines.append(f"- Category: {cat}")
            lines.append(f"- Action: {best.get('proposed_action', 'N/A')}")
            lines.append("")
            return "\n".join(lines)

    for cat in CATEGORY_ORDER:
        cat_findings = [f for f in findings if f.get("category") == cat]
        if cat_findings:
            best = cat_findings[0]
            lines.append(f"**Priority: MEDIUM** — {best.get('title', 'Unknown')}")
            lines.append(f"- Category: {cat}")
            lines.append(f"- Action: {best.get('proposed_action', 'N/A')}")
            lines.append("")
            return "\n".join(lines)

    lines.append("No actionable findings.\n")
    return "\n".join(lines)


def render_report(
    findings: list[dict],
    proposals_summary: dict,
    semantic_summary: dict,
    signals_dir: Path,
    meta_root: Path,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    manifest = load_json(signals_dir / "manifest.json") or {}

    lines = [
        "# Meta-Harness Review Report (v0.4-seed)",
        "",
        f"Generated: {now}",
        f"Tasks analyzed: {manifest.get('tasks_collected', 'N/A')}",
        f"Receipts analyzed: {manifest.get('receipts_collected', 'N/A')}",
        f"Reviews analyzed: {manifest.get('reviews_collected', 'N/A')}",
        f"Total findings: {len(findings)}",
        "",
        "---",
        "",
        "## 1. Current Run Tool Status",
        "",
        render_current_run_tool_status(signals_dir, findings),
        "",
        "## 2. Runtime Profile",
        "",
        render_runtime_profile(signals_dir),
        "",
        "## 3. Rule Findings",
        "",
    ]

    for cat in CATEGORY_ORDER:
        lines.append(render_findings_section(findings, cat))
        lines.append("")

    lines.append("## 4. Token Budget")
    lines.append("")
    lines.append(render_token_budget(meta_root))
    lines.append("")

    lines.append("## 5. Semantic Judgement")
    lines.append("")
    lines.append(render_semantic_judgement(semantic_summary, findings))
    lines.append("")

    lines.append("## 6. Candidate Repairs")
    lines.append("")
    candidate_dir = meta_root / "proposals" / "candidate"
    rejected_dir = meta_root / "proposals" / "rejected"
    lines.append(render_proposals_section(proposals_summary, candidate_dir, rejected_dir))
    lines.append("")

    lines.append("## 7. Prediction Contracts")
    lines.append("")
    lines.append(render_prediction_contracts(signals_dir / "findings.json", proposals_summary))
    lines.append("")

    lines.append("## 8. Contract Replay")
    lines.append("")
    lines.append(render_contract_replay(meta_root))
    lines.append("")

    lines.append("## 9. Evolution Signals")
    lines.append("")
    lines.append(render_evolution_signals(meta_root))
    lines.append("")

    lines.append("## 10. Recommended Next Patch")
    lines.append("")
    replay_results = load_contract_replay_results(meta_root)
    lines.append(render_recommended_patch(findings, proposals_summary, semantic_summary, replay_results))

    lines.extend([
        "",
        "---",
        "",
        "*This report was generated by Meta-Harness v0.4-seed. It proposes candidate",
        "changes only. Active harness changes must pass existing gates and reviewer",
        "approval before promotion.*",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Render meta-review report (v0.3)")
    parser.add_argument("--signals-dir", required=True, help="Path to signals/latest/")
    parser.add_argument("--meta-root", required=True, help="Path to meta-harness root")
    parser.add_argument("--semantic-mode", choices=["none", "offline", "llm"], default="none", help="Semantic result mode for this run")
    args = parser.parse_args()

    signals_dir = Path(args.signals_dir).resolve()
    meta_root = Path(args.meta_root).resolve()

    findings = load_json(signals_dir / "findings.json") or []
    proposals_summary = load_json(signals_dir / "proposals_summary.json")
    semantic_summary = None
    if args.semantic_mode in ("offline", "llm"):
        semantic_summary = load_json(meta_root / "semantic-reviews" / "latest" / "summary.json")

    report = render_report(findings, proposals_summary, semantic_summary, signals_dir, meta_root)

    reports_dir = meta_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    stamped_path = reports_dir / f"meta-review-{timestamp}.md"
    latest_path = reports_dir / "meta-review-latest.md"

    with open(stamped_path, "w", encoding="utf-8") as f:
        f.write(report)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport written to {stamped_path}")
    print(f"  Latest copy: {latest_path}")
    print(f"  Findings: {len(findings)}")
    if proposals_summary:
        print(f"  Proposals: {proposals_summary.get('total_proposals', 0)}")
    if semantic_summary:
        print(f"  Semantic mode: {semantic_summary.get('mode', 'N/A')}")
    else:
        print("  Semantic mode: none")


if __name__ == "__main__":
    main()
