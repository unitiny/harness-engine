import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import find_repo_root, read_text, get_list_after_label, is_local_workspace_path


def normalize_path_text(p):
    return p.replace("\\", "/").strip().strip("/")


def test_allowed_path(changed, allowed):
    changed_norm = normalize_path_text(changed)
    for item in allowed:
        allowed_norm = normalize_path_text(item)
        if not allowed_norm:
            continue
        if allowed_norm.endswith("/"):
            if changed_norm.lower().startswith(allowed_norm.lower()):
                return True
        elif changed_norm.lower() == allowed_norm.lower():
            return True
        elif changed_norm.lower().startswith(allowed_norm.lower() + "/"):
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--TaskBrief", required=True)
    parser.add_argument("--ChangedFiles", action="append", default=None)
    parser.add_argument("--ReportOnly", action="store_true")
    args = parser.parse_args()

    try:
        root = find_repo_root()

        task_path = Path(args.TaskBrief).resolve()
        task_content = task_path.read_text(encoding="utf-8", errors="replace")
        allowed = get_list_after_label(task_content, "Allowed files or paths:")

        changed_files = args.ChangedFiles
        if not changed_files or len(changed_files) == 0:
            result1 = subprocess.run(
                ["git", "-C", str(root), "diff", "--name-only", "HEAD"],
                capture_output=True, text=True
            )
            result2 = subprocess.run(
                ["git", "-C", str(root), "diff", "--name-only", "--cached"],
                capture_output=True, text=True
            )
            lines1 = result1.stdout.strip().splitlines() if result1.stdout.strip() else []
            lines2 = result2.stdout.strip().splitlines() if result2.stdout.strip() else []
            combined = list(dict.fromkeys(lines1 + lines2))
            changed_files = combined

        generated_allow = [
            "harness-engine/.dev-harness/memory/indexes/",
        ]
        effective_allowed = allowed + generated_allow

        outside = []
        unique_files = sorted(set(changed_files))
        for f in unique_files:
            if is_local_workspace_path(f):
                continue
            if not test_allowed_path(f, effective_allowed):
                outside.append(f)

        print(f"[scope-diff-gate] task: {args.TaskBrief}")
        for f in unique_files:
            if is_local_workspace_path(f):
                print(f"[scope-diff-gate] LOCAL_EXCLUDED {f}")
                continue
            if f in outside:
                print(f"[scope-diff-gate] OUTSIDE {f}")
            else:
                print(f"[scope-diff-gate] OK {f}")

        if len(outside) > 0 and not args.ReportOnly:
            details = "\n".join(f"- {f}" for f in outside)
            print(f"[scope-diff-gate] changed files outside task allowed scope:\n{details}", file=sys.stderr)
            sys.exit(1)

        print("[scope-diff-gate] PASS")

    except SystemExit:
        raise
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
