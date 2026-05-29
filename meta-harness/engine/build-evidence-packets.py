#!/usr/bin/env python3
"""build-evidence-packets.py — Convert rule findings into bounded evidence packets.

Each packet contains the finding plus minimal surrounding context needed for
semantic judgement. Packets are capped in size and count.
"""

import argparse
import hashlib
import json
import sys
import shutil
import re
from pathlib import Path
from datetime import datetime


def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config(meta_root: Path) -> dict:
    cfg_path = meta_root / "config.yaml"
    if not cfg_path.exists():
        return {}
    import yaml
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3] + "..."


def get_task_by_filename(tasks: list[dict], filename: str) -> dict:
    for t in tasks:
        if t.get("filename") == filename:
            return t
    return {}


def get_receipt_by_task(receipts: list[dict], task_num: str) -> dict:
    for r in receipts:
        if r.get("task_number") == task_num:
            return r
    return {}


def get_review_by_task(reviews: list[dict], task_num: str) -> dict:
    for r in reviews:
        if r.get("task_number") == task_num:
            return r
    return {}


def extract_task_number(filename: str) -> str:
    return filename.split("-", 1)[0] if filename else "000"


def extract_log_shape(evidence_files: list[str]) -> dict:
    """Extract run/role hints from a harness automation log path."""
    joined = " ".join(str(p) for p in evidence_files)
    run_match = re.search(r"run-\d{8}-\d{6}-W\d+", joined)
    if not run_match:
        run_match = re.search(r"run-[^\\/ ]+", joined)
    role_match = re.search(r"(task_writer|implementer|reviewer|preflight|semantic_triage)", joined)
    return {
        "run_id": run_match.group(0) if run_match else "",
        "role": role_match.group(1) if role_match else "",
    }


def normalize_evidence_signature(evidence: str) -> str:
    """Build a short stable signature for repeated tool/runtime failures."""
    text = re.sub(r"run-\d{8}-\d{6}-W\d+", "run-*", evidence or "")
    text = re.sub(r"round-\d+", "round-*", text)
    text = re.sub(r"\b\d+\b", "N", text)
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if any(marker in stripped for marker in ["[TOOL OUTPUT: ERROR]", "cannot access", "File has not been read", "Acceptance Gate: FAIL", "scope-diff-gate", "phase="]):
            lines.append(stripped[:160])
        if len(lines) >= 4:
            break
    if not lines:
        lines = [text.strip()[:240]]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:12]


def dedupe_key_for_finding(finding: dict) -> str:
    shape = extract_log_shape(finding.get("evidence_files", []))
    key_parts = [
        finding.get("category", ""),
        finding.get("gap_type", ""),
        shape["run_id"],
        shape["role"],
        normalize_evidence_signature(finding.get("evidence", "")),
    ]
    return "|".join(key_parts)


def dedupe_findings(findings: list[dict]) -> tuple[list[dict], dict]:
    """Collapse repeated same-run/same-role failure shapes before LLM triage."""
    by_key: dict[str, list[dict]] = {}
    for finding in findings:
        by_key.setdefault(dedupe_key_for_finding(finding), []).append(finding)

    deduped = []
    duplicate_groups = []
    for group in by_key.values():
        representative = dict(group[0])
        duplicates = group[1:]
        if duplicates:
            representative["_dedupe_group"] = {
                "duplicate_count": len(duplicates),
                "duplicate_finding_ids": [f.get("id", "unknown") for f in duplicates],
            }
            duplicate_groups.append(
                {
                    "representative_finding_id": representative.get("id", "unknown"),
                    "duplicates": len(duplicates),
                    "duplicate_finding_ids": [f.get("id", "unknown") for f in duplicates],
                }
            )
        deduped.append(representative)

    budget = {
        "input_findings": len(findings),
        "deduped_findings": len(deduped),
        "semantic_calls_saved": max(0, len(findings) - len(deduped)),
        "duplicate_groups": duplicate_groups,
    }
    return deduped, budget


