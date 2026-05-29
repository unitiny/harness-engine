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


def get_number(file):
    num = get_task_number(file)
    if num is None:
        print(f"[review-gate] numbered file expected: {file.name}", file=sys.stderr)
        sys.exit(1)
    return num


def get_task_stream(file, content):
    stream = get_field_value(content, "Task Stream")
    if stream:
        return stream
    if re.search("write-task|short-command|numbered-task|task-closure|review-scientific", file.name):
        return "harness-write-task-governance"
    if re.search("memory", file.name):
        return "harness-memory"
    if re.search("structure-proof|surrogate|mechanism", file.name):
        return "structure-proof"
    if re.search("event-collection|controls|probability|no-trade", file.name):
        return "event-library"
    return "general"


def read_task(file):
    content = file.read_text(encoding="utf-8", errors="replace")
    return {
        "file": file,
        "number": get_number(file),
        "content": content,
        "status": get_task_status(content),
        "stream": get_task_stream(file, content),
    }


def assert_review(review_file, review_root, task_root):
    if isinstance(review_file, list):
        review_file = review_file[0]
    if isinstance(review_file, dict):
        review_file = review_file["file"]
    if isinstance(review_file, str):
        candidate = review_file if Path(review_file).is_absolute() else str(review_root / review_file)
        review_file = Path(candidate)
    if not isinstance(review_file, Path):
        review_file = Path(review_file)

    content = review_file.read_text(encoding="utf-8", errors="replace")
    number = get_number(review_file)
    task_pattern = f"{number:03d}-*.md"
    task_files = sorted(task_root.glob(task_pattern))
    task = task_files[-1] if task_files else None

    if not task:
        print(f"[review-gate] review has no matching task brief: {review_file.name}", file=sys.stderr)
        sys.exit(1)

    for heading in [
        "Verdict",
        "Task Fit",
        "Dual-Model Scope Review",
        "Scientific Verdict",
        "Verification",
        "Task Closure Packet",
    ]:
        if not get_section_text(content, heading):
            print(f"[review-gate] review lacks required section '{heading}': {review_file.name}", file=sys.stderr)
            sys.exit(1)

    verdict = get_section_text(content, "Verdict")
    if not re.search(r"(?i)\b(PASS|PASS_WITH_RISK|FAIL|BLOCKED)\b", verdict):
        print(f"[review-gate] review Verdict lacks concrete value: {review_file.name}", file=sys.stderr)
        sys.exit(1)
    if re.search(r"(?i)\bPASS(?:_WITH_RISK)?\b", verdict):
        has_diff_evidence = bool(re.search(
            r"(?i)git\s+(diff|show|status)|diff\s+--|actual\s+diff|diff inspected\s*:\s*yes",
            content,
        ))
        if not has_diff_evidence:
            print(f"[review-gate] PASS review must include diff/git evidence: {review_file.name}", file=sys.stderr)
            sys.exit(1)

    scientific = get_section_text(content, "Scientific Verdict")
    for field in [
        "Execution verdict",
        "Research/scientific verdict",
        "Promotion allowed",
        "Blocked claims",
        "Proxy metric limitations",
    ]:
        if not re.search(re.escape(field), scientific):
            print(f"[review-gate] Scientific Verdict lacks field '{field}': {review_file.name}", file=sys.stderr)
            sys.exit(1)

    if (re.search(r"(?im)Promotion allowed\s*:\s*true", scientific) and
            not re.search(r"(?i)structure_proof_passed|microstructure_alignment_candidate|explicit approval", scientific)):
        print(f"[review-gate] promotion allowed without explicit proof state: {review_file.name}", file=sys.stderr)
        sys.exit(1)

    if (re.search(r"(?i)proxy_metric_used|proxy metric|no_full_feature_recomputation", scientific) and
            not re.search(r"(?i)Promotion allowed\s*:\s*(false|no)", scientific)):
        print(f"[review-gate] proxy metric limitation must block promotion: {review_file.name}", file=sys.stderr)
        sys.exit(1)

    verification = get_section_text(content, "Verification")
    for field in [
        "Diff inspected",
        "Scope checked against allowed files",
        "Verification rerun by reviewer",
        "Secret check performed",
        "Receipt claims contradicted by diff",
    ]:
        if not re.search(re.escape(field), verification):
            print(f"[review-gate] Verification lacks field '{field}': {review_file.name}", file=sys.stderr)
            sys.exit(1)

    scope = get_section_text(content, "Dual-Model Scope Review")
    for field in [
        "Execution receipt used",
        "Actual changed files",
        "Files outside scope",
        "Forbidden operations detected",
        "Secret or credential exposure detected",
    ]:
        if not re.search(re.escape(field), scope):
            print(f"[review-gate] Dual-Model Scope Review lacks field '{field}': {review_file.name}", file=sys.stderr)
            sys.exit(1)

    closure = get_section_text(content, "Task Closure Packet")
    for field in [
        "Review artifact written",
        "Session log updated",
        "Gate/eval evidence recorded",
        "Next-task prediction",
    ]:
        if not re.search(re.escape(field), closure):
            print(f"[review-gate] Task Closure Packet lacks field '{field}': {review_file.name}", file=sys.stderr)
            sys.exit(1)

    print(f"[review-gate] PASS: {review_file.name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--Review", default=None)
    parser.add_argument("--AllLatestStreams", action="store_true")
    args = parser.parse_args()

    try:
        harness_root = find_harness_root()
        task_root = harness_root / "task-briefs"
        review_root = harness_root / "reviews"

        if args.Review:
            review_file = Path(args.Review).resolve()
            assert_review(review_file, review_root, task_root)
            return

        tasks = []
        for f in sorted(task_root.glob("*.md")):
            t = read_task(f)
            if t["status"] in ("DONE", "BLOCKED"):
                tasks.append(t)

        if not tasks:
            print("[review-gate] PASS: no closed tasks")
            return

        if args.AllLatestStreams:
            streams = {}
            for t in tasks:
                s = t["stream"]
                if s not in streams or t["number"] > streams[s]["number"]:
                    streams[s] = t
            targets = list(streams.values())
        else:
            targets = [max(tasks, key=lambda t: t["number"])]

        for task in targets:
            review_pattern = f"{task['number']:03d}-*.md"
            reviews = sorted(review_root.glob(review_pattern))
            review = reviews[-1] if reviews else None
            if not review:
                # Backward compat: new tasks use receipts instead of reviews
                receipt_dir = harness_root / "execution-receipts"
                receipts = sorted(receipt_dir.glob(review_pattern)) if receipt_dir.exists() else []
                if receipts:
                    import subprocess
                    r = subprocess.run(
                        [sys.executable, str(Path(__file__).parent / "receipt_gate.py"),
                         "--Receipt", str(receipts[-1])],
                    )
                    if r.returncode != 0:
                        sys.exit(1)
                    continue
                print(f"[review-gate] missing review for task: {task['file'].name}", file=sys.stderr)
                sys.exit(1)
            assert_review(review, review_root, task_root)

    except SystemExit:
        raise
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
