#!/usr/bin/env python3
"""analyze-gaps.py — Deterministic gap analysis from collected signals.

Reads signals/latest/*.json, applies heuristic rules, produces findings.json.
Finding categories: token_waste, ai_guidance_gap, delivery_quality_risk,
missing_evaluator_coverage, tool_efficiency_risk, runtime_observability_risk.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path


def load_json(path: Path) -> list | dict:
    if not path.exists():
        return [] if path.suffix == ".json" else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_section(text: str, heading: str) -> str:
    """Extract content under a markdown heading."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def has_section(text: str, heading: str) -> bool:
    return bool(re.search(rf"^##\s+{re.escape(heading)}\b", text, re.MULTILINE))


def has_subsection(text: str, heading: str) -> bool:
    return bool(re.search(rf"^###\s+{re.escape(heading)}\b", text, re.MULTILINE))


def extract_list_items(text: str, section: str) -> list[str]:
    """Extract bullet items from a section."""
    content = find_section(text, section)
    return [line.strip().lstrip("- ").strip("` ") for line in content.split("\n") if line.strip().startswith("- ")]


# --- Token Waste Detectors ---

def is_required_audit_block(paragraph: str) -> bool:
    """Return true for repeated evidence blocks that should remain explicit."""
    lower = paragraph.lower()
    audit_terms = [
        "dev-gate",
        "gate evidence",
        "receipt artifact",
        "review artifact",
        "scope check",
        "engineering verdict",
        "scientific verdict",
    ]
    if "```powershell" in lower and "dev-gate" in lower:
        return True
    return sum(1 for term in audit_terms if term in lower) >= 2


def detect_repeated_boilerplate(tasks: list[dict]) -> list[dict]:
    """Find identical paragraphs repeated across multiple task briefs."""
    findings = []
    paragraph_locations = {}  # hash -> list of filenames

    for task in tasks:
        content = task.get("content", "")
        if not content:
            continue
        # Split into paragraphs (blocks separated by blank lines)
        paragraphs = re.split(r"\n\s*\n", content)
        for para in paragraphs:
            para = para.strip()
            if len(para) < 100:  # Skip very short paragraphs
                continue
            if is_required_audit_block(para):
                continue
            h = hashlib.md5(para.encode("utf-8")).hexdigest()
            if h not in paragraph_locations:
                paragraph_locations[h] = {"text": para[:200], "files": []}
            paragraph_locations[h]["files"].append(task["filename"])

    for h, info in paragraph_locations.items():
        if len(info["files"]) >= 2:
            findings.append({
                "id": f"tw-boilerplate-{h[:8]}",
                "category": "token_waste",
                "gap_type": "missing_rule",
                "severity": "medium",
                "title": f"Repeated boilerplate in {len(info['files'])} task briefs",
                "description": f"Identical paragraph block found in: {', '.join(info['files'])}",
                "evidence": info["text"] + "...",
                "evidence_files": info["files"],
                "proposed_action": "Extract to a template or generator script to avoid repetition",
            })

    return findings


def detect_long_static_instructions(tasks: list[dict], policy_refs: dict) -> list[dict]:
    """Find instruction blocks that duplicate template content."""
    findings = []
    template_content = ""
    tmpl = policy_refs.get("task_template", {})
    if "content" in tmpl:
        template_content = tmpl["content"]

    for task in tasks:
        content = task.get("content", "")
        if not content or not template_content:
            continue
        # Check for "Scope Contract" or similar large template sections
        scope_section = find_section(content, "Scope Contract")
        if len(scope_section) > 500:
            # Check if it matches template boilerplate
            template_scope = find_section(template_content, "Scope Contract")
            if template_scope and scope_section.strip() == template_scope.strip():
                findings.append({
                    "id": f"tw-static-scope-{task['filename'][:3]}",
                    "category": "token_waste",
                    "gap_type": "bad_tool_policy",
                    "severity": "low",
                    "title": f"Task {task['filename']} copies template boilerplate verbatim",
                    "description": "Scope Contract section is identical to the task template, adding no value",
                    "evidence": scope_section[:300],
                    "evidence_files": [task["filename"]],
                    "proposed_action": "Reference template section by name instead of copying full text",
                })

    return findings


