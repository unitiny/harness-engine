import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import find_repo_root, find_harness_root, ensure_dir, write_text, write_json


def convert_to_relative_path(file_path, harness_root):
    root_text = str(harness_root)
    path_text = str(file_path.resolve())
    if not root_text.endswith(os.sep):
        root_text = root_text + os.sep
    if path_text.lower().startswith(root_text.lower()):
        relative = path_text[len(root_text):]
    else:
        relative = path_text
    return relative.replace("\\", "/")


def get_memory_type(relative):
    if re.match(r"^memory/active/", relative):
        return "active"
    if re.match(r"^memory/canon/decisions/", relative):
        return "decision"
    if re.match(r"^memory/canon/constraints/", relative):
        return "constraint"
    if re.match(r"^memory/canon/facts/", relative):
        return "fact"
    if re.match(r"^memory/canon/lessons/", relative):
        return "lesson"
    if re.match(r"^memory/canon/skill-candidates/", relative):
        return "skill_candidate"
    if re.match(r"^memory/traces/", relative):
        return "trace"
    if re.match(r"^memory/archive/", relative):
        return "archive"
    if relative == "memory/active-context.md":
        return "active_compat"
    if relative == "memory/project-memory.md":
        return "project_memory_compat"
    if relative == "memory/session-log.md":
        return "session_log_compat"
    if relative == "memory/skill-candidates.md":
        return "skill_candidate_compat"
    if relative == "memory/memory-schema.md":
        return "schema"
    if relative == "memory/README.md":
        return "readme"
    return "memory"


def get_first_heading(content, fallback):
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def get_status(content, mem_type):
    m = re.search(r"(?im)^\s*status\s*:\s*([A-Za-z_]+)\s*$", content)
    if m:
        return m.group(1).lower()
    if mem_type == "archive":
        return "archived"
    if mem_type in ("skill_candidate", "skill_candidate_compat"):
        return "candidate"
    return "active"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--Fast", action="store_true")
    args = parser.parse_args()

    try:
        harness_root = find_harness_root()
        memory_root = harness_root / "memory"
        index_root = memory_root / "indexes"

        ensure_dir(index_root)

        files = sorted(memory_root.rglob("*.md"))
        files = [
            f for f in files
            if "memory/indexes/" not in f.as_posix()
            and "memory/cache/" not in f.as_posix()
        ]

        entries = []
        for f in files:
            relative = convert_to_relative_path(f, harness_root)
            content = f.read_text(encoding="utf-8")
            mem_type = get_memory_type(relative)
            sha = hashlib.sha256(f.read_bytes()).hexdigest().lower()
            entries.append({
                "id": re.sub(r"[^A-Za-z0-9]+", "-", relative).strip("-").lower(),
                "path": relative,
                "type": mem_type,
                "status": get_status(content, mem_type),
                "title": get_first_heading(content, f.stem),
                "bytes": f.stat().st_size,
                "sha256": sha,
                "modified_utc": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "0Z",
            })

        generated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "0Z"

        manifest = {
            "generated_utc": generated_utc,
            "source_root": "harness-engine/.dev-harness/memory",
            "entry_count": len(entries),
            "entries": entries,
        }

        manifest_path = index_root / "memory-manifest.json"
        retrieval_path = index_root / "retrieval-index.json"
        index_md_path = index_root / "memory-index.md"
        stale_path = index_root / "stale-report.md"

        write_json(manifest_path, manifest)

        retrieval_entries = [
            {
                "id": e["id"],
                "path": e["path"],
                "type": e["type"],
                "status": e["status"],
                "title": e["title"],
                "bytes": e["bytes"],
            }
            for e in entries
        ]
        retrieval = {
            "generated_utc": generated_utc,
            "entries": retrieval_entries,
        }
        write_json(retrieval_path, retrieval)

        lines = [
            "# Memory Index",
            "",
            f"Generated UTC: {generated_utc}",
            "",
            "| Type | Status | Bytes | Path | Title |",
            "|---|---|---:|---|---|",
        ]
        for e in entries:
            lines.append(f"| {e['type']} | {e['status']} | {e['bytes']} | `{e['path']}` | {e['title']} |")
        write_text(index_md_path, "\n".join(lines) + "\n")

        stale_lines = [
            "# Memory Stale Report",
            "",
            f"Generated UTC: {generated_utc}",
            "",
            "Phase 1 only checks index freshness by rebuilding indexes during gate.",
            "Rejected, superseded, and archived exclusion checks will become strict after canonical migration.",
        ]
        write_text(stale_path, "\n".join(stale_lines) + "\n")

        print(f"[memory-index] indexed {len(entries)} memory markdown file(s)")

    except SystemExit:
        raise
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
