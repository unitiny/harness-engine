#!/usr/bin/env python3
"""replay-contracts.py — Prediction contract replay and measurement.

Compares prior proposals against later artifacts. Measures whether the
expected improvement actually occurred.

Replay verdicts: improved, unchanged, regressed, inconclusive.
These are evidence only — they do not auto-promote active rules.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_config(meta_root: Path) -> dict:
    import yaml
    cfg_path = meta_root / "config.yaml"
    if not cfg_path.exists():
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def count_findings_by_category(findings: list[dict]) -> dict[str, int]:
    return dict(Counter(f.get("category", "unknown") for f in findings))


def measure_task_brief_avg_lines(tasks: list[dict]) -> float:
    if not tasks:
        return 0.0
    return sum(t.get("line_count", 0) for t in tasks) / len(tasks)


def measure_repeated_boilerplate(findings: list[dict]) -> int:
    return sum(1 for f in findings if f.get("category") == "token_waste" and f.get("gap_type") == "missing_rule")


def measure_missing_scope(findings: list[dict]) -> int:
    return sum(1 for f in findings if f.get("category") == "ai_guidance_gap")


def measure_missing_gate_evidence(findings: list[dict]) -> int:
    return sum(1 for f in findings if f.get("category") == "delivery_quality_risk")


def measure_repair_round_count(receipts: list[dict]) -> int:
    count = 0
    for r in receipts:
        content = r.get("content", "")
        if "BLOCKED" in content.upper():
            count += 1
    return count


def measure_tool_efficiency_risks(findings: list[dict]) -> int:
    return sum(1 for f in findings if f.get("category") == "tool_efficiency_risk")


def compute_relative_change(baseline: float, current: float) -> float:
    """Compute relative change. Negative = improvement for metrics where decrease is good."""
    if baseline == 0:
        if current == 0:
            return 0.0
        return 1.0 if current > 0 else -1.0
    return (current - baseline) / baseline


def judge_verdict(relative_change: float, min_samples: int, actual_samples: int,
                  improve_threshold: float = -0.20, regress_threshold: float = 0.20,
                  inconclusive_when_underpowered: bool = True) -> str:
    if actual_samples < min_samples:
        if inconclusive_when_underpowered:
            return "inconclusive"
    if relative_change <= improve_threshold:
        return "improved"
    if relative_change >= regress_threshold:
        return "regressed"
    return "unchanged"


def load_prior_proposals(meta_root: Path) -> list[dict]:
    """Load all candidate proposals from the candidate directory."""
    proposals = []
    candidate_dir = meta_root / "proposals" / "candidate"
    if not candidate_dir.exists():
        return proposals
    # Also check for prior runs in replays/contracts
    contracts_dir = meta_root / "replays" / "contracts"
    if contracts_dir.exists():
        for f in contracts_dir.glob("*.json"):
            data = load_json(f)
            if data:
                proposals.append(data)
    return proposals


def replay_one_contract(
    proposal: dict,
    current_findings: list[dict],
    current_tasks: list[dict],
    current_receipts: list[dict],
    baseline_findings: list[dict],
    baseline_tasks: list[dict],
    config: dict,
) -> dict:
    """Replay one prediction contract against current data."""
    contract = proposal.get("prediction_contract", {})
    target_surface = proposal.get("target_surface", "")
    proposal_id = proposal.get("proposal_id", "unknown")

    replay_cfg = config.get("contract_replay", {})
    min_samples = replay_cfg.get("min_samples_for_verdict", 3)
    inconclusive = replay_cfg.get("inconclusive_when_underpowered", True)

    # Select metric based on category
    if target_surface == "token_waste":
        baseline_val = float(measure_repeated_boilerplate(baseline_findings))
        current_val = float(measure_repeated_boilerplate(current_findings))
        metric_name = "repeated_boilerplate_count"
    elif target_surface == "ai_guidance_gap":
        baseline_val = float(measure_missing_scope(baseline_findings))
        current_val = float(measure_missing_scope(current_findings))
        metric_name = "missing_scope_count"
    elif target_surface == "delivery_quality_risk":
        baseline_val = float(measure_missing_gate_evidence(baseline_findings))
        current_val = float(measure_missing_gate_evidence(current_findings))
        metric_name = "missing_gate_evidence_count"
    elif target_surface == "missing_evaluator_coverage":
        baseline_val = float(sum(1 for f in baseline_findings if f.get("category") == "missing_evaluator_coverage"))
        current_val = float(sum(1 for f in current_findings if f.get("category") == "missing_evaluator_coverage"))
        metric_name = "missing_evaluator_coverage_count"
    elif target_surface == "tool_efficiency_risk":
        baseline_val = float(measure_tool_efficiency_risks(baseline_findings))
        current_val = float(measure_tool_efficiency_risks(current_findings))
        metric_name = "tool_efficiency_risk_count"
    else:
        baseline_val = float(len(baseline_findings))
        current_val = float(len(current_findings))
        metric_name = "total_findings"

    rel_change = compute_relative_change(baseline_val, current_val)
    verdict = judge_verdict(rel_change, min_samples, len(current_tasks), inconclusive_when_underpowered=inconclusive)

    return {
        "contract_id": f"replay-{proposal_id}",
        "proposal_id": proposal_id,
        "expected_future_behavior": contract.get("expected_future_behavior", ""),
        "measurable_signal": contract.get("measurable_signal", ""),
        "baseline_window": {
            "findings_count": len(baseline_findings),
            "tasks_count": len(baseline_tasks),
        },
        "replay_window": {
            "findings_count": len(current_findings),
            "tasks_count": len(current_tasks),
        },
        "metric_name": metric_name,
        "baseline_value": baseline_val,
        "current_value": current_val,
        "relative_change": round(rel_change, 3),
        "observed_change": f"{metric_name}: {baseline_val} -> {current_val} ({rel_change:+.1%})",
        "verdict": verdict,
        "evidence": f"Baseline: {baseline_val}, Current: {current_val}, Change: {rel_change:+.1%}",
        "next_action": {
            "improved": "Consider promoting to validated",
            "unchanged": "Monitor for another cycle",
            "regressed": "Review whether the repair was effective",
            "inconclusive": "Collect more samples before judging",
        }.get(verdict, "Review manually"),
        "replayed_at": datetime.now().isoformat(),
    }


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def proposal_metric_from_run_metrics(proposal: dict, run_metrics: list[dict]) -> tuple[str, list[float]]:
    """Return a metric series for proposals that can be replayed by run."""
    surface = proposal.get("target_surface", "")
    if surface == "tool_efficiency_risk":
        return "tool_error_count_per_run", [float(r.get("tool_error_count", 0)) for r in run_metrics]
    if surface == "delivery_quality_risk":
        return "timeout_count_per_run", [float(r.get("timeout_count", 0)) for r in run_metrics]
    return "", []


def replay_contracts_with_run_metrics(
    proposals: list[dict],
    run_metrics: list[dict],
    config: dict,
) -> list[dict]:
    """Replay actionable proposal contracts against per-run trend metrics."""
    replay_cfg = config.get("contract_replay", {})
    baseline_window = int(replay_cfg.get("baseline_window", 5))
    replay_window = int(replay_cfg.get("replay_window", 5))
    min_samples = int(replay_cfg.get("min_samples_for_verdict", 3))
    inconclusive = replay_cfg.get("inconclusive_when_underpowered", True)

    ordered_runs = sorted(run_metrics, key=lambda r: (r.get("latest_mtime", 0), r.get("run_id", "")))
    sample_count = baseline_window + replay_window
    window_runs = ordered_runs[-sample_count:] if sample_count > 0 else ordered_runs

    results = []
    for proposal in proposals:
        metric_name, values = proposal_metric_from_run_metrics(proposal, window_runs)
        if not metric_name:
            continue
        if len(values) < max(1, min_samples):
            baseline_runs = window_runs[:baseline_window]
            current_runs = window_runs[baseline_window:]
        else:
            baseline_runs = window_runs[:baseline_window]
            current_runs = window_runs[baseline_window:baseline_window + replay_window]
        baseline_values = values[:len(baseline_runs)]
        current_values = values[len(baseline_runs):len(baseline_runs) + len(current_runs)]
        baseline_val = average(baseline_values)
        current_val = average(current_values)
        rel_change = compute_relative_change(baseline_val, current_val)
        verdict = judge_verdict(
            rel_change,
            min_samples,
            min(len(baseline_runs), len(current_runs)),
            inconclusive_when_underpowered=inconclusive,
        )
        contract = proposal.get("prediction_contract", {}) or {}
        proposal_id = proposal.get("proposal_id", "unknown")
        results.append({
            "contract_id": f"replay-{proposal_id}",
            "proposal_id": proposal_id,
            "expected_future_behavior": contract.get("expected_future_behavior", ""),
            "measurable_signal": contract.get("measurable_signal", ""),
            "metric_name": metric_name,
            "baseline_value": round(baseline_val, 3),
            "current_value": round(current_val, 3),
            "relative_change": round(rel_change, 3),
            "observed_change": f"{metric_name}: {baseline_val:.3g} -> {current_val:.3g} ({rel_change:+.1%})",
            "verdict": verdict,
            "evidence": f"Run metric replay over {len(baseline_runs)} baseline run(s) and {len(current_runs)} current run(s)",
            "run_metric_window": {
                "baseline_runs": [r.get("run_id", "") for r in baseline_runs],
                "current_runs": [r.get("run_id", "") for r in current_runs],
            },
            "next_action": {
                "improved": "Consider promoting to validated after human review",
                "unchanged": "Monitor for another cycle",
                "regressed": "Review whether the repair was effective",
                "inconclusive": "Collect more runs before judging",
            }.get(verdict, "Review manually"),
            "replayed_at": datetime.now().isoformat(),
        })
    return results


def render_replay_report(results: list[dict]) -> str:
    """Render contract replay results as markdown."""
    lines = [
        "# Contract Replay Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Total contracts replayed: {len(results)}",
        "",
    ]

    from collections import Counter
    verdict_counts = Counter(r["verdict"] for r in results)
    lines.append("## Summary")
    lines.append("")
    for v in ["improved", "unchanged", "regressed", "inconclusive"]:
        count = verdict_counts.get(v, 0)
        label = v.replace("_", " ").title()
        lines.append(f"- **{label}**: {count}")
    lines.append("")

    lines.append("## Details")
    lines.append("")
    for r in results:
        lines.append(f"### {r['contract_id']}")
        lines.append("")
        lines.append(f"- **Proposal**: {r['proposal_id']}")
        lines.append(f"- **Expected**: {r['expected_future_behavior']}")
        lines.append(f"- **Metric**: {r['metric_name']}")
        lines.append(f"- **Baseline**: {r['baseline_value']}")
        lines.append(f"- **Current**: {r['current_value']}")
        lines.append(f"- **Change**: {r['relative_change']:+.1%}")
        lines.append(f"- **Verdict**: {r['verdict'].upper()}")
        if r.get("run_metric_window"):
            baseline = ", ".join(r["run_metric_window"].get("baseline_runs", []))
            current = ", ".join(r["run_metric_window"].get("current_runs", []))
            lines.append(f"- **Run window**: {baseline} -> {current}")
        lines.append(f"- **Next action**: {r['next_action']}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "*Replay verdicts are evidence only. They do not automatically promote active rules.*",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Replay prediction contracts against current data")
    parser.add_argument("--meta-root", required=True, help="Path to meta-harness root")
    args = parser.parse_args()

    meta_root = Path(args.meta_root).resolve()
    config = load_config(meta_root)

    replay_cfg = config.get("contract_replay", {})
    if not replay_cfg.get("enabled", True):
        print("Contract replay is disabled in config.")
        sys.exit(0)

    # Load current signals
    signals_dir = meta_root / "signals" / "latest"
    current_findings = load_json(signals_dir / "findings.json") or []
    current_tasks = load_json(signals_dir / "tasks.json") or []
    current_receipts = load_json(signals_dir / "receipts.json") or []
    run_metrics = load_json(signals_dir / "run_metrics.json") or []

    proposals_summary = load_json(signals_dir / "proposals_summary.json") or {}
    actionable_proposals = proposals_summary.get("actionable_proposals", []) or []

    # Prefer the current proposal summary because it preserves structured
    # prediction contracts. Fall back to saved prior contracts for older runs.
    run_metric_results = replay_contracts_with_run_metrics(actionable_proposals, run_metrics, config)
    if run_metric_results:
        results = run_metric_results
        results_dir = meta_root / "replays" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        payload = {
            "results": results,
            "replayed_at": datetime.now().isoformat(),
            "mode": "run_metrics",
        }
        save_json(results_dir / f"replay-{timestamp}.json", payload)
        save_json(results_dir / "replay-latest.json", payload)
        report = render_replay_report(results)
        reports_dir = meta_root / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"contract-replay-{timestamp}.md"
        report_path.write_text(report, encoding="utf-8")
        (reports_dir / "contract-replay-latest.md").write_text(report, encoding="utf-8")
        verdict_counts = Counter(r["verdict"] for r in results)
        print(f"\nContract replay: {len(results)} contracts")
        for v, count in verdict_counts.most_common():
            print(f"  {v}: {count}")
        print(f"\nReport: {report_path}")
        return

    # Load prior proposals with contracts
    prior_proposals = load_prior_proposals(meta_root)
    if not prior_proposals:
        print("No prior proposals with prediction contracts found.")
        print("Contract replay requires at least one prior proposal cycle.")
        sys.exit(0)

    # For baseline, we use the current findings as baseline for future comparison
    # Save current state as baseline for next replay
    baseline_dir = meta_root / "replays" / "contracts"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = baseline_dir / "baseline-latest.json"
    baseline = load_json(baseline_path)
    if not baseline:
        # First replay: current data becomes baseline for next time
        baseline = {
            "findings": current_findings,
            "tasks_count": len(current_tasks),
            "saved_at": datetime.now().isoformat(),
        }
        save_json(baseline_path, baseline)
        print("No prior baseline found. Current data saved as baseline for next replay cycle.")
        print("Run replay again after the next meta-review cycle to see comparison.")

    baseline_findings = baseline.get("findings", [])
    baseline_tasks = [{"line_count": 0} for _ in range(baseline.get("tasks_count", 0))]

    # Replay each proposal contract
    results = []
    for proposal in prior_proposals:
        result = replay_one_contract(
            proposal, current_findings, current_tasks, current_receipts,
            baseline_findings, baseline_tasks, config,
        )
        results.append(result)

    # Save results
    results_dir = meta_root / "replays" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    save_json(results_dir / f"replay-{timestamp}.json", {
        "results": results,
        "replayed_at": datetime.now().isoformat(),
    })
    save_json(results_dir / "replay-latest.json", {
        "results": results,
        "replayed_at": datetime.now().isoformat(),
    })

    # Render report
    report = render_replay_report(results)
    reports_dir = meta_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"contract-replay-{timestamp}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    with open(reports_dir / "contract-replay-latest.md", "w", encoding="utf-8") as f:
        f.write(report)

    # Print summary
    verdict_counts = Counter(r["verdict"] for r in results)
    print(f"\nContract replay: {len(results)} contracts")
    for v, count in verdict_counts.most_common():
        print(f"  {v}: {count}")
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
