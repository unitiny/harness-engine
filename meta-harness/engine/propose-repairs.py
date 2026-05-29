#!/usr/bin/env python3
"""propose-repairs.py — Convert gap findings + semantic verdicts into proposals.

Merges rule findings with semantic triage results. Produces proposals with
5 possible promotion states:
  - candidate_rule_only
  - candidate_semantic_supported
  - candidate_needs_human_review
  - rejected_false_positive
  - rejected_benign_exception
"""

import argparse
import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path


TARGET_PRIORITY = ["checker", "workflow", "eval", "memory", "template", "tool_policy", "instruction"]


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_target(finding: dict, semantic_target: str = "none") -> str:
    """Select the best patch target, preferring semantic suggestion."""
    category = finding.get("category", "")
    gap_type = finding.get("gap_type", "")
    proposed_action = finding.get("proposed_action", "").lower()

    if category == "tool_efficiency_risk":
        if "interface" in proposed_action or "generator" in proposed_action:
            return "tool_policy"
        return "workflow"

    if semantic_target and semantic_target != "none":
        if semantic_target in TARGET_PRIORITY:
            return semantic_target

    if any(kw in proposed_action for kw in ["require", "enforce", "check", "detect", "gate"]):
        if gap_type in ("missing_checker", "missing_eval"):
            return "checker"
        if "template" in proposed_action and "require" in proposed_action:
            return "template"

    if gap_type == "bad_workflow":
        return "workflow"
    if gap_type == "missing_eval" and ("replay" in proposed_action or "validation" in proposed_action):
        return "eval"
    if gap_type == "missing_memory":
        return "memory"
    if "template" in proposed_action or "field" in proposed_action:
        return "template"
    if gap_type == "bad_tool_policy":
        return "tool_policy"
    if gap_type in ("missing_rule", "weak_rule"):
        if any(kw in proposed_action for kw in ["require", "enforce", "check"]):
            return "checker"
        return "instruction"
    return "instruction"


def build_prediction_contract(finding: dict, target: str) -> dict:
    category = finding.get("category", "")
    contracts = {
        "token_waste": {
            "expected_future_behavior": "Fewer repeated boilerplate blocks in new task briefs and reviews",
            "measurable_signal": "Token count per task brief decreases; repeat-block count decreases",
            "replay_or_eval": "Re-run collect-signals after 5 new tasks; boilerplate finding count should decrease",
        },
        "ai_guidance_gap": {
            "expected_future_behavior": "Implementer receipts need fewer repair rounds from ambiguous scope",
            "measurable_signal": "BLOCKED status count from scope ambiguity decreases",
            "replay_or_eval": "Re-run analyze-gaps after 5 new tasks; missing guidance finding count should decrease",
        },
        "delivery_quality_risk": {
            "expected_future_behavior": "Reviews more consistently compare brief, receipt, diff, and gate evidence",
            "measurable_signal": "Review-without-diff finding count decreases",
            "replay_or_eval": "Re-run analyze-gaps; delivery quality findings should decrease",
        },
        "missing_evaluator_coverage": {
            "expected_future_behavior": "Failed or partial tasks produce concrete evaluator repair proposals",
            "measurable_signal": "Blocked-without-eval-repair finding count decreases",
            "replay_or_eval": "Re-run analyze-gaps after next BLOCKED task; evaluator proposal should be present",
        },
        "tool_efficiency_risk": {
            "expected_future_behavior": "Agents avoid repeated failing tool-call patterns and choose safer, lower-token tool paths before retrying",
            "measurable_signal": "[TOOL OUTPUT: ERROR] count, repeated Bash quoting failures, and long generator shell commands decrease in automation logs",
            "replay_or_eval": "Re-run meta-review over later automation logs; tool_efficiency_risk findings and [TOOL OUTPUT: ERROR] windows should decrease",
        },
    }
    return contracts.get(category, {
        "expected_future_behavior": "Harness quality improves as measured by reduced findings in this category",
        "measurable_signal": "Finding count in this category decreases",
        "replay_or_eval": "Re-run analyze-gaps and compare finding counts",
    })


def build_applies_when(finding: dict) -> str:
    category = finding.get("category", "")
    return {
        "token_waste": "When new task briefs are generated or existing templates are used",
        "ai_guidance_gap": "When task briefs are created or reviewed for completeness",
        "delivery_quality_risk": "When reviews are written or receipts are submitted",
        "missing_evaluator_coverage": "When a task is BLOCKED, fails, or has MEDIUM+ risk class",
        "tool_efficiency_risk": "When automation logs show [TOOL OUTPUT: ERROR], repeated tool errors, long shell commands, or avoidable retry loops",
    }.get(category, "When the described condition occurs")


