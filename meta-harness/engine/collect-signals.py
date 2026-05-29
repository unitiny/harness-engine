#!/usr/bin/env python3
"""collect-signals.py — Bounded signal collection from .dev-harness artifacts.

Reads recent task briefs, execution receipts, reviews, gates, and policy refs.
Outputs compact JSON snapshots to signals/latest/.
"""

import argparse
import json
import os
import sys
import yaml
import re
from pathlib import Path
from datetime import datetime


def load_config(meta_root: Path) -> dict:
    cfg_path = meta_root / "config.yaml"
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def resolve_harness_root(meta_root: Path) -> Path:
    """Resolve the .dev-harness root relative to meta-harness."""
    return meta_root.parent / ".dev-harness"


def collect_sorted_files(directory: Path, pattern: str = "*.md", limit: int = 5) -> list[dict]:
    """Collect the latest N files matching pattern, sorted by name (which includes date)."""
    if not directory.exists():
        return []
    files = sorted(directory.glob(pattern), reverse=True)
    results = []
    for f in files[:limit]:
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            results.append({
                "filename": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "line_count": content.count("\n") + 1,
                "content": content,
                "content_hash": hash(content) & 0xFFFFFFFF,
            })
        except Exception as e:
            results.append({
                "filename": f.name,
                "path": str(f),
                "error": str(e),
            })
    return results


def extract_task_number(filename: str) -> str:
    """Extract task number from filename like '075-2026-05-21-...'."""
    parts = filename.split("-", 1)
    return parts[0] if parts else "000"


def collect_receipts(receipts_dir: Path, task_numbers: list[str]) -> list[dict]:
    """Collect receipts matching collected task numbers."""
    if not receipts_dir.exists():
        return []
    results = []
    for tn in task_numbers:
        matches = sorted(receipts_dir.glob(f"{tn}-*.md"))
        for receipt_file in matches:
            try:
                content = receipt_file.read_text(encoding="utf-8", errors="replace")
                results.append({
                    "task_number": tn,
                    "filename": receipt_file.name,
                    "path": str(receipt_file),
                    "size_bytes": receipt_file.stat().st_size,
                    "line_count": content.count("\n") + 1,
                    "content": content,
                    "content_hash": hash(content) & 0xFFFFFFFF,
                })
            except Exception as e:
                results.append({
                    "task_number": tn,
                    "filename": receipt_file.name,
                    "error": str(e),
                })
    return results


def collect_reviews(reviews_dir: Path, task_numbers: list[str]) -> list[dict]:
    """Collect reviews matching collected task numbers."""
    if not reviews_dir.exists():
        return []
    results = []
    for tn in task_numbers:
        # Reviews may have different naming patterns
        matches = list(reviews_dir.glob(f"{tn}-*.md"))
        for m in matches:
            try:
                content = m.read_text(encoding="utf-8", errors="replace")
                results.append({
                    "task_number": tn,
                    "filename": m.name,
                    "path": str(m),
                    "size_bytes": m.stat().st_size,
                    "line_count": content.count("\n") + 1,
                    "content": content,
                    "content_hash": hash(content) & 0xFFFFFFFF,
                })
            except Exception as e:
                results.append({
                    "task_number": tn,
                    "filename": m.name,
                    "error": str(e),
                })
    return results


def collect_policy_refs(harness_root: Path) -> dict:
    """Collect key governance and protocol documents."""
    policy_paths = [
        ("self_evolution_protocol", "docs/protocols/self-evolution-protocol.md"),
        ("runbook", "docs/operations/runbook.md"),
        ("review_template", "templates/review-template.md"),
        ("task_template", "templates/task-template.md"),
        ("receipt_template", "templates/execution-receipt-template.md"),
    ]
    refs = {}
    for key, rel_path in policy_paths:
        full = harness_root / rel_path
        if full.exists():
            try:
                content = full.read_text(encoding="utf-8", errors="replace")
                refs[key] = {
                    "path": str(full),
                    "size_bytes": full.stat().st_size,
                    "line_count": content.count("\n") + 1,
                    "content": content,
                }
            except Exception as e:
                refs[key] = {"path": str(full), "error": str(e)}
        else:
            refs[key] = {"path": str(full), "status": "not_found"}
    return refs


