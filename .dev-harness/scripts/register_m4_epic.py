"""Register M4 epic from spec file, bypassing CLI encoding issues on Windows."""
import json, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import (
    to_slug, find_repo_root, find_harness_root,
    write_text, ensure_dir, die,
)
import shutil, re

SPEC = Path(__file__).resolve().parent.parent / "automation" / "epic-m4-spec.json"

def parse_acceptance_item(item, index):
    m = re.match(r"^([A-Za-z][A-Za-z0-9_.-]*)\|(.+)$", item)
    if m:
        return {"id": m.group(1).strip(), "description": m.group(2).strip(), "status": "pending"}
    return {"id": f"A{index}", "description": item.strip(), "status": "pending"}

def main():
    with open(SPEC, encoding="utf-8") as f:
        spec = json.load(f)

    root = find_repo_root()
    harness_root = find_harness_root()
    epic_root = Path(spec.get("OutputRoot", ""))
    if not epic_root.is_absolute():
        epic_root = root / epic_root
    ensure_dir(epic_root)

    # goal.md
    goal_lines = [f"# {spec['Title']} Goal", "", spec["Goal"], "",
        "## Safety Boundary", "",
        "Generated Epic documents are a contract for task generation. Task briefs must stay within this goal and the contract acceptance items."]
    write_text(epic_root / "goal.md", "\n".join(goal_lines))

    # designs/
    designs_dir = epic_root / "designs"
    entries = []
    for dp in spec.get("DesignPaths", []):
        src = root / dp
        if src.exists():
            ensure_dir(designs_dir)
            dest = designs_dir / src.name
            shutil.copy2(str(src), str(dest))
            entries.append((dp, src.name))
            print(f"  copied: {dp} -> designs/{src.name}")
        else:
            entries.append((dp, None))
            print(f"  WARNING: not found: {dp}", file=sys.stderr)

    design_lines = [f"# {spec['Title']} Design", "", "## Authoritative Docs", ""]
    for orig, local in entries:
        design_lines.append(f"- {orig}  *(full copy: designs/{local})*" if local else f"- {orig}")
    design_lines += ["", "## Design Rule", "",
        "The loop must cite this design file and bind each generated task to one contract acceptance item.",
        "", "## Reading Guide for Loop Agents", "",
        "Before writing or executing any task, the agent MUST read the full design documents",
        "listed above. For each doc with a local copy, read `designs/<filename>` relative to",
        "the epic root directory.",
        "",
        "## Task Priority", "",
        "Frontend pages (login page, Dashboard panel) MUST be prioritized before backend integration tasks.",
        "The backlog order reflects this: login page first, then Dashboard UI, then backend Tool integration."]
    write_text(epic_root / "design.md", "\n".join(design_lines))

    # backlog.md — frontend tasks first
    backlog_lines = [f"# {spec['Title']} Backlog", ""]
    for i, item in enumerate(spec.get("BacklogItems", [])):
        backlog_lines.append(f"{i + 1}. {item}")
    write_text(epic_root / "backlog.md", "\n".join(backlog_lines))

    # contract.json
    items = [parse_acceptance_item(a, i+1) for i, a in enumerate(spec.get("AcceptanceItems", []))]
    contract = {
        "version": 1,
        "epic_id": spec["EpicId"],
        "status": "active",
        "north_star": spec["Goal"],
        "acceptance_items": items,
        "forbidden_changes": spec.get("ForbiddenChanges", []),
        "completion_rule": {"all_acceptance_done": True, "final_full_gate_required": True, "reviewer_done_required": True},
    }
    write_text(epic_root / "contract.json", json.dumps(contract, indent=2, ensure_ascii=False))

    print(f"\nEpic registered: {epic_root}")
    print(f"Run loop:")
    print(f'  python harness-engine/.dev-harness/scripts/auto_harness_loop.py -MaxIterations 1 -EpicRoot "{epic_root}"')

if __name__ == "__main__":
    main()