def detect_broad_historical_reads(tasks: list[dict]) -> list[dict]:
    """Detect briefs that reference entire history instead of bounded window."""
    findings = []
    broad_patterns = [
        r"all\s+(previous\s+)?tasks",
        r"entire\s+history",
        r"all\s+task\s+briefs",
        r"all\s+reviews",
        r"all\s+receipts",
        r"read\s+all",
    ]

    for task in tasks:
        content = task.get("content", "").lower()
        for pat in broad_patterns:
            if re.search(pat, content):
                findings.append({
                    "id": f"tw-broad-{task['filename'][:3]}",
                    "category": "token_waste",
                    "gap_type": "bad_workflow",
                    "severity": "medium",
                    "title": f"Task {task['filename']} references broad history",
                    "description": f"Pattern '{pat}' found — should use bounded read or index",
                    "evidence": f"Matched pattern: {pat}",
                    "evidence_files": [task["filename"]],
                    "proposed_action": "Replace with bounded read of latest N artifacts or index lookup",
                })
                break  # One match per task is enough

    return findings


# --- Tool Efficiency Detectors ---

def extract_tool_blocks(console: str) -> list[dict]:
    """Extract numbered tool blocks from a role console log."""
    blocks = []
    matches = list(re.finditer(r"^\s*\[(\d+)\]\s+([A-Za-z_][\w-]*)\s*$", console or "", re.MULTILINE))
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(console)
        blocks.append({
            "index": int(match.group(1)),
            "tool": match.group(2),
            "text": console[start:end].strip(),
        })
    return blocks


def is_shell_quoting_error(text: str) -> bool:
    lower = text.lower()
    return (
        "tool output: error" in lower
        and "bash" in lower
        and (
            "unexpected eof while looking for matching" in lower
            or "syntax error near unexpected token" in lower
            or "unterminated quoted string" in lower
        )
    )


def has_tool_output_error(text: str) -> bool:
    return "[tool output: error]" in (text or "").lower()


def summarize_tool_errors(blocks: list[dict], content: str) -> list[dict]:
    """Return bounded summaries of generic tool-output errors."""
    summaries = []
    for block in blocks:
        if not has_tool_output_error(block.get("text", "")):
            continue
        text = block.get("text", "")
        output_pos = text.lower().find("[tool output: error]")
        excerpt = text[output_pos:] if output_pos >= 0 else text
        summaries.append({
            "index": block.get("index"),
            "tool": block.get("tool", "tool"),
            "excerpt": excerpt.strip()[:1200],
        })

    if not summaries and "[tool output: error]" in (content or "").lower():
        for match in re.finditer(r"\[TOOL OUTPUT: ERROR\]", content or "", re.IGNORECASE):
            start = max(0, match.start() - 600)
            end = min(len(content), match.end() + 1000)
            summaries.append({
                "index": None,
                "tool": "unknown",
                "excerpt": content[start:end].strip()[:1200],
            })
            if len(summaries) >= 3:
                break
    return summaries


