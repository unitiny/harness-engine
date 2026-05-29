import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import find_repo_root, find_harness_root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--Fast", action="store_true")
    args = parser.parse_args()

    try:
        harness_root = find_harness_root()
        memory_root = harness_root / "memory"

        print(f"[memory-gate] root: {memory_root}")

        required_dirs = [
            "memory/active",
            "memory/canon",
            "memory/canon/decisions",
            "memory/canon/constraints",
            "memory/canon/facts",
            "memory/canon/lessons",
            "memory/canon/skill-candidates",
            "memory/traces",
            "memory/archive",
            "memory/indexes",
            "memory/cache",
        ]

        for d in required_dirs:
            path = harness_root / d.replace("/", os.sep)
            if not path.exists():
                print(f"[memory-gate] missing required memory directory: {d}", file=sys.stderr)
                sys.exit(1)

        build_script = Path(__file__).resolve().parent / "build_memory_index.py"
        fast_flag = ["--Fast"] if args.Fast else []
        result = subprocess.run(
            [sys.executable, str(build_script)] + fast_flag,
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            sys.exit(1)
        if result.stdout.strip():
            print(result.stdout.strip())

        required_indexes = [
            "memory/indexes/memory-manifest.json",
            "memory/indexes/retrieval-index.json",
            "memory/indexes/memory-index.md",
            "memory/indexes/stale-report.md",
        ]

        for p in required_indexes:
            full_path = harness_root / p.replace("/", os.sep)
            if not full_path.exists():
                print(f"[memory-gate] missing generated memory index: {p}", file=sys.stderr)
                sys.exit(1)

        manifest_path = harness_root / "memory" / "indexes" / "memory-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("entry_count", 0) < 1:
            print("[memory-gate] memory manifest has no entries", file=sys.stderr)
            sys.exit(1)

        active_files = []
        active_dir = memory_root / "active"
        if active_dir.exists():
            active_files.extend(active_dir.glob("*.md"))
        compat_active = memory_root / "active-context.md"
        if compat_active.exists():
            active_files.append(compat_active)

        for f in active_files:
            if f.stat().st_size > 8192:
                print(f"[memory-gate] active memory exceeds 8 KB hard cap: {f}", file=sys.stderr)
                sys.exit(1)

        canon_dir = memory_root / "canon"
        if canon_dir.exists():
            for f in canon_dir.rglob("*.md"):
                if f.stat().st_size > 65536:
                    print(f"[memory-gate] canonical memory file exceeds 64 KB hard cap: {f}", file=sys.stderr)
                    sys.exit(1)

        memory_markdown = [
            f for f in memory_root.rglob("*.md")
            if "memory/indexes/" not in f.as_posix()
            and "memory/cache/" not in f.as_posix()
        ]

        secret_pattern = r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"'][A-Za-z0-9_\-]{16,}"
        hits = []
        for f in memory_markdown:
            content = f.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                if re.search(secret_pattern, line):
                    hits.append((f, i))

        if len(hits) > 0:
            details = "\n".join(f"{f}:{lineno}" for f, lineno in hits[:10])
            print(f"[memory-gate] possible secret material found in memory files:\n{details}", file=sys.stderr)
            sys.exit(1)

        print("[memory-gate] PASS")

    except SystemExit:
        raise
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
