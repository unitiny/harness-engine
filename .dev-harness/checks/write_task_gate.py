import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import (
    find_repo_root,
    find_harness_root,
    get_field_value,
    get_section_text,
    get_task_status,
)


def get_task_number(file):
    m = re.match(r"^(\d{3})-", file.name)
    if not m:
        print(f"[write-task-gate] task brief is not numbered: {file.name}", file=sys.stderr)
        sys.exit(1)
    return int(m.group(1))


def get_task_stream(file, content):
    stream = get_field_value(content, "Task Stream")
    if stream:
        return stream

    run_type = get_section_text(content, "Run Type").strip()
    layer = get_section_text(content, "Layer").strip()

    if re.search("write-task|short-command|numbered-task|task-closure", file.name):
        return "harness-write-task-governance"
    if re.search("memory", file.name):
        return "harness-memory"
    if (re.search("META_HARNESS|HARNESS_RUNTIME|CONSTITUTION", run_type, re.IGNORECASE) or
            re.search("dev-harness|harness-engine|meta|constitution", layer, re.IGNORECASE)):
        return "harness-governance"
    if re.search("structure-proof", file.name):
        return "structure-proof"
    if re.search("probability|controls|freeze|no-trade|event-collection", file.name):
        return "event-library"
    return "general"


def read_task_brief(file, required_status=False):
    content = file.read_text(encoding="utf-8", errors="replace")
    status = get_task_status(content)
    if required_status and status == "UNKNOWN":
        print("[write-task-gate] missing Task Status", file=sys.stderr)
        sys.exit(1)
    return {
        "file": file,
        "number": get_task_number(file),
        "content": content,
        "status": status,
        "stream": get_task_stream(file, content),
        "previous_acceptance": get_section_text(content, "Previous Task Acceptance"),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--TaskBrief", default=None)
    args = parser.parse_args()

    try:
        harness_root = find_harness_root()
        task_root = harness_root / "task-briefs"
        review_root = harness_root / "reviews"

        if args.TaskBrief:
            target_file = Path(args.TaskBrief).resolve()
        else:
            md_files = sorted(task_root.glob("*.md"))
            if not md_files:
                print("[write-task-gate] no task brief found", file=sys.stderr)
                sys.exit(1)
            target_file = md_files[-1]

        target = read_task_brief(target_file, required_status=True)
        print(f"[write-task-gate] target: {target['file'].name}")
        print(f"[write-task-gate] stream: {target['stream']}")

        if not target["previous_acceptance"]:
            print(f"[write-task-gate] target task lacks Previous Task Acceptance section: {target['file'].name}", file=sys.stderr)
            sys.exit(1)

        all_tasks = []
        for f in sorted(task_root.glob("*.md")):
            all_tasks.append(read_task_brief(f))

        tasks = [
            t for t in all_tasks
            if t["number"] < target["number"]
            and t["stream"] == target["stream"]
            and t["status"] != "UNKNOWN"
        ]
        tasks.sort(key=lambda t: t["number"])

        nearest_same_stream = tasks[-1] if tasks else None
        if not nearest_same_stream:
            if not re.search(r"(?i)no same-stream previous task|none", target["previous_acceptance"]):
                print("[write-task-gate] no earlier same-stream task exists, but target does not state that explicitly", file=sys.stderr)
                sys.exit(1)
            print("[write-task-gate] PASS: no earlier same-stream task")
            return

        if nearest_same_stream["status"] in ("CLAIMED", "UNCLAIMED"):
            print(f"[write-task-gate] previous same-stream task is not closed: {nearest_same_stream['file'].name} status={nearest_same_stream['status']}", file=sys.stderr)
            sys.exit(1)

        if nearest_same_stream["status"] not in ("DONE", "BLOCKED"):
            print(f"[write-task-gate] previous same-stream task has invalid status: {nearest_same_stream['file'].name} status={nearest_same_stream['status']}", file=sys.stderr)
            sys.exit(1)

        if not re.search(re.escape(nearest_same_stream["file"].name), target["previous_acceptance"]):
            print(f"[write-task-gate] target Previous Task Acceptance must reference previous same-stream task: {nearest_same_stream['file'].name}", file=sys.stderr)
            sys.exit(1)

        review_pattern = f"{nearest_same_stream['number']:03d}-*.md"
        reviews = sorted(review_root.glob(review_pattern))
        review = reviews[-1] if reviews else None
        if not review:
            receipt_root = harness_root / "execution-receipts"
            receipts = sorted(receipt_root.glob(review_pattern)) if receipt_root.exists() else []
            receipt = receipts[-1] if receipts else None
            if not receipt:
                print(f"[write-task-gate] missing review or execution receipt for previous same-stream task: {nearest_same_stream['file'].name}", file=sys.stderr)
                sys.exit(1)
            import subprocess
            r = subprocess.run([sys.executable, str(Path(__file__).parent / "receipt_gate.py"), "--Receipt", str(receipt)])
            if r.returncode != 0:
                sys.exit(1)
            review_name = receipt.name
        else:
            review_content = review.read_text(encoding="utf-8", errors="replace")
            if not re.search(r"(?im)^##\s+Verdict\b", review_content):
                print(f"[write-task-gate] previous same-stream review lacks Verdict section: {review.name}", file=sys.stderr)
                sys.exit(1)
            if not re.search(r"(?im)^##\s+Verification\b", review_content):
                print(f"[write-task-gate] previous same-stream review lacks Verification section: {review.name}", file=sys.stderr)
                sys.exit(1)
            if not re.search(r"(?im)Result:\s*(PASS|FAIL|BLOCKED)|PASS|FAIL|BLOCKED", review_content):
                print(f"[write-task-gate] previous same-stream review lacks concrete verification result: {review.name}", file=sys.stderr)
                sys.exit(1)
            review_name = review.name

        for field in ["Acceptance audit performed", "Errors found", "Error-fix tasks included in this brief"]:
            if not re.search(re.escape(field), target["previous_acceptance"]):
                print(f"[write-task-gate] target Previous Task Acceptance lacks field: {field}", file=sys.stderr)
                sys.exit(1)

        print(f"[write-task-gate] previous same-stream task: {nearest_same_stream['file'].name}")
        print(f"[write-task-gate] review: {review_name}")
        print("[write-task-gate] PASS")

    except SystemExit:
        raise
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