def build_task_goal(task: dict) -> str:
    """Extract the Goal section from a task brief."""
    import re
    content = task.get("content", "")
    m = re.search(r"^##\s+Goal\s*\n(.*?)(?=^##\s|\Z)", content, re.MULTILINE | re.DOTALL)
    return m.group(1).strip()[:500] if m else "(no Goal section found)"


def build_task_status(task: dict) -> str:
    """Extract task status."""
    import re
    content = task.get("content", "")
    m = re.search(r"Task\s+Status:\s*(\w+)", content)
    return m.group(1) if m else "UNKNOWN"


def build_review_verdict(review: dict) -> str:
    """Extract review verdict."""
    content = review.get("content", "")
    for v in ["PASS_WITH_NOTES", "PASS", "REJECT", "BLOCKED"]:
        if v in content.upper():
            return v
    return "UNKNOWN"


def build_gate_summary(receipt: dict) -> str:
    """Extract gate evidence summary from receipt."""
    import re
    content = receipt.get("content", "")
    gate_section = ""
    m = re.search(r"^##\s+Commands\s+Run\s*\n(.*?)(?=^##\s|\Z)", content, re.MULTILINE | re.DOTALL)
    if m:
        gate_section = m.group(1).strip()
    if not gate_section:
        return "(no Commands Run section)"
    return truncate(gate_section, 300)


def build_packet(
    finding: dict,
    tasks: list[dict],
    receipts: list[dict],
    reviews: list[dict],
    max_excerpt: int = 1200,
) -> dict:
    """Build one evidence packet from a finding."""
    evidence_files = finding.get("evidence_files", [])
    primary_file = evidence_files[0] if evidence_files else ""
    task_num = extract_task_number(primary_file)

    task = get_task_by_filename(tasks, primary_file)
    receipt = get_receipt_by_task(receipts, task_num)
    review = get_review_by_task(reviews, task_num)

    # Determine question for LLM based on category
    category = finding.get("category", "")
    questions = {
        "token_waste": "Is this repeated block harmful token waste, required template structure, or a benign repeat?",
        "ai_guidance_gap": "Is this missing guidance element a real problem, or is the task brief sufficiently clear without it?",
        "delivery_quality_risk": "Does this artifact truly lack quality evidence, or was quality verified by another acceptable route?",
        "missing_evaluator_coverage": "Should this failure class have evaluator coverage, or is the current level of checking sufficient?",
        "tool_efficiency_risk": "Does this tool-use trace show preventable inefficiency? Explain why devharness guidance allowed the error, how devharness should change to prevent repeat tool failures, and whether the repair target is tool policy, generator interface, workflow, checker, or no change.",
    }

    packet = {
        "packet_id": f"pkt-{finding.get('id', 'unknown')}",
        "finding_id": finding.get("id", "unknown"),
        "category": category,
        "rule_trigger": finding.get("gap_type", "unknown"),
        "why_rule_is_uncertain": f"Rule detected: {finding.get('title', '')}. Semantic context may reveal this is benign or a false positive.",
        "task_goal": build_task_goal(task) if task else "(no task context)",
        "task_status": build_task_status(task) if task else "UNKNOWN",
        "review_verdict": build_review_verdict(review) if review else "(no review)",
        "gate_evidence_summary": build_gate_summary(receipt) if receipt else "(no receipt)",
        "diff_evidence_summary": "(diff analysis not yet automated)",
        "evidence_excerpt": truncate(finding.get("evidence", ""), max_excerpt),
        "candidate_interpretation": finding.get("proposed_action", ""),
        "question_for_llm": questions.get(category, "Is this finding a true issue?"),
        "authority_boundary": "LLM judgement is advisory only. Active harness changes require human review and existing gates.",
    }
    if finding.get("_dedupe_group"):
        packet["dedupe_group"] = finding["_dedupe_group"]

    return packet


def build_all_packets(
    findings: list[dict],
    tasks: list[dict],
    receipts: list[dict],
    reviews: list[dict],
    max_packets: int = 5,
    max_packet_chars: int = 6000,
    max_excerpt: int = 1200,
) -> list[dict]:
    """Build evidence packets from findings, ranked by severity."""
    packets, _budget = build_all_packets_with_budget(
        findings,
        tasks,
        receipts,
        reviews,
        max_packets,
        max_packet_chars,
        max_excerpt,
    )
    return packets