def build_does_not_apply_when(finding: dict) -> str:
    gap_type = finding.get("gap_type", "")
    if gap_type == "missing_checker":
        return "When the failure class is already covered by an existing checker"
    if gap_type == "bad_workflow":
        return "When the current workflow order does not cause the issue"
    return "When the finding is no longer present in gap analysis"


def build_anti_gaming_check(finding: dict, target: str) -> str:
    return f"Verify that the {target} change reduces the specific finding class without masking other quality signals"


def resolve_promotion_state(semantic_verdict: str | None) -> str:
    """Map semantic verdict to proposal promotion state."""
    if semantic_verdict is None:
        return "candidate_rule_only"
    return {
        "true_positive": "candidate_semantic_supported",
        "false_positive": "rejected_false_positive",
        "benign_exception": "rejected_benign_exception",
        "needs_human_review": "candidate_needs_human_review",
    }.get(semantic_verdict, "candidate_rule_only")


def get_output_dir(promotion_state: str, meta_root: Path) -> Path:
    """Return the correct output directory based on promotion state."""
    if promotion_state.startswith("rejected"):
        return meta_root / "proposals" / "rejected"
    return meta_root / "proposals" / "candidate"


def load_semantic_verdicts(meta_root: Path, semantic_mode: str = "none") -> dict[str, dict]:
    """Load semantic verdicts indexed by finding_id."""
    if semantic_mode not in ("offline", "llm"):
        return {}
    verdicts = {}
    review_dir = meta_root / "semantic-reviews" / "latest"
    summary = load_json(review_dir / "summary.json")
    if summary and "verdicts" in summary:
        for v in summary["verdicts"]:
            fid = v.get("finding_id", "")
            if fid:
                verdicts[fid] = v
    return verdicts


def propose_repairs(findings: list[dict], meta_root: Path, semantic_verdicts: dict) -> list[dict]:
    proposals = []
    seen_targets = {}

    for finding in findings:
        fid = finding.get("id", "unknown")
        sv = semantic_verdicts.get(fid)
        semantic_target = sv.get("better_patch_target", "none") if sv else "none"
        target = select_target(finding, semantic_target)
        promotion_state = resolve_promotion_state(sv["semantic_verdict"] if sv else None)

        key = f"{target}-{finding.get('gap_type', '')}-{promotion_state}"

        if key in seen_targets:
            existing = proposals[seen_targets[key]]
            existing["finding_ids"].append(fid)
            existing["source_findings"].append(fid)
            continue

        proposal = {
            "proposal_id": f"prop-{fid}",
            "source_findings": [fid],
            "finding_ids": [fid],
            "semantic_review": sv if sv else None,
            "target": target,
            "target_surface": finding.get("category", ""),
            "problem_evidence": finding.get("evidence", ""),
            "proposed_change": sv.get("recommended_action", finding.get("proposed_action", "")) if sv else finding.get("proposed_action", ""),
            "rationale": sv.get("reason", finding.get("description", "")) if sv else finding.get("description", ""),
            "applies_when": build_applies_when(finding),
            "does_not_apply_when": build_does_not_apply_when(finding),
            "anti_gaming_check": build_anti_gaming_check(finding, target),
            "prediction_contract": build_prediction_contract(finding, target),
            "promotion_state": promotion_state,
            "created_at": datetime.now().isoformat(),
        }

        seen_targets[key] = len(proposals)
        proposals.append(proposal)

    return proposals


