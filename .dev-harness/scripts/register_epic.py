import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import (
    to_slug,
    format_bullets,
    find_repo_root,
    find_harness_root,
    write_text,
    read_text,
    ensure_dir,
    die,
)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--EpicId", required=True)
    p.add_argument("--Title", required=True)
    p.add_argument("--Goal", required=True)
    p.add_argument("--DesignPaths", action="append", default=[])
    p.add_argument("--BacklogItems", action="append", default=[])
    p.add_argument("--AcceptanceItems", action="append", default=[])
    p.add_argument("--ForbiddenChanges", action="append", default=[])
    p.add_argument("--OutputRoot", default="")
    p.add_argument("--Force", action="store_true")
    return p.parse_args()


def parse_acceptance_item(item, index):
    m = re.match(r"^([A-Za-z][A-Za-z0-9_.-]*)\|(.+)$", item)
    if m:
        return {
            "id": m.group(1).strip(),
            "description": m.group(2).strip(),
            "status": "pending",
        }
    return {
        "id": f"A{index}",
        "description": item.strip(),
        "status": "pending",
    }


def parse_backlog_item(item, index):
    parts = [part.strip() for part in item.split("|")]
    if len(parts) >= 3:
        acceptance_item, task_stream, title = parts[:3]
        allowed_paths = [p.strip() for p in parts[3].split(",") if p.strip()] if len(parts) >= 4 else []
        verification_commands = [p.strip() for p in parts[4].split("&&") if p.strip()] if len(parts) >= 5 else []
        depends_on = [p.strip() for p in parts[5].split(",") if p.strip()] if len(parts) >= 6 else []
        return {
            "id": f"B{index}",
            "title": title,
            "acceptance_item": acceptance_item,
            "task_stream": task_stream,
            "status": "pending",
            "depends_on": depends_on,
            "allowed_paths": allowed_paths,
            "verification_commands": verification_commands,
            "design_section": "",
        }
    return {
        "id": f"B{index}",
        "title": item.strip(),
        "acceptance_item": "",
        "task_stream": "implementation",
        "status": "pending",
        "depends_on": [],
        "allowed_paths": [],
        "verification_commands": [],
        "design_section": "",
    }


def main():
    args = parse_args()
    root = find_repo_root()
    harness_root = find_harness_root()

    if not args.OutputRoot:
        safe_id = to_slug(args.EpicId)
        args.OutputRoot = str(harness_root / "automation" / "epics" / safe_id)

    epic_root = Path(args.OutputRoot)
    if epic_root.exists() and not args.Force:
        die(f"[register-epic] epic directory already exists. Use -Force to overwrite generated files: {epic_root}")

    ensure_dir(epic_root)

    goal_lines = []
    goal_lines.append(f"# {args.Title} Goal")
    goal_lines.append("")
    goal_lines.append(args.Goal)
    goal_lines.append("")
    goal_lines.append("## Safety Boundary")
    goal_lines.append("")
    goal_lines.append("Generated Epic documents are a contract for task generation. Task briefs must stay within this goal and the contract acceptance items.")
    write_text(epic_root / "goal.md", "\n".join(goal_lines))

    # Copy full design doc content into designs/ subdirectory
    designs_dir = epic_root / "designs"
    if args.DesignPaths:
        ensure_dir(designs_dir)
    design_doc_entries = []
    for dp in args.DesignPaths:
        src = root / dp
        if src.exists() and src.is_file():
            local_name = src.name
            dest = designs_dir / local_name
            shutil.copy2(str(src), str(dest))
            design_doc_entries.append((dp, local_name))
            print(f"[register-epic] copied design doc: {dp} -> designs/{local_name}")
        else:
            design_doc_entries.append((dp, None))
            print(f"[register-epic] WARNING: design doc not found, keeping reference only: {dp}", file=sys.stderr)

    design_lines = []
    design_lines.append(f"# {args.Title} Design")
    design_lines.append("")
    design_lines.append("## Authoritative Docs")
    design_lines.append("")
    for orig_path, local_name in design_doc_entries:
        if local_name:
            design_lines.append(f"- {orig_path}  *(full copy: designs/{local_name})*")
        else:
            design_lines.append(f"- {orig_path}")
    design_lines.append("")
    design_lines.append("## Design Rule")
    design_lines.append("")
    design_lines.append("The loop must cite this design file and bind each generated task to one contract acceptance item.")
    design_lines.append("")
    design_lines.append("## Reading Guide for Loop Agents")
    design_lines.append("")
    design_lines.append("Before writing or executing any task, the agent MUST read the full design documents")
    design_lines.append("listed above. For each doc with a local copy, read `designs/<filename>` relative to")
    design_lines.append("the epic root directory. These contain the authoritative specifications that define")
    design_lines.append("data models, API contracts, permission rules, and acceptance criteria details.")
    write_text(epic_root / "design.md", "\n".join(design_lines))

    backlog_lines = []
    backlog_lines.append(f"# {args.Title} Backlog")
    backlog_lines.append("")
    structured_backlog = {"version": 1, "epic_id": args.EpicId, "items": []}
    if args.BacklogItems:
        for i, item in enumerate(args.BacklogItems):
            backlog_lines.append(f"{i + 1}. {item}")
            structured_backlog["items"].append(parse_backlog_item(item, i + 1))
    else:
        backlog_lines.append("1. Generate the next smallest task brief.")
        backlog_lines.append("2. Execute, verify, review, and update state.")
        structured_backlog["items"].append({
            "id": "B1",
            "title": "Generate the next smallest task brief.",
            "acceptance_item": "A1",
            "task_stream": "implementation",
            "status": "pending",
            "depends_on": [],
            "allowed_paths": [],
            "verification_commands": [],
            "design_section": "",
        })
    write_text(epic_root / "backlog.md", "\n".join(backlog_lines))
    write_text(epic_root / "backlog.json", json.dumps(structured_backlog, indent=2, ensure_ascii=False))

    items = []
    if args.AcceptanceItems:
        for i, item in enumerate(args.AcceptanceItems):
            items.append(parse_acceptance_item(item, i + 1))
    else:
        items.append({
            "id": "A1",
            "description": "Generate and execute the next smallest task for this epic.",
            "status": "pending",
        })

    contract = {
        "version": 1,
        "epic_id": args.EpicId,
        "status": "active",
        "north_star": args.Goal,
        "acceptance_items": items,
        "forbidden_changes": args.ForbiddenChanges if args.ForbiddenChanges else ["Do not modify unrelated product code."],
        "completion_rule": {
            "all_acceptance_done": True,
            "final_full_gate_required": True,
            "reviewer_done_required": True,
        },
    }
    write_text(epic_root / "contract.json", json.dumps(contract, indent=2, ensure_ascii=False))

    print(f"[register-epic] wrote {epic_root}")
    print("[register-epic] run loop:")
    print(f'harness-engine/.dev-harness/scripts/auto_harness_loop.py -MaxIterations 1 -EpicRoot "{epic_root}"')


if __name__ == "__main__":
    main()