def build_all_packets_with_budget(
    findings: list[dict],
    tasks: list[dict],
    receipts: list[dict],
    reviews: list[dict],
    max_packets: int = 5,
    max_packet_chars: int = 6000,
    max_excerpt: int = 1200,
) -> tuple[list[dict], dict]:
    """Build ranked packets and return token-economy budget metadata."""
    findings, budget = dedupe_findings(findings)
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    ranked = sorted(findings, key=lambda f: severity_rank.get(f.get("severity", "medium"), 1))

    packets = []
    for finding in ranked[:max_packets]:
        packet = build_packet(finding, tasks, receipts, reviews, max_excerpt)

        # Compute content hash for caching
        cache_key = json.dumps(packet, sort_keys=True, ensure_ascii=False)
        packet["content_hash"] = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:16]

        # Check packet size
        packet_str = json.dumps(packet, ensure_ascii=False)
        if len(packet_str) > max_packet_chars:
            packet["evidence_excerpt"] = truncate(packet["evidence_excerpt"], max_excerpt // 2)
            packet["task_goal"] = truncate(packet["task_goal"], 200)

        packets.append(packet)

    budget["packet_limit"] = max_packets
    budget["packets_emitted"] = len(packets)
    budget["packet_limit_saved"] = max(0, len(findings) - len(packets))
    budget["semantic_calls_planned"] = len(packets)
    return packets, budget


def main():
    parser = argparse.ArgumentParser(description="Build evidence packets from rule findings")
    parser.add_argument("--signals-dir", required=True, help="Path to signals/latest/")
    parser.add_argument("--meta-root", required=True, help="Path to meta-harness root")
    args = parser.parse_args()

    signals_dir = Path(args.signals_dir).resolve()
    meta_root = Path(args.meta_root).resolve()

    findings = load_json(signals_dir / "findings.json") or []
    tasks = load_json(signals_dir / "tasks.json") or []
    receipts = load_json(signals_dir / "receipts.json") or []
    reviews = load_json(signals_dir / "reviews.json") or []
    out_dir = meta_root / "evidence-packets" / "latest"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not findings:
        print("No findings to build evidence packets from.")
        with open(out_dir / "_no-findings.txt", "w", encoding="utf-8") as f:
            f.write(f"No findings at {datetime.now().isoformat()}\n")
        manifest = {
            "generated_at": datetime.now().isoformat(),
            "total_findings": 0,
            "total_packets": 0,
            "max_packets": 0,
            "packets": [],
        }
        with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        sys.exit(0)

    config = load_config(meta_root)
    pkt_cfg = config.get("evidence_packets", {})
    sem_cfg = config.get("semantic_triage", {})
    max_packets = sem_cfg.get("max_packets", 5)
    max_packet_chars = sem_cfg.get("max_packet_chars", 6000)
    max_excerpt = pkt_cfg.get("max_excerpt_chars", 1200)

    packets, token_budget = build_all_packets_with_budget(findings, tasks, receipts, reviews, max_packets, max_packet_chars, max_excerpt)

    # Write individual packet files
    for pkt in packets:
        pkt_path = out_dir / f"{pkt['packet_id']}.json"
        with open(pkt_path, "w", encoding="utf-8") as f:
            json.dump(pkt, f, indent=2, ensure_ascii=False)

    # Write packet manifest
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "total_findings": len(findings),
        "total_packets": len(packets),
        "max_packets": max_packets,
        "token_budget": token_budget,
        "packets": [{"packet_id": p["packet_id"], "finding_id": p["finding_id"], "category": p["category"], "content_hash": p["content_hash"]} for p in packets],
    }
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nEvidence packets: {len(packets)} from {len(findings)} findings")
    if token_budget.get("semantic_calls_saved"):
        print(f"  token economy: skipped {token_budget['semantic_calls_saved']} duplicate semantic call(s)")
    for p in packets:
        print(f"  {p['packet_id']}: {p['category']} -> {p['question_for_llm'][:60]}...")
    print(f"\nPackets written to {out_dir}")


if __name__ == "__main__":
    main()