def classify_tool_error(summary: dict, content: str) -> dict:
    """Classify known recurring tool-error patterns into concrete repair targets."""
    excerpt = summary.get("excerpt", "")
    text = f"{excerpt}\n{content or ''}".lower()

    if "acceptance gate: fail" in text and re.search(r"scenarios:\s+\d+\s+passed,\s+\d+\s+failed", text):
        return {
            "gap_type": "product_acceptance_failure",
            "title_suffix": "product acceptance failure",
            "proposed_action": (
                "Route the next repair to the current product task: inspect acceptance report scenario names, "
                "first failed step, app route/controller/view/API behavior, and service startup assumptions. "
                "Do not propose harness or meta-harness repair unless the evidence proves the evaluator itself "
                "is wrong and the task explicitly scopes evaluator files."
            ),
        }

    if (
        "can't open file" in text
        and "cockpit-api" in text
        and "harness-engine" in text
        and "new_task_brief.py" in text
    ):
        return {
            "gap_type": "wrong_working_directory",
            "title_suffix": "wrong working directory for harness generator",
            "proposed_action": (
                "Update task_writer workflow to invoke harness generators from repo root "
                "or via a repo-root absolute path; never call new_task_brief.py from inside cockpit-api/."
            ),
        }

    if (
        "cd: cockpit-api: no such file or directory" in text
        or "cannot access 'harness-engine/.dev-harness/" in text
    ):
        return {
            "gap_type": "wrong_working_directory",
            "title_suffix": "relative cd failed from wrong working directory",
            "proposed_action": (
                "Require agents to resolve repo root before app or harness commands, then use "
                "repo root absolute paths or an explicit verified cwd instead of relative cd cockpit-api retries."
            ),
        }

    if "file does not exist" in text and "current working directory" in text:
        return {
            "gap_type": "blind_file_read",
            "title_suffix": "blind file read without existence precheck",
            "proposed_action": (
                "Require task_writer and implementer guidance to verify file exists before Read "
                "when a path is guessed or generated; use a bounded directory listing or Test-Path first, "
                "then read the confirmed path."
            ),
        }

    if (
        "[scope-diff-gate]" in text
        and "changed files outside task allowed scope" in text
        and (
            "cockpit-api/tmp/" in text
            or "harness-engine/.dev-harness/automation/" in text
            or "openclacky" in text
        )
    ):
        return {
            "gap_type": "scope_runtime_noise",
            "title_suffix": "scope gate tripped on runtime noise",
            "proposed_action": (
                "Add the reported runtime-only paths to LOCAL_WORKSPACE_PREFIXES "
                "and keep scope_diff_gate focused on task-authored changes."
            ),
        }

    if "could not generate field" in text and "unknown type" in text and "rails generate" in text:
        return {
            "gap_type": "framework_command_misuse",
            "title_suffix": "framework generator command used invalid field type",
            "proposed_action": (
                "Teach implementer guidance to prefer explicit migration files or Rails-supported "
                "generator field types before retrying generator commands."
            ),
        }

    return {
        "gap_type": "bad_tool_policy",
        "title_suffix": "[TOOL OUTPUT: ERROR]",
        "proposed_action": (
            "Ask semantic analysis why devharness guidance allowed this tool failure, "
            "whether a safer tool path or generator/file interface should be preferred, "
            "and how to reduce repeat errors and token waste next time."
        ),
    }


