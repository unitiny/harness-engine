import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import (
    find_repo_root,
    find_harness_root,
    get_section_text,
    get_field_value,
    get_task_status,
    get_task_number,
)


REQUIRED_SECTIONS = [
    "Task",
    "Files Changed",
    "Summary",
    "Acceptance Criteria Status",
    "Commands Run",
    "Scope Check",
    "Scope Independent Check",
    "Acceptance Verification",
    "Deliverable File Existence Check",
    "API Permission Check",
    "Gate Evidence",
    "Verification Self-Assessment",
    "Memory Promotion Decisions",
    "Next-Task Prediction",
]

SCOPE_CHECK_FIELDS = [
    "Changed only allowed files",
    "Performed forbidden operations",
]

SECURITY_CHECK_FIELDS = [
    "Secrets added or exposed",
    "Raw model output persisted",
    "Trust boundary violations",
    "Unauthorized tenant access",
    "AI permission gateway bypass",
]

MEMORY_TARGETS = [
    "project-memory.md",
    "decision-log.md",
]

VERIFICATION_FIELDS = [
    "Diff inspected",
    "Scope checked programmatically",
    "Receipt claims contradicted by diff",
]


def has_blocked_evaluator_repair(content):
    """Return true only when a BLOCKED receipt proposes a future checker/eval repair."""
    negative_pattern = re.compile(
        r"(?i)\b(no|without|missing|lacks?|none|not)\b.{0,80}\b(evaluator|checker|eval|gate)\b.{0,80}\b(proposal|repair|coverage|fix)\b"
    )
    positive_patterns = [
        r"(?i)\b(evaluator|checker|eval|gate)\b.{0,80}\b(proposal|repair|coverage|fix)\b",
        r"(?i)\b(propose|add|require|create)\b.{0,80}\b(evaluator|checker|eval|gate)\b",
        r"(?i)\bwould catch\b.{0,80}\b(earlier|next|future|before)\b",
    ]
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    for line in lines:
        if negative_pattern.search(line):
            continue
        if any(re.search(pattern, line) for pattern in positive_patterns):
            return True
    return False


def get_number(file):
    num = get_task_number(file)
    if num is None:
        print(f"[receipt-gate] numbered file expected: {file.name}", file=sys.stderr)
        sys.exit(1)
    return num


def get_required_section(content, headings, receipt_name):
    if isinstance(headings, str):
        headings = [headings]
    for heading in headings:
        body = get_section_text(content, heading)
        if body:
            return body
    print(f"[receipt-gate] receipt lacks required section '{headings[0]}': {receipt_name}", file=sys.stderr)
    sys.exit(1)


def _matching_task_file(receipt_file, task_root):
    number = get_number(receipt_file)
    task_pattern = f"{number:03d}-*.md"
    task_files = sorted(task_root.glob(task_pattern))
    if not task_files:
        print(f"[receipt-gate] receipt has no matching task brief: {receipt_file.name}", file=sys.stderr)
        sys.exit(1)
    return task_files[-1]


def _is_frontend_task(task_content):
    layer = get_section_text(task_content, "Layer").lower()
    scope = get_section_text(task_content, "Scope Contract").lower()
    full_text = task_content.lower()
    return (
        "frontend" in layer
        or "openclacky/lib/clacky/web" in scope
        or "harness-engine/acceptance/scenarios" in scope
        or "dashboard" in full_text and "web ui" in full_text
    )


def _frontend_acceptance_evidence_missing(gate_evidence):
    evidence = gate_evidence.lower()
    required_groups = [
        ("acceptance_gate", "acceptance gate", "acceptance-gate"),
        ("playwright", "browser acceptance"),
        ("five-layer", "five layer", "l1", "l2", "l3", "l4", "l5"),
    ]
    for group in required_groups:
        if not any(token in evidence for token in group):
            return True
    if not all(layer in evidence for layer in ("l1", "l2", "l3", "l4")) and "five" not in evidence:
        return True
    if not re.search(r"(?i)\b(pass|passed|0 failed|scenarios?:\s*\d+\s+passed)", gate_evidence):
        return True
    return False


