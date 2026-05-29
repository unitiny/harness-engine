#!/usr/bin/env python3
"""Build Meta-Harness experience records and evolution scores.

This is an evidence layer only. It records observed harness outcomes and scores
candidate proposals for later human review; it does not promote active rules.
"""

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_task_number(filename: str) -> str:
    match = re.match(r"^(\d+)-", filename or "")
    return match.group(1) if match else ""


def extract_task_status(content: str) -> str:
    match = re.search(r"Task Status:\s*([A-Z_]+)", content or "", re.IGNORECASE)
    return match.group(1).upper() if match else "UNKNOWN"


def extract_list_value(content: str, label: str, default: str = "") -> str:
    match = re.search(rf"^\s*-\s*{re.escape(label)}:\s*(.+?)\s*$", content or "", re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else default


def extract_section_value(content: str, heading: str, default: str = "") -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*\n+([^\n#]+)"
    match = re.search(pattern, content or "", re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else default


def extract_verdict(content: str, labels: list[str], default: str = "UNKNOWN") -> str:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*:\s*([A-Z_]+)", content or "", re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return default


def index_by_task_number(items: list[dict]) -> dict[str, dict]:
    indexed = {}
    for item in items:
        task_number = item.get("task_number") or extract_task_number(item.get("filename", ""))
        if task_number and task_number not in indexed:
            indexed[task_number] = item
    return indexed


def findings_for_task(findings: list[dict], task_filename: str, task_number: str) -> list[dict]:
    matches = []
    for finding in findings:
        files = finding.get("evidence_files", [])
        if any(task_filename == Path(f).name or task_filename in f for f in files):
            matches.append(finding)
            continue
        if task_number and task_number in str(finding.get("id", "")):
            matches.append(finding)
    return matches


def build_experience_records(
    tasks: list[dict],
    receipts: list[dict],
    reviews: list[dict],
    findings: list[dict],
) -> list[dict]:
    receipt_by_task = index_by_task_number(receipts)
    review_by_task = index_by_task_number(reviews)
    records = []

    for task in tasks:
        filename = task.get("filename", "")
        task_number = extract_task_number(filename)
        content = task.get("content", "")
        receipt = receipt_by_task.get(task_number, {})
        review = review_by_task.get(task_number, {})
        task_findings = findings_for_task(findings, filename, task_number)
        finding_categories = sorted({f.get("category", "unknown") for f in task_findings})

        receipt_content = receipt.get("content", "")
        review_content = review.get("content", "")

        records.append(
            {
                "record_id": f"exp-{task_number or len(records) + 1}",
                "task_number": task_number,
                "task_file": filename,
                "task_status": extract_task_status(content),
                "task_stream": extract_list_value(content, "Task Stream", "unknown"),
                "run_type": extract_section_value(content, "Run Type", "unknown"),
                "risk_class": extract_section_value(content, "Risk Class", "unknown").upper(),
                "task_lines": task.get("line_count", 0),
                "receipt_present": bool(receipt),
                "review_present": bool(review),
                "receipt_lines": receipt.get("line_count", 0),
                "review_lines": review.get("line_count", 0),
                "review_verdict": extract_verdict(review_content, ["Verdict", "Review verdict"]),
                "engineering_verdict": extract_verdict(receipt_content, ["Engineering verdict", "Engineering Verdict"]),
                "scientific_verdict": extract_verdict(receipt_content, ["Scientific verdict", "Scientific Verdict"]),
                "finding_count": len(task_findings),
                "finding_categories": finding_categories,
                "blocked_signal": "BLOCKED" in (content + "\n" + receipt_content + "\n" + review_content).upper(),
                "gate_pass_signal": "PASS" in review_content.upper() or "PASS" in receipt_content.upper(),
            }
        )

    return records


def load_proposal_markdown(path: Path) -> dict:
    content = path.read_text(encoding="utf-8", errors="replace")
    proposal = {
        "proposal_id": path.stem,
        "promotion_state": "",
        "target_surface": "",
    }
    state_match = re.search(r"\*\*State\*\*:\s*(.+)", content)
    surface_match = re.search(r"\*\*Surface\*\*:\s*(.+)", content)
    if state_match:
        proposal["promotion_state"] = state_match.group(1).strip()
    if surface_match:
        proposal["target_surface"] = surface_match.group(1).strip()
    return proposal


def load_current_proposals(meta_root: Path) -> list[dict]:
    proposals = []
    for folder in [meta_root / "proposals" / "candidate", meta_root / "proposals" / "rejected"]:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("prop-*.md")):
            proposals.append(load_proposal_markdown(path))
    return proposals


def build_evolution_scores(proposals: list[dict], findings: list[dict]) -> list[dict]:
    category_counts = Counter(f.get("category", "unknown") for f in findings)
    scores = []

    for proposal in proposals:
        state = proposal.get("promotion_state", "")
        surface = proposal.get("target_surface", "unknown")
        surface_pressure = category_counts.get(surface, 0)
        score = surface_pressure
        reasons = []

        if state == "candidate_semantic_supported":
            score += 2
            reasons.append("semantic-supported finding")
        elif state == "candidate_needs_human_review":
            score += 1
            reasons.append("uncertain but actionable candidate")
        elif state.startswith("rejected"):
            score -= 3
            reasons.append("semantic rejection or benign exception")

        if surface == "missing_evaluator_coverage":
            score += 2
            reasons.append("evaluator coverage affects future blocker prevention")
        elif surface == "delivery_quality_risk":
            score += 1
            reasons.append("delivery risk affects closure quality")
        elif surface == "token_waste":
            score += 0
            reasons.append("token economy signal")
        elif surface == "tool_efficiency_risk":
            score += 2
            reasons.append("tool efficiency affects token cost and failure rate")

        scores.append(
            {
                "proposal_id": proposal.get("proposal_id", "unknown"),
                "promotion_state": state,
                "target_surface": surface,
                "surface_finding_count": surface_pressure,
                "evolution_score": score,
                "score_reason": "; ".join(reasons) if reasons else "rule-only candidate",
                "next_action": (
                    "Require human review before promotion; replay against later experience records"
                    if score > 0
                    else "Keep rejected or monitor unless future replay evidence changes"
                ),
            }
        )

    scores.sort(key=lambda s: s["evolution_score"], reverse=True)
    return scores


def write_jsonl(path: Path, records: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Build Meta-Harness experience archive")
    parser.add_argument("--signals-dir", required=True, help="Path to signals/latest/")
    parser.add_argument("--meta-root", required=True, help="Path to meta-harness root")
    args = parser.parse_args()

    signals_dir = Path(args.signals_dir).resolve()
    meta_root = Path(args.meta_root).resolve()

    tasks = load_json(signals_dir / "tasks.json") or []
    receipts = load_json(signals_dir / "receipts.json") or []
    reviews = load_json(signals_dir / "reviews.json") or []
    findings = load_json(signals_dir / "findings.json") or []

    records = build_experience_records(tasks, receipts, reviews, findings)
    proposals = load_current_proposals(meta_root)
    scores = build_evolution_scores(proposals, findings)

    out_dir = meta_root / "experience" / "latest"
    if out_dir.exists():
        for old in out_dir.glob("*"):
            if old.is_file():
                old.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(out_dir / "experience-records.jsonl", records)
    save_json(out_dir / "experience-records.json", records)
    save_json(out_dir / "evolution-scores.json", scores)
    save_json(
        out_dir / "summary.json",
        {
            "generated_at": datetime.now().isoformat(),
            "experience_records": len(records),
            "proposals_scored": len(scores),
            "task_status_counts": dict(Counter(r["task_status"] for r in records)),
            "finding_category_counts": dict(Counter(c for r in records for c in r["finding_categories"])),
            "top_scores": scores[:5],
        },
    )

    print(f"\nExperience archive: {len(records)} records")
    print(f"Evolution scores: {len(scores)} proposals")
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()