def detect_tool_efficiency_risks(automation_logs: list[dict]) -> list[dict]:
    """Find inefficient/error-prone tool-use loops in automation console logs."""
    findings = []

    for log in automation_logs:
        content = log.get("content", "")
        if not content:
            continue
        blocks = extract_tool_blocks(content)
        lower_content = content.lower()

        bash_blocks = [b for b in blocks if b["tool"] == "Bash"] if blocks else []
        quoting_failures = [b for b in bash_blocks if is_shell_quoting_error(b["text"])]
        window_quoting_failures = len(re.findall(r"unexpected eof while looking for matching", lower_content))
        has_generator_context = "new_task_brief.py" in content or "generator" in lower_content

        if len(quoting_failures) >= 2 or (window_quoting_failures >= 2 and has_generator_context):
            if quoting_failures:
                first = quoting_failures[0]["index"]
                last = quoting_failures[-1]["index"]
                excerpt_start = max(0, content.find(f"[{first}] Bash") - 200)
                next_marker = f"[{last + 1}]"
                excerpt_end = content.find(next_marker, excerpt_start)
                if excerpt_end == -1:
                    excerpt_end = min(len(content), content.find(f"[{last}] Bash", excerpt_start) + 2500)
                evidence = content[excerpt_start:excerpt_end].strip()
            else:
                evidence = content[:3000].strip()
            findings.append({
                "id": f"ter-bash-quoting-{log.get('run_id', 'run')}-{log.get('round_id', 'round')}-{log.get('role', 'role')}",
                "category": "tool_efficiency_risk",
                "gap_type": "bad_tool_policy",
                "severity": "high",
                "title": f"{log.get('role', 'agent')} repeated Bash quoting failures before generator success",
                "description": "The agent retried long generator invocations through shell strings after quoting failures, wasting tool calls and tokens.",
                "evidence": evidence[:3000],
                "evidence_files": [log.get("path", "")],
                "proposed_action": "Teach task_writer to avoid long shell-quoted generator calls: use an argument-file/spec-file interface for new_task_brief.py or a wrapper that accepts JSON, then pass only a short command.",
            })

        help_then_long_bash = False
        for idx, block in enumerate(bash_blocks[:-1]):
            if "--help" in block["text"] and "new_task_brief.py" in block["text"]:
                next_block = bash_blocks[idx + 1]
                if "new_task_brief.py" in next_block["text"] and len(next_block["text"]) > 4000:
                    help_then_long_bash = True
                    break
        if help_then_long_bash and not any(f.get("evidence_files") == [log.get("path", "")] for f in findings):
            findings.append({
                "id": f"ter-long-generator-{log.get('run_id', 'run')}-{log.get('round_id', 'round')}-{log.get('role', 'role')}",
                "category": "tool_efficiency_risk",
                "gap_type": "bad_tool_policy",
                "severity": "medium",
                "title": f"{log.get('role', 'agent')} used long shell command after generator help",
                "description": "The role learned the generator interface but still encoded a large task brief as shell arguments.",
                "evidence": content[:3000],
                "evidence_files": [log.get("path", "")],
                "proposed_action": "Provide a compact generator invocation pattern in harness_context_summary.py and support generator input from a bounded JSON/spec file.",
            })

        if not any(f.get("evidence_files") == [log.get("path", "")] for f in findings):
            error_summaries = summarize_tool_errors(blocks, content)
            if error_summaries:
                first = error_summaries[0]
                classification = classify_tool_error(first, content)
                evidence = "\n\n---\n\n".join(
                    f"[{item['index']}] {item['tool']}\n{item['excerpt']}" if item.get("index") is not None
                    else item["excerpt"]
                    for item in error_summaries[:3]
                )
                findings.append({
                    "id": f"ter-tool-output-error-{log.get('run_id', 'run')}-{log.get('round_id', 'round')}-{log.get('role', 'role')}",
                    "category": "tool_efficiency_risk",
                    "gap_type": classification["gap_type"],
                    "severity": "medium",
                    "title": f"{log.get('role', 'agent')} had {classification['title_suffix']} in {first.get('tool', 'tool')}",
                    "description": "The role encountered tool output errors that may indicate missing devharness guidance, wrong preferred tool path, or an avoidable retry/token sink.",
                    "evidence": evidence[:3000],
                    "evidence_files": [log.get("path", "")],
                    "proposed_action": classification["proposed_action"],
                })

    return findings


# --- Runtime Trace Detectors ---

def detect_runtime_trace_risks(runtime_trace: dict) -> list[dict]:
    """Find speed and reliability risks from collected runtime spans."""
    if not runtime_trace:
        return []

    findings = []
    phase_summary = runtime_trace.get("phase_summary", {}) or {}
    total_duration_ms = int(runtime_trace.get("total_duration_ms", 0) or 0)
    latest_run_id = runtime_trace.get("latest_run_id", "")

    for phase, summary in phase_summary.items():
        failures = int(summary.get("failure_count", 0) or 0)
        timeouts = int(summary.get("timeout_count", 0) or 0)
        phase_duration_ms = int(summary.get("total_duration_ms", 0) or 0)
        max_duration_ms = int(summary.get("max_duration_ms", 0) or 0)

        if failures or timeouts:
            findings.append({
                "id": f"rt-reliability-{latest_run_id or 'latest'}-{phase}",
                "category": "runtime_observability_risk",
                "gap_type": "phase_reliability_failure",
                "severity": "high" if timeouts else "medium",
                "title": f"{phase} had runtime failures in latest traced run",
                "description": f"Phase {phase} recorded failures={failures}, timeouts={timeouts}.",
                "evidence": (
                    f"run={latest_run_id}; phase={phase}; failures={failures}; "
                    f"timeouts={timeouts}; total_duration_ms={phase_duration_ms}"
                ),
                "evidence_files": [],
                "proposed_action": (
                    "Inspect the phase span logs before changing prompts; repair the first failing phase "
                    "or add a narrower guard so later phases do not consume time after an unrecoverable failure."
                ),
            })

        hot_ratio = (phase_duration_ms / total_duration_ms) if total_duration_ms else 0
        if phase_duration_ms >= 300000 or hot_ratio >= 0.50:
            findings.append({
                "id": f"rt-latency-{latest_run_id or 'latest'}-{phase}",
                "category": "runtime_observability_risk",
                "gap_type": "phase_latency_hotspot",
                "severity": "high" if phase_duration_ms >= 900000 else "medium",
                "title": f"{phase} dominates runtime critical path",
                "description": (
                    f"Phase {phase} consumed {phase_duration_ms} ms "
                    f"({hot_ratio:.0%} of traced runtime)."
                ),
                "evidence": (
                    f"run={latest_run_id}; phase={phase}; total_duration_ms={phase_duration_ms}; "
                    f"max_span_ms={max_duration_ms}; run_total_ms={total_duration_ms}"
                ),
                "evidence_files": [],
                "proposed_action": (
                    "Treat this phase as the next critical path optimization target: reduce prompt/context size, "
                    "prefer generator/spec-file paths for predictable artifacts, or split fast checks from full checks."
                ),
            })

    return findings