def collect_gates(harness_root: Path) -> dict:
    """Collect recent gate/check outputs if available."""
    gates = {"checks_dir_exists": False, "recent_check_files": []}
    checks_dir = harness_root / "checks"
    if checks_dir.exists():
        gates["checks_dir_exists"] = True
        # Check for current Python gate/check entrypoints.
        for f in sorted(checks_dir.glob("*.py"), reverse=True)[:5]:
            gates["recent_check_files"].append({
                "filename": f.name,
                "path": str(f),
            })
    # Check automation logs for recent gate evidence
    logs_dir = harness_root / "automation" / "logs"
    if logs_dir.exists():
        recent_runs = sorted(logs_dir.iterdir(), reverse=True)[:3]
        gates["recent_run_dirs"] = []
        for run_dir in recent_runs:
            if run_dir.is_dir():
                summary_file = run_dir / "run-summary.json"
                if summary_file.exists():
                    try:
                        content = summary_file.read_text(encoding="utf-8", errors="replace")
                        gates["recent_run_dirs"].append({
                            "dir": run_dir.name,
                            "summary_preview": content[:1000],
                        })
                    except Exception:
                        gates["recent_run_dirs"].append({
                            "dir": run_dir.name,
                            "summary": "unreadable",
                        })
    return gates


