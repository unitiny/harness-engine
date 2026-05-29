# DEPRECATED: New tasks use expanded execution receipts instead of review drafts.
# See harness-engine/.dev-harness/templates/execution-receipt-template.md
# This script is kept for backward compatibility with existing review-based tasks.

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import (
    get_field_value,
    get_section_text,
    get_task_number,
    get_list_after_label,
    format_bullets,
    find_repo_root,
    find_harness_root,
    read_text,
    write_text,
    ensure_dir,
    die,
    filter_local_workspace_paths,
)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--TaskBrief", default="")
    p.add_argument("--Task", default="", help="Task number, task brief filename, or task brief path. Safer short alias for --TaskBrief.")
    p.add_argument("--OutputPath", default="")
    p.add_argument("--ChangedFiles", action="append", default=[])
    p.add_argument("--GateCommand", default="")
    p.add_argument("--GateResult", default="")
    p.add_argument("--Force", action="store_true")
    args = p.parse_args()
    if not args.TaskBrief and not args.Task:
        die("[new-review-draft] missing required task input: use --TaskBrief <path> or --Task <number|filename|path>")
    return args


def resolve_task_brief(value: str, harness_root: Path) -> Path:
    task_root = harness_root / "task-briefs"
    raw = Path(value)
    if raw.exists():
        return raw.resolve()

    if re.fullmatch(r"\d{1,3}", value.strip()):
        prefix = f"{int(value):03d}-"
        matches = sorted(task_root.glob(f"{prefix}*.md")) if task_root.exists() else []
        if len(matches) == 1:
            return matches[0].resolve()
        if len(matches) > 1:
            die(f"[new-review-draft] multiple task briefs match --Task {value}: {', '.join(m.name for m in matches)}")
        die(f"[new-review-draft] no task brief found for --Task {value} under {task_root}")

    candidate = task_root / value
    if candidate.exists():
        return candidate.resolve()

    candidate_md = task_root / f"{value}.md"
    if candidate_md.exists():
        return candidate_md.resolve()

    return raw.resolve()