# --- AI Guidance Gap Detectors ---

def detect_missing_scope_contract(tasks: list[dict]) -> list[dict]:
    """Find tasks missing allowed/forbidden files or acceptance criteria."""
    findings = []

    for task in tasks:
        content = task.get("content", "")
        if not content:
            continue

        missing = []

        # Check for Scope Contract section
        scope = find_section(content, "Scope Contract")
        if not scope:
            # Try alternate headings
            scope = find_section(content, "Scope")

        if scope:
            allowed = find_section(content, "Allowed files")
            forbidden = find_section(content, "Forbidden files")
            if not allowed and not extract_list_items(content, "Scope Contract"):
                pass  # Might use different format
            elif not extract_list_items(scope, "Allowed files") and not extract_list_items(scope, "Allowed"):
                if "allowed" not in scope.lower():
                    missing.append("allowed_files")

            if not extract_list_items(scope, "Forbidden files") and not extract_list_items(scope, "Forbidden"):
                if "forbidden" not in scope.lower():
                    missing.append("forbidden_files")
        else:
            missing.append("scope_contract_section")

        # Check acceptance criteria
        if not has_section(content, "Acceptance Criteria"):
            missing.append("acceptance_criteria")

        # Check stop conditions
        if not has_section(content, "Stop Conditions"):
            missing.append("stop_conditions")

        # Check task stream
        if "task stream" not in content.lower():
            missing.append("task_stream")

        if missing:
            findings.append({
                "id": f"ag-missing-{task['filename'][:3]}",
                "category": "ai_guidance_gap",
                "gap_type": "weak_rule" if len(missing) <= 2 else "missing_rule",
                "severity": "high" if len(missing) >= 3 else "medium",
                "title": f"Task {task['filename']} missing: {', '.join(missing)}",
                "description": f"Missing guidance elements reduce implementer clarity",
                "evidence": f"Missing: {', '.join(missing)}",
                "evidence_files": [task["filename"]],
                "proposed_action": f"Add missing fields: {', '.join(missing)}",
            })

    return findings


def detect_vague_acceptance_criteria(tasks: list[dict]) -> list[dict]:
    """Find tasks with non-observable acceptance criteria."""
    findings = []
    vague_patterns = [
        r"code\s+should\s+work",
        r"everything\s+passes",
        r"no\s+errors",
        r"works\s+correctly",
        r"tested\s+and\s+verified(?!:\s*\[)",
        r"properly\s+implemented",
    ]

    for task in tasks:
        content = task.get("content", "")
        criteria = find_section(content, "Acceptance Criteria")
        if not criteria:
            continue

        for pat in vague_patterns:
            if re.search(pat, criteria, re.IGNORECASE):
                findings.append({
                    "id": f"ag-vague-{task['filename'][:3]}",
                    "category": "ai_guidance_gap",
                    "gap_type": "weak_rule",
                    "severity": "medium",
                    "title": f"Task {task['filename']} has vague acceptance criteria",
                    "description": f"Acceptance criteria contains non-observable language: '{pat}'",
                    "evidence": criteria[:300],
                    "evidence_files": [task["filename"]],
                    "proposed_action": "Replace vague criteria with observable, measurable conditions",
                })
                break

    return findings


# --- Delivery Quality Detectors ---