def collect_automation_logs(harness_root: Path, limit: int = 5, max_chars: int = 12000) -> list[dict]:
    """Collect bounded recent role console logs for tool-efficiency analysis."""
    logs_dir = harness_root / "automation" / "logs"
    if not logs_dir.exists():
        return []

    console_files = sorted(logs_dir.glob("run-*/round-*/*/console.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    results = []
    for path in console_files[:limit]:
        try:
            full_content = path.read_text(encoding="utf-8", errors="replace")
            content = full_content
            error_windows = extract_error_windows(full_content)
            rel_parts = path.relative_to(logs_dir).parts
            run_id = rel_parts[0] if len(rel_parts) > 0 else ""
            round_id = rel_parts[1] if len(rel_parts) > 1 else ""
            role = rel_parts[2] if len(rel_parts) > 2 else ""
            truncated = len(content) > max_chars
            if truncated:
                tail = content[-max_chars:]
                if error_windows:
                    content = "\n\n--- ERROR WINDOWS ---\n\n" + "\n\n---\n\n".join(error_windows)
                    content += "\n\n--- LOG TAIL ---\n\n" + tail
                else:
                    content = tail
            elif error_windows:
                content = full_content
            results.append({
                "path": str(path),
                "run_id": run_id,
                "round_id": round_id,
                "role": role,
                "size_bytes": path.stat().st_size,
                "content": content,
                "truncated_to_tail": truncated,
                "error_windows": error_windows,
            })
        except Exception as e:
            results.append({
                "path": str(path),
                "error": str(e),
            })
    return results


def extract_error_windows(content: str, window_chars: int = 1800, max_windows: int = 3) -> list[str]:
    """Extract bounded snippets around tool errors from a full console log."""
    patterns = [
        r"\[TOOL OUTPUT: ERROR\]",
        r"Exit code\s+\d+",
        r"unexpected EOF while looking for matching",
        r"syntax error near unexpected token",
        r"unterminated quoted string",
    ]
    matches = []
    for pattern in patterns:
        matches.extend(re.finditer(pattern, content or "", re.IGNORECASE))
    if not matches:
        return []

    windows = []
    seen_ranges = []
    for match in sorted(matches, key=lambda m: m.start()):
        start = max(0, match.start() - window_chars // 2)
        end = min(len(content), match.end() + window_chars // 2)

        # Expand to nearest visible tool boundary when nearby.
        tool_start = content.rfind("\n  [", 0, match.start())
        if tool_start != -1 and match.start() - tool_start < window_chars:
            start = max(0, tool_start)
        next_tool = content.find("\n  [", match.end())
        if next_tool != -1 and next_tool - match.end() < window_chars:
            end = next_tool

        if any(not (end < s or start > e) for s, e in seen_ranges):
            continue
        seen_ranges.append((start, end))
        windows.append(content[start:end].strip())
        if len(windows) >= max_windows:
            break
    return windows


def collect_run_metrics(harness_root: Path) -> list[dict]:
    """Collect per-run automation metrics for contract replay.

    This intentionally scans all run console logs, but only stores compact
    counters. The bounded role logs remain the token-facing artifact.
    """
    logs_dir = harness_root / "automation" / "logs"
    if not logs_dir.exists():
        return []

    metrics = []
    for run_dir in sorted([p for p in logs_dir.iterdir() if p.is_dir()], key=lambda p: p.name):
        console_files = sorted(run_dir.rglob("console.log"))
        combined = []
        size_bytes = 0
        latest_mtime = 0.0
        for console in console_files:
            try:
                text = console.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            combined.append(text)
            stat = console.stat()
            size_bytes += stat.st_size
            latest_mtime = max(latest_mtime, stat.st_mtime)
        content = "\n".join(combined)
        if not content:
            continue

        exit_codes = re.findall(r"__AUTO_HARNESS_EXIT_CODE:(\d+)", content)
        metrics.append({
            "run_id": run_dir.name,
            "console_files": len(console_files),
            "size_bytes": size_bytes,
            "latest_mtime": latest_mtime,
            "tool_error_count": content.count("[TOOL OUTPUT: ERROR]"),
            "timeout_count": content.count("[TIMEOUT]"),
            "exit_codes": exit_codes,
            "last_exit_code": int(exit_codes[-1]) if exit_codes else None,
            "used_spec_file": "--SpecFile" in content,
            "used_short_review_task": "new_review_draft.py --Task" in content,
            "dev_gate_passed": "[dev-gate] PASS" in content,
            "blocked_precheck": "BLOCKED_PRECHECK" in content,
            "skip_acceptance_blocked": "--SkipAcceptance is forbidden" in content,
        })
    return metrics


def classify_phase_from_role(role: str) -> str:
    """Map a role/log directory name to a stable runtime phase."""
    normalized = (role or "").strip().lower()
    known = {
        "task_writer": "task_writer",
        "implementer": "implementer",
        "reviewer": "reviewer",
        "preflight": "preflight",
        "semantic": "semantic_triage",
    }
    return known.get(normalized, normalized or "unknown")


def collect_runtime_trace(harness_root: Path) -> dict:
    """Build a compact runtime trace from automation log file metadata.

    The active harness does not yet emit explicit span events. This first
    version derives role spans from console logs so meta-harness can report
    speed and reliability without changing the execution loop first.
    """
    logs_dir = harness_root / "automation" / "logs"
    if not logs_dir.exists():
        return {
            "schema_version": 1,
            "source": "automation_console_files",
            "runs_analyzed": 0,
            "latest_run_id": "",
            "total_duration_ms": 0,
            "spans": [],
            "critical_path": [],
            "phase_summary": {},
        }

    spans = []
    for console in sorted(logs_dir.glob("run-*/round-*/*/console.log")):
        try:
            text = console.read_text(encoding="utf-8", errors="replace")
            stat = console.stat()
        except Exception:
            continue

        rel_parts = console.relative_to(logs_dir).parts
        run_id = rel_parts[0] if len(rel_parts) > 0 else ""
        round_id = rel_parts[1] if len(rel_parts) > 1 else ""
        role = rel_parts[2] if len(rel_parts) > 2 else ""
        phase = classify_phase_from_role(role)
        line_count = text.count("\n") + 1 if text else 0
        duration_ms = max(1, int(stat.st_size / 80) + line_count)
        tool_error_count = text.count("[TOOL OUTPUT: ERROR]")
        timeout_count = text.count("[TIMEOUT]")
        exit_codes = re.findall(r"__AUTO_HARNESS_EXIT_CODE:(\d+)", text)
        last_exit_code = int(exit_codes[-1]) if exit_codes else None
        status = "pass"
        if timeout_count:
            status = "timeout"
        elif tool_error_count or (last_exit_code is not None and last_exit_code != 0):
            status = "fail"

        spans.append({
            "run_id": run_id,
            "round_id": round_id,
            "role": role,
            "phase": phase,
            "path": str(console),
            "started_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "ended_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "duration_ms": duration_ms,
            "status": status,
            "tool_error_count": tool_error_count,
            "timeout_count": timeout_count,
            "exit_code": last_exit_code,
            "size_bytes": stat.st_size,
            "line_count": line_count,
        })

    runs = sorted({span["run_id"] for span in spans if span.get("run_id")})
    latest_run_id = ""
    if spans:
        latest_span = sorted(spans, key=lambda span: (span.get("ended_at", ""), span.get("run_id", "")), reverse=True)[0]
        latest_run_id = latest_span.get("run_id", "")

    latest_spans = [span for span in spans if span.get("run_id") == latest_run_id] if latest_run_id else spans
    phase_summary = {}
    for span in latest_spans:
        phase = span.get("phase", "unknown")
        item = phase_summary.setdefault(phase, {
            "span_count": 0,
            "total_duration_ms": 0,
            "max_duration_ms": 0,
            "failure_count": 0,
            "timeout_count": 0,
        })
        item["span_count"] += 1
        item["total_duration_ms"] += int(span.get("duration_ms", 0))
        item["max_duration_ms"] = max(item["max_duration_ms"], int(span.get("duration_ms", 0)))
        if span.get("status") == "fail":
            item["failure_count"] += 1
        if span.get("status") == "timeout":
            item["timeout_count"] += 1

    critical_path = sorted(
        latest_spans,
        key=lambda span: int(span.get("duration_ms", 0)),
        reverse=True,
    )[:5]
    total_duration_ms = sum(int(span.get("duration_ms", 0)) for span in latest_spans)
    return {
        "schema_version": 1,
        "source": "automation_console_files",
        "runs_analyzed": len(runs),
        "latest_run_id": latest_run_id,
        "total_duration_ms": total_duration_ms,
        "spans": latest_spans,
        "critical_path": [
            {
                "phase": span.get("phase", "unknown"),
                "role": span.get("role", ""),
                "round_id": span.get("round_id", ""),
                "duration_ms": span.get("duration_ms", 0),
                "status": span.get("status", "unknown"),
                "path": span.get("path", ""),
            }
            for span in critical_path
        ],
        "phase_summary": phase_summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Collect bounded harness signals")
    parser.add_argument("--meta-root", required=True, help="Path to meta-harness root")
    parser.add_argument("--limit", type=int, default=None, help="Override default task limit")
    parser.add_argument("--all", action="store_true", help="Collect max history")
    args = parser.parse_args()

    meta_root = Path(args.meta_root).resolve()
    config = load_config(meta_root)
    harness_root = resolve_harness_root(meta_root)

    if not harness_root.exists():
        print(f"ERROR: harness root not found at {harness_root}", file=sys.stderr)
        sys.exit(1)

    sig_cfg = config.get("signal_collection", {})
    limit = args.limit or (sig_cfg.get("max_history", 50) if args.all else sig_cfg.get("recent_tasks", 5))

    # Collect task briefs
    tasks = collect_sorted_files(harness_root / "task-briefs", "*.md", limit)
    task_numbers = [extract_task_number(t["filename"]) for t in tasks if "filename" in t]

    # Collect matching receipts and reviews
    receipts = collect_receipts(harness_root / "execution-receipts", task_numbers)
    reviews = collect_reviews(harness_root / "reviews", task_numbers)

    # Collect policy references
    policy_refs = collect_policy_refs(harness_root) if sig_cfg.get("include_policy_refs", True) else {}

    # Collect gate information
    gates = collect_gates(harness_root)

    # Collect bounded automation logs for tool-efficiency signals
    log_cfg = config.get("automation_logs", {})
    automation_logs = collect_automation_logs(
        harness_root,
        limit=log_cfg.get("recent_console_logs", 5),
        max_chars=log_cfg.get("max_console_chars", 12000),
    )
    run_metrics = collect_run_metrics(harness_root)
    runtime_trace = collect_runtime_trace(harness_root)

    # Build manifest
    manifest = {
        "collection_timestamp": datetime.now().isoformat(),
        "harness_root": str(harness_root),
        "meta_root": str(meta_root),
        "task_limit": limit,
        "tasks_collected": len(tasks),
        "receipts_collected": len(receipts),
        "reviews_collected": len(reviews),
        "automation_logs_collected": len(automation_logs),
        "run_metrics_collected": len(run_metrics),
        "runtime_trace_spans_collected": len(runtime_trace.get("spans", [])),
        "policy_refs_collected": len([k for k, v in policy_refs.items() if "error" not in v and v.get("status") != "not_found"]),
    }

    # Write outputs
    out_dir = meta_root / "signals" / "latest"
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "manifest.json": manifest,
        "tasks.json": tasks,
        "receipts.json": receipts,
        "reviews.json": reviews,
        "gates.json": gates,
        "automation_logs.json": automation_logs,
        "run_metrics.json": run_metrics,
        "runtime_trace.json": runtime_trace,
        "policy_refs.json": policy_refs,
    }

    for fname, data in outputs.items():
        with open(out_dir / fname, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"  wrote {out_dir / fname}")

    print(f"\nSignal collection complete: {len(tasks)} tasks, {len(receipts)} receipts, {len(reviews)} reviews")


if __name__ == "__main__":
    main()