def assert_receipt(receipt_file, task_root):
    if isinstance(receipt_file, str):
        receipt_file = Path(receipt_file)
    if not receipt_file.exists():
        print(f"[receipt-gate] receipt not found: {receipt_file}", file=sys.stderr)
        sys.exit(1)
    harness_root = find_harness_root()
    task_briefs_root = (harness_root / "task-briefs").resolve()
    try:
        receipt_file.resolve().relative_to(task_briefs_root)
        print(
            f"[receipt-gate] receipt must not be under task-briefs/: {receipt_file}",
            file=sys.stderr,
        )
        sys.exit(1)
    except ValueError:
        pass

    content = receipt_file.read_text(encoding="utf-8", errors="replace")

    # Validate matching task brief exists
    task_file = _matching_task_file(receipt_file, task_root)
    task_content = task_file.read_text(encoding="utf-8", errors="replace")

    # Validate all required sections exist
    for heading in REQUIRED_SECTIONS:
        body = get_section_text(content, heading)
        if not body:
            print(f"[receipt-gate] receipt lacks required section '{heading}': {receipt_file.name}", file=sys.stderr)
            sys.exit(1)
        if body.strip() in ("PENDING", "PENDING_REVIEW"):
            print(f"[receipt-gate] section '{heading}' is still PENDING: {receipt_file.name}", file=sys.stderr)
            sys.exit(1)

    # Validate Task status
    status_after = get_field_value(content, "Task status after completion")
    if status_after.upper() not in ("DONE", "BLOCKED"):
        print(f"[receipt-gate] Task status after completion must be DONE or BLOCKED: {receipt_file.name}", file=sys.stderr)
        sys.exit(1)
    if status_after.upper() == "BLOCKED":
        if not has_blocked_evaluator_repair(content):
            print(
                f"[receipt-gate] BLOCKED receipt must propose an evaluator/checker repair: {receipt_file.name}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Validate Scope Check has concrete answers
    scope_check = get_section_text(content, "Scope Check")
    for field in SCOPE_CHECK_FIELDS:
        if not re.search(re.escape(field), scope_check):
            print(f"[receipt-gate] Scope Check lacks field '{field}': {receipt_file.name}", file=sys.stderr)
            sys.exit(1)

    # Validate Security Check has concrete answers
    security = get_required_section(content, ["Security Check", "Secret And Safety Check"], receipt_file.name)
    for field in SECURITY_CHECK_FIELDS:
        if not re.search(re.escape(field), security):
            print(f"[receipt-gate] Security Check lacks field '{field}': {receipt_file.name}", file=sys.stderr)
            sys.exit(1)

    # Validate Gate Evidence — DONE tasks must have actual output
    gate_evidence = get_section_text(content, "Gate Evidence")
    if status_after.upper() == "DONE":
        if re.search(r"^\s*(not run|PENDING)\s*$", gate_evidence, re.IGNORECASE | re.MULTILINE):
            print(f"[receipt-gate] Gate Evidence must record actual results for DONE tasks: {receipt_file.name}", file=sys.stderr)
            sys.exit(1)
        if _is_frontend_task(task_content) and _frontend_acceptance_evidence_missing(gate_evidence):
            print(
                f"[receipt-gate] frontend DONE receipt must include passing Playwright five-layer acceptance evidence: {receipt_file.name}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Validate Verification Self-Assessment
    verification = get_section_text(content, "Verification Self-Assessment")
    for field in VERIFICATION_FIELDS:
        if not re.search(re.escape(field), verification):
            print(f"[receipt-gate] Verification Self-Assessment lacks field '{field}': {receipt_file.name}", file=sys.stderr)
            sys.exit(1)

    # Validate Memory Promotion Decisions cover required targets
    memory = get_section_text(content, "Memory Promotion Decisions")
    for target in MEMORY_TARGETS:
        if not re.search(re.escape(target), memory):
            print(f"[receipt-gate] Memory Promotion Decisions must address '{target}': {receipt_file.name}", file=sys.stderr)
            sys.exit(1)

    # Validate Scope Independent Check references scope_diff_gate
    scope_independent = get_section_text(content, "Scope Independent Check")
    if not re.search(r"scope_diff_gate|OK|OUTSIDE|PASS", scope_independent):
        print(f"[receipt-gate] Scope Independent Check must reference scope_diff_gate.py output: {receipt_file.name}", file=sys.stderr)
        sys.exit(1)

    # Validate Next-Task Prediction is not empty
    prediction = get_section_text(content, "Next-Task Prediction")
    if len(prediction.strip()) < 10:
        print(f"[receipt-gate] Next-Task Prediction is too short: {receipt_file.name}", file=sys.stderr)
        sys.exit(1)

    print(f"[receipt-gate] PASS: {receipt_file.name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--Receipt", default=None)
    parser.add_argument("--AllLatestStreams", action="store_true")
    args = parser.parse_args()

    try:
        harness_root = find_harness_root()
        task_root = harness_root / "task-briefs"

        if args.Receipt:
            receipt_file = Path(args.Receipt).resolve()
            assert_receipt(receipt_file, task_root)
            return

        # Find latest closed tasks
        tasks = []
        task_prefix_re = re.compile(r"^(\d{3})-")
        for f in sorted(task_root.glob("*.md")):
            if not task_prefix_re.match(f.name):
                continue
            content = f.read_text(encoding="utf-8", errors="replace")
            status = get_task_status(content)
            if status in ("DONE", "BLOCKED"):
                num = get_task_number(f)
                tasks.append({"file": f, "number": num, "status": status})

        if not tasks:
            print("[receipt-gate] PASS: no closed tasks")
            return

        if args.AllLatestStreams:
            # Group by task stream
            streams = {}
            stream_re = re.compile(r"Task Stream:\s*(.+)", re.IGNORECASE)
            for t in tasks:
                content = t["file"].read_text(encoding="utf-8", errors="replace")
                m = stream_re.search(content)
                stream = m.group(1).strip() if m else "general"
                if stream not in streams or t["number"] > streams[stream]["number"]:
                    streams[stream] = t
            targets = list(streams.values())
        else:
            targets = [max(tasks, key=lambda t: t["number"])]

        for task in targets:
            receipt_pattern = f"{task['number']:03d}-*.md"
            receipt_dir = harness_root / "execution-receipts"
            receipts = sorted(receipt_dir.glob(receipt_pattern)) if receipt_dir.exists() else []
            receipt = receipts[-1] if receipts else None
            if not receipt:
                print(f"[receipt-gate] missing receipt for task: {task['file'].name}", file=sys.stderr)
                sys.exit(1)
            assert_receipt(receipt, task_root)

    except SystemExit:
        raise
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