def detect_review_without_diff(reviews: list[dict]) -> list[dict]:
    """Find reviews that pass without referencing diff evidence."""
    findings = []

    for review in reviews:
        content = review.get("content", "")
        if not content:
            continue

        verdict = ""
        for v in ["PASS", "PASS_WITH_NOTES", "REJECT", "BLOCKED"]:
            if v in content.upper():
                verdict = v
                break

        if "PASS" in verdict:
            # Check for diff evidence
            has_diff = bool(re.search(r"git\s+diff|diff\s+--|scope.diff|actual\s+diff", content, re.IGNORECASE))
            has_git_cmd = bool(re.search(r"git\s+(log|status|diff|show)", content, re.IGNORECASE))

            if not has_diff and not has_git_cmd:
                findings.append({
                    "id": f"dq-no-diff-{review['filename'][:3]}",
                    "category": "delivery_quality_risk",
                    "gap_type": "missing_eval",
                    "severity": "high",
                    "title": f"Review {review['filename']} passes without diff evidence",
                    "description": "PASS verdict without referencing git diff or actual code changes",
                    "evidence": f"Verdict: {verdict}, no diff/git references found",
                    "evidence_files": [review["filename"]],
                    "proposed_action": "Require diff comparison evidence for PASS verdicts in review template",
                })

    return findings


def detect_missing_gate_evidence(receipts: list[dict]) -> list[dict]:
    """Find receipts that claim DONE without gate output."""
    findings = []

    for receipt in receipts:
        content = receipt.get("content", "")
        if not content:
            continue

        status = ""
        for s in ["DONE", "BLOCKED", "PASS"]:
            if s in content.upper():
                status = s
                break

        if status == "DONE":
            gate_section = find_section(content, "Commands Run")
            has_gate_output = bool(re.search(r"gate|dev-gate|check", gate_section, re.IGNORECASE))

            # Check scope section
            scope_section = find_section(content, "Scope Check")
            has_scope_check = bool(scope_section and "yes" in scope_section.lower())

            if not has_gate_output and not has_scope_check:
                findings.append({
                    "id": f"dq-no-gate-{receipt['task_number']}",
                    "category": "delivery_quality_risk",
                    "gap_type": "missing_eval",
                    "severity": "high",
                    "title": f"Receipt {receipt['filename']} DONE without gate evidence",
                    "description": "Execution claims DONE but provides no gate or scope check output",
                    "evidence": f"Status: {status}, gate output: absent, scope check: absent",
                    "evidence_files": [receipt["filename"]],
                    "proposed_action": "Require gate output in receipt for DONE status",
                })

    return findings


def detect_scope_diff_missing(receipts: list[dict]) -> list[dict]:
    """Find receipts from scope-sensitive tasks without scope-diff evidence."""
    findings = []

    for receipt in receipts:
        content = receipt.get("content", "")
        if not content:
            continue

        scope_section = find_section(content, "Scope Check")
        if not scope_section:
            continue

        # If scope check section exists but is incomplete
        lines = [l.strip() for l in scope_section.split("\n") if l.strip()]
        unanswered = [l for l in lines if l.startswith("-") and "yes/no" in l.lower()]

        if unanswered:
            findings.append({
                "id": f"dq-scope-{receipt['task_number']}",
                "category": "delivery_quality_risk",
                "gap_type": "weak_rule",
                "severity": "medium",
                "title": f"Receipt {receipt['filename']} has incomplete scope check",
                "description": "Scope check fields not fully answered",
                "evidence": f"Unanswered fields: {len(unanswered)}",
                "evidence_files": [receipt["filename"]],
                "proposed_action": "Enforce complete scope check in receipt template",
            })

    return findings


# --- Missing Evaluator Coverage Detectors ---

def detect_blocked_without_eval_repair(tasks: list[dict], receipts: list[dict]) -> list[dict]:
    """Find BLOCKED tasks without a proposed evaluator repair."""
    findings = []

    for task in tasks:
        content = task.get("content", "")
        if "BLOCKED" not in content.upper():
            continue

        # Check if any receipt or review proposes an evaluator repair
        task_num = task["filename"][:3]
        has_repair_proposal = False

        for receipt in receipts:
            if receipt.get("task_number") == task_num:
                rc = receipt.get("content", "")
                if re.search(r"evaluator|checker|repair|gate.*fix", rc, re.IGNORECASE):
                    has_repair_proposal = True
                    break

        if not has_repair_proposal:
            findings.append({
                "id": f"me-blocked-{task_num}",
                "category": "missing_evaluator_coverage",
                "gap_type": "missing_checker",
                "severity": "medium",
                "title": f"Task {task['filename']} BLOCKED without evaluator repair proposal",
                "description": "Blocked task should propose which check or eval could prevent this class of failure",
                "evidence": f"Task status: BLOCKED, no evaluator repair found in matching receipt",
                "evidence_files": [task["filename"]],
                "proposed_action": "Propose a checker or eval that would catch this blocker earlier",
            })

    return findings