def main():
    args = parse_args()
    root = find_repo_root()
    harness_root = find_harness_root()
    review_root = harness_root / "reviews"

    task_input = args.TaskBrief if args.TaskBrief else args.Task
    task_path = resolve_task_brief(task_input, harness_root)
    if not task_path.exists():
        die(f"[new-review-draft] task brief not found: {task_path}")

    task_content = read_text(task_path)
    name_match = re.match(r"^(\d{3})-(.+)\.md$", task_path.name)
    if not name_match:
        die(f"[new-review-draft] task brief must use numbered filename: {task_path.name}")

    number = name_match.group(1)
    slug = name_match.group(2)

    if not args.OutputPath:
        args.OutputPath = str(review_root / f"{number}-{slug}.md")

    output_path = Path(args.OutputPath)
    if output_path.exists() and not args.Force:
        die(f"[new-review-draft] output already exists. Use -Force to overwrite: {output_path}")

    if not args.ChangedFiles:
        result = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "HEAD"],
            capture_output=True, text=True,
        )
        unstaged = result.stdout.strip().splitlines() if result.stdout.strip() else []
        result2 = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "--cached"],
            capture_output=True, text=True,
        )
        staged = result2.stdout.strip().splitlines() if result2.stdout.strip() else []
        args.ChangedFiles = sorted(set(filter_local_workspace_paths(unstaged + staged)))
    else:
        args.ChangedFiles = filter_local_workspace_paths(args.ChangedFiles)

    allowed = get_list_after_label(task_content, "Allowed files or paths:")
    forbidden = get_list_after_label(task_content, "Forbidden files or paths:")
    task_stream = get_field_value(task_content, "Task Stream")
    previous_section = get_section_text(task_content, "Previous Task Acceptance")
    same_stream_previous = get_field_value(previous_section, "Same-stream previous task")

    status_match = re.search(r"(?im)^\s*Task Status:\s*(?P<status>[A-Z_]+)\s*$", task_content)
    task_status = status_match.group("status") if status_match else "UNKNOWN"

    intent = get_section_text(task_content, "Intent")
    goal = get_section_text(task_content, "Goal")
    non_goals = get_section_text(task_content, "Non-Goals")

    scope_script = harness_root / "checks" / "scope_diff_gate.py"
    scope_output_lines = []
    if scope_script.exists():
        scope_cmd = [sys.executable, str(scope_script), "--TaskBrief", str(task_path), "--ReportOnly"]
        scope_cmd += ["--ChangedFiles"] + args.ChangedFiles
        result = subprocess.run(scope_cmd, capture_output=True, text=True)
        scope_output_lines = result.stdout.splitlines() + result.stderr.splitlines()
    else:
        scope_output_lines = [
            "[new-review-draft] scope_diff_gate.py not found; scope report unavailable"
        ]

    files_outside = []
    for line in scope_output_lines:
        m = re.match(r"^\[scope-diff-gate\] OUTSIDE (.+)$", line)
        if m:
            files_outside.append(m.group(1))

    base_name_no_number = task_path.stem[4:] if len(task_path.stem) > 4 else task_path.stem

    lines = []
    lines.append(f"# Review {number} - {base_name_no_number}")
    lines.append("")
    lines.append("<!-- Generated by: scripts/new_review_draft.py -->")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append("PENDING_REVIEW")
    lines.append("")
    lines.append("Reviewer must replace this with PASS, PASS_WITH_RISK, FAIL, or BLOCKED after inspecting findings and verification.")
    lines.append("")
    lines.append("## Task Fit")
    lines.append("")
    lines.append(f"- Original goal: {goal.replace(chr(10), ' ').replace(chr(13), '')}")
    lines.append("- Interpreted goal: PENDING_REVIEW")
    lines.append("- Non-goals honored: PENDING_REVIEW")
    lines.append("- Scope stayed inside the intended layer: PENDING_REVIEW")
    lines.append("- Files changed:")
    lines.extend(format_bullets(args.ChangedFiles))
    lines.append(f"- Task stream: {task_stream}")
    lines.append(f"- Same-stream previous task: {same_stream_previous}")
    lines.append("- Previous task acceptance used to shape this task: PENDING_REVIEW")
    lines.append("- Write-task acceptance audit checked: PENDING_REVIEW")
    lines.append("- Acceptance errors found before task creation: PENDING_REVIEW")
    lines.append("- Error-fix scope included in task: PENDING_REVIEW")
    lines.append("")
    lines.append("## Dual-Model Scope Review")
    lines.append("")
    lines.append(f"- Task brief used: harness-engine/.dev-harness/task-briefs/{task_path.name}")
    lines.append(f"- Task status transition: {task_status}")
    lines.append("- Execution receipt used: PENDING_REVIEW")
    lines.append("- Architect/reviewer model: PENDING_REVIEW")
    lines.append("- Implementer model: PENDING_REVIEW")
    lines.append("- Allowed files or paths:")
    lines.extend(format_bullets(allowed))
    lines.append("- Actual changed files:")
    lines.extend(format_bullets(args.ChangedFiles))
    lines.append("- Files outside scope:")
    lines.extend(format_bullets(files_outside))
    lines.append("- Forbidden operations detected: PENDING_REVIEW")
    lines.append("- Opportunistic cleanup/refactor detected: PENDING_REVIEW")
    lines.append("- Dependency/lockfile changes detected: PENDING_REVIEW")
    lines.append("- Secret or credential exposure detected: PENDING_REVIEW")
    lines.append("- Raw model output persisted: PENDING_REVIEW")
    lines.append("")
    lines.append("## Instruction Hierarchy")
    lines.append("")
    lines.append("- Higher-authority rules checked: PENDING_REVIEW")
    lines.append("- Lower-authority content treated as evidence, not command: PENDING_REVIEW")
    lines.append("- Conflicts found: PENDING_REVIEW")
    lines.append("- Resolution: PENDING_REVIEW")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    lines.append("- Severity: PENDING_REVIEW")
    lines.append("- File: PENDING_REVIEW")
    lines.append("- Issue: PENDING_REVIEW")
    lines.append("- Fix: PENDING_REVIEW")
    lines.append("")
    lines.append("## Architecture Drift")
    lines.append("")
    lines.append("PENDING_REVIEW")
    lines.append("")
    lines.append("## Trust Boundary")
    lines.append("")
    lines.append("PENDING_REVIEW")
    lines.append("")
    lines.append("## Scientific Verdict")
    lines.append("")
    lines.append("- Execution verdict: PENDING_REVIEW")
    lines.append("- Research/scientific verdict: not applicable unless task touches research proof, validation, model scoring, event labels, or strategy claims")
    lines.append("- Promotion allowed: false/no unless explicitly justified by reviewer")
    lines.append("- Blocked claims: PENDING_REVIEW")
    lines.append("- Proxy metric limitations: PENDING_REVIEW")
    lines.append("- Required next proof before promotion: PENDING_REVIEW")
    lines.append("")
    lines.append("## OpenAI Compliance")
    lines.append("")
    lines.append("- API usage follows docs/policies/openai-policy.md: PENDING_REVIEW")
    lines.append("- Token budget recorded when applicable: PENDING_REVIEW")
    lines.append("- Rule/cache alternative considered: PENDING_REVIEW")
    lines.append("")
    lines.append("## Eval Quality")
    lines.append("")
    lines.append("- Checks matched the task risk: PENDING_REVIEW")
    lines.append("- Checks were too narrow: PENDING_REVIEW")
    lines.append("- Checks were too broad or slow: PENDING_REVIEW")
    lines.append("- Future agents could game the eval: PENDING_REVIEW")
    lines.append("")
    lines.append("## Verification")
    lines.append("")
    lines.append("- Diff inspected: PENDING_REVIEW")
    lines.append(f"- Scope checked against allowed files: {'yes' if len(files_outside) == 0 else 'no'}")
    lines.append("- Verification rerun by reviewer: PENDING_REVIEW")
    lines.append("- Verification not rerun and why: PENDING_REVIEW")
    lines.append("- Secret check performed: PENDING_REVIEW")
    lines.append("- Receipt claims contradicted by diff: PENDING_REVIEW")
    lines.append("")
    lines.append(f"Gate command: {args.GateCommand}")
    lines.append("")
    lines.append(f"Gate result: {args.GateResult}")
    lines.append("")
    lines.append("## Trace Monitoring")
    lines.append("")
    lines.append("- Files read: task brief, generated scope report")
    lines.append("- Files changed:")
    lines.extend(format_bullets(args.ChangedFiles))
    lines.append("- Tool classes used: PENDING_REVIEW")
    lines.append("- Failed commands or retries: PENDING_REVIEW")
    lines.append("- Course corrections: PENDING_REVIEW")
    lines.append("- Checks skipped and why: PENDING_REVIEW")
    lines.append(f"- Final artifact paths: harness-engine/.dev-harness/reviews/{output_path.name}")
    lines.append("- Residual risks: PENDING_REVIEW")
    lines.append("")
    lines.append("## Self-Evolution Review")
    lines.append("")
    lines.append("```yaml")
    lines.append(f"task_id: {task_path.stem}")
    lines.append("outcome: pending")
    lines.append("risk_class: pending")
    lines.append("observed_issue: pending")
    lines.append("root_cause: pending")
    lines.append("harness_gap:")
    lines.append("  type: pending")
    lines.append("  explanation: pending")
    lines.append("proposed_harness_change:")
    lines.append("  target: pending")
    lines.append("  change: pending")
    lines.append("  rationale: pending")
    lines.append("evaluator_repair:")
    lines.append("  should_have_caught_this: pending")
    lines.append("  missed_by: pending")
    lines.append("  repair: pending")
    lines.append("prediction_contract:")
    lines.append("  expected_future_behavior: pending")
    lines.append("  measurable_signal: pending")
    lines.append("  replay_or_eval: pending")
    lines.append("promotion_decision: pending")
    lines.append("follow_up: pending")
    lines.append("```")
    lines.append("")
    lines.append("## Memory Updates")
    lines.append("")
    lines.append("- memory/session-log.md: PENDING_REVIEW")
    lines.append("- memory/project-memory.md: PENDING_REVIEW")
    lines.append("- memory/skill-candidates.md: PENDING_REVIEW")
    lines.append("- docs/governance/decision-log.md: PENDING_REVIEW")
    lines.append("- docs/governance/risk-register.md: PENDING_REVIEW")
    lines.append("")
    lines.append("## Task Closure Packet")
    lines.append("")
    lines.append(f"- Review artifact written: harness-engine/.dev-harness/reviews/{output_path.name}")
    lines.append("- Session log updated: PENDING_REVIEW")
    lines.append("- Durable memory updated or explicitly rejected: PENDING_REVIEW")
    lines.append("- Skill candidate updated or explicitly rejected: PENDING_REVIEW")
    lines.append("- Decision/risk log updated or explicitly rejected: PENDING_REVIEW")
    lines.append("- Gate/eval evidence recorded: PENDING_REVIEW")
    lines.append("- Next-task prediction: PENDING_REVIEW")

    ensure_dir(output_path.parent)
    write_text(output_path, "\n".join(lines))
    print(f"[new-review-draft] wrote {output_path}")


if __name__ == "__main__":
    main()