def write_proposal_files(proposals: list[dict], meta_root: Path) -> list[Path]:
    written = []
    for prop in proposals:
        out_dir = get_output_dir(prop["promotion_state"], meta_root)
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{prop['proposal_id']}.md"
        fpath = out_dir / fname

        sem_section = ""
        if prop.get("semantic_review"):
            sr = prop["semantic_review"]
            sem_section = f"""
## Semantic Review

- **Verdict**: {sr.get('semantic_verdict', 'N/A')}
- **Reason**: {sr.get('reason', 'N/A')}
- **Confidence**: {sr.get('confidence', 'N/A')}
- **Better target**: {sr.get('better_patch_target', 'N/A')}
- **Risk if promoted**: {sr.get('risk_if_promoted', 'N/A')}
"""

        lines = [
            f"# Proposal: {prop['proposal_id']}",
            "",
            f"- **Target**: {prop['target']}",
            f"- **Surface**: {prop['target_surface']}",
            f"- **State**: {prop['promotion_state']}",
            f"- **Created**: {prop['created_at']}",
            f"- **Findings**: {', '.join(prop['source_findings'])}",
            "",
            "## Problem Evidence",
            "",
            prop["problem_evidence"],
            "",
            "## Proposed Change",
            "",
            prop["proposed_change"],
            "",
            "## Rationale",
            "",
            prop["rationale"],
            sem_section,
            "## Conditions",
            "",
            f"- **Applies when**: {prop['applies_when']}",
            f"- **Does not apply when**: {prop['does_not_apply_when']}",
            "",
            "## Anti-Gaming Check",
            "",
            prop["anti_gaming_check"],
            "",
            "## Prediction Contract",
            "",
            f"- **Expected behavior**: {prop['prediction_contract']['expected_future_behavior']}",
            f"- **Measurable signal**: {prop['prediction_contract']['measurable_signal']}",
            f"- **Replay/eval**: {prop['prediction_contract']['replay_or_eval']}",
            "",
        ]

        with open(fpath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        written.append(fpath)

    return written


def summarize_actionable_proposals(proposals: list[dict], written: list[Path]) -> list[dict]:
    """Return proposal summaries that are eligible for report recommendations."""
    by_name = {path.name: str(path) for path in written}
    actionable = []
    for prop in proposals:
        state = prop.get("promotion_state", "")
        if state.startswith("rejected"):
            continue
        fname = f"{prop['proposal_id']}.md"
        actionable.append({
            "proposal_id": prop.get("proposal_id", ""),
            "source_findings": prop.get("source_findings", []),
            "target": prop.get("target", ""),
            "target_surface": prop.get("target_surface", ""),
            "promotion_state": state,
            "proposed_change": prop.get("proposed_change", ""),
            "rationale": prop.get("rationale", ""),
            "prediction_contract": prop.get("prediction_contract", {}),
            "proposal_file": by_name.get(fname, ""),
        })
    return actionable


def main():
    parser = argparse.ArgumentParser(description="Generate candidate repair proposals from findings + semantic verdicts")
    parser.add_argument("--signals-dir", required=True, help="Path to signals/latest/")
    parser.add_argument("--meta-root", required=True, help="Path to meta-harness root")
    parser.add_argument("--semantic-mode", choices=["none", "offline", "llm"], default="none", help="Semantic result mode for this run")
    args = parser.parse_args()

    signals_dir = Path(args.signals_dir).resolve()
    meta_root = Path(args.meta_root).resolve()

    findings = load_json(signals_dir / "findings.json") or []
    if not findings:
        print("No findings to propose repairs for.")
        candidate_dir = meta_root / "proposals" / "candidate"
        rejected_dir = meta_root / "proposals" / "rejected"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        if rejected_dir.exists():
            shutil.rmtree(rejected_dir)
        with open(candidate_dir / "_no-findings.txt", "w") as f:
            f.write(f"No findings at {datetime.now().isoformat()}\n")
        save_json(signals_dir / "proposals_summary.json", {
            "total_findings": 0,
            "total_proposals": 0,
            "semantic_verdicts_available": 0,
            "proposals_by_state": {},
            "proposals_by_target": {},
            "actionable_proposals": [],
            "proposal_files": [],
            "created_at": datetime.now().isoformat(),
        })
        sys.exit(0)

    semantic_verdicts = load_semantic_verdicts(meta_root, args.semantic_mode)
    proposals = propose_repairs(findings, meta_root, semantic_verdicts)

    written = write_proposal_files(proposals, meta_root)

    # Summary
    from collections import Counter
    state_counts = Counter(p["promotion_state"] for p in proposals)
    target_counts = Counter(p["target"] for p in proposals)

    summary = {
        "total_findings": len(findings),
        "total_proposals": len(proposals),
        "semantic_verdicts_available": len(semantic_verdicts),
        "proposals_by_state": dict(state_counts),
        "proposals_by_target": dict(target_counts),
        "actionable_proposals": summarize_actionable_proposals(proposals, written),
        "proposal_files": [str(w) for w in written],
        "created_at": datetime.now().isoformat(),
    }
    save_json(signals_dir / "proposals_summary.json", summary)

    print(f"\nRepair proposals: {len(proposals)} from {len(findings)} findings")
    for state, count in state_counts.most_common():
        print(f"  {state}: {count}")
    for t in TARGET_PRIORITY:
        if t in target_counts:
            print(f"  target {t}: {target_counts[t]}")
    print(f"\nProposals written")


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