def detect_risky_without_coverage(tasks: list[dict], receipts: list[dict]) -> list[dict]:
    """Find MEDIUM/HIGH risk tasks without complete evaluator coverage."""
    findings = []

    for task in tasks:
        content = task.get("content", "")
        if not content:
            continue

        # Check risk class
        risk_match = re.search(r"Risk\s+Class\s*\n\s*(LOW|MEDIUM|HIGH|BLOCKED)", content, re.IGNORECASE)
        if not risk_match or risk_match.group(1).upper() not in ("MEDIUM", "HIGH"):
            continue

        task_num = task["filename"][:3]

        # Check for eval section in task
        has_eval = has_section(content, "Eval Criteria") or has_section(content, "Verification")

        if not has_eval:
            findings.append({
                "id": f"me-risk-{task_num}",
                "category": "missing_evaluator_coverage",
                "gap_type": "missing_eval",
                "severity": "medium",
                "title": f"Task {task['filename']} ({risk_match.group(1)} risk) lacks eval criteria",
                "description": f"{risk_match.group(1)} risk task should have explicit eval criteria",
                "evidence": f"Risk class: {risk_match.group(1)}, eval criteria section: missing",
                "evidence_files": [task["filename"]],
                "proposed_action": "Add eval criteria section with replay or validation plan",
            })

    return findings


def analyze_gaps(signals_dir: Path) -> list[dict]:
    """Run all gap analyzers and return combined findings."""
    tasks = load_json(signals_dir / "tasks.json")
    receipts = load_json(signals_dir / "receipts.json")
    reviews = load_json(signals_dir / "reviews.json")
    automation_logs = load_json(signals_dir / "automation_logs.json")
    policy_refs = load_json(signals_dir / "policy_refs.json")
    runtime_trace = load_json(signals_dir / "runtime_trace.json")

    all_findings = []

    # Token waste
    all_findings.extend(detect_repeated_boilerplate(tasks))
    all_findings.extend(detect_long_static_instructions(tasks, policy_refs))
    all_findings.extend(detect_broad_historical_reads(tasks))
    all_findings.extend(detect_tool_efficiency_risks(automation_logs))
    all_findings.extend(detect_runtime_trace_risks(runtime_trace))

    # AI guidance gaps
    all_findings.extend(detect_missing_scope_contract(tasks))
    all_findings.extend(detect_vague_acceptance_criteria(tasks))

    # Delivery quality risks
    all_findings.extend(detect_review_without_diff(reviews))
    all_findings.extend(detect_missing_gate_evidence(receipts))
    all_findings.extend(detect_scope_diff_missing(receipts))

    # Missing evaluator coverage
    all_findings.extend(detect_blocked_without_eval_repair(tasks, receipts))
    all_findings.extend(detect_risky_without_coverage(tasks, receipts))

    return all_findings


def main():
    parser = argparse.ArgumentParser(description="Analyze harness gaps from collected signals")
    parser.add_argument("--signals-dir", required=True, help="Path to signals/latest/")
    parser.add_argument("--output", default=None, help="Output path for findings.json")
    args = parser.parse_args()

    signals_dir = Path(args.signals_dir).resolve()
    if not signals_dir.exists():
        print(f"ERROR: signals directory not found at {signals_dir}", file=sys.stderr)
        sys.exit(1)

    findings = analyze_gaps(signals_dir)

    output_path = Path(args.output) if args.output else signals_dir / "findings.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2, ensure_ascii=False)

    # Summary
    categories = Counter(f["category"] for f in findings)
    print(f"\nGap analysis complete: {len(findings)} findings")
    for cat, count in categories.most_common():
        print(f"  {cat}: {count}")
    print(f"\nFindings written to {output_path}")


if __name__ == "__main__":
    main()
