#!/usr/bin/env python3
"""Build the next task spec from an epic contract and structured backlog."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import read_json, write_json, die


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--EpicContract", required=True)
    parser.add_argument("--Backlog", required=True)
    parser.add_argument("--OutputSpec", default="")
    return parser.parse_args()


def normalize_status(value):
    return str(value or "pending").strip().lower()


def completed_item_ids(items):
    return {
        str(item.get("id"))
        for item in items
        if normalize_status(item.get("status")) in {"done", "complete", "completed"}
    }


def is_unblocked(item, done_ids):
    return all(str(dep) in done_ids for dep in item.get("depends_on", []) or [])


def select_backlog_item(backlog):
    items = backlog.get("items", []) or []
    done_ids = completed_item_ids(items)
    for item in items:
        if normalize_status(item.get("status")) not in {"pending", "ready", "unclaimed"}:
            continue
        if is_unblocked(item, done_ids):
            return item
    return None


def acceptance_description(contract, item_id):
    for item in contract.get("acceptance_items", []) or []:
        if item.get("id") == item_id:
            return item.get("description", "")
    return ""


def build_task_spec(contract, backlog_item):
    acceptance_item = backlog_item.get("acceptance_item", "")
    acceptance_text = acceptance_description(contract, acceptance_item)
    title = backlog_item.get("title", "Next epic task")
    allowed_paths = backlog_item.get("allowed_paths", []) or []
    verification_commands = backlog_item.get("verification_commands", []) or []
    forbidden = contract.get("forbidden_changes", []) or ["Do not modify unrelated files."]

    criteria = []
    if acceptance_text:
        criteria.append(f"{acceptance_item}: {acceptance_text}")
    criteria.extend(backlog_item.get("acceptance_criteria", []) or [])
    if not criteria:
        criteria.append(f"Complete backlog item {backlog_item.get('id', '')}: {title}")

    return {
        "Title": title,
        "TaskStream": backlog_item.get("task_stream") or "implementation",
        "RunType": backlog_item.get("run_type") or "IMPLEMENT",
        "Layer": backlog_item.get("layer") or "product",
        "RiskClass": backlog_item.get("risk_class") or "MEDIUM",
        "Intent": backlog_item.get("intent") or f"Implement backlog item {backlog_item.get('id', '')}: {title}",
        "Goal": backlog_item.get("goal") or title,
        "NonGoals": backlog_item.get("non_goals", []) or ["Do not perform unrelated refactors."],
        "AllowedPaths": allowed_paths,
        "ForbiddenPaths": backlog_item.get("forbidden_paths", []) or forbidden,
        "AllowedOperations": backlog_item.get("allowed_operations", []) or ["Edit only files listed in allowed scope."],
        "ForbiddenOperations": backlog_item.get("forbidden_operations", []) or ["Do not change dependency lockfiles unless listed in allowed scope."],
        "AcceptanceCriteria": criteria,
        "VerificationCommands": verification_commands or ["python harness-engine/.dev-harness/checks/dev_gate.py --SkipRust --Fast"],
        "StopConditions": backlog_item.get("stop_conditions", []) or ["Stop if required changes exceed allowed scope."],
        "EpicId": contract.get("epic_id", ""),
        "AcceptanceItem": acceptance_item,
        "DesignSection": backlog_item.get("design_section") or f"Backlog {backlog_item.get('id', '')}",
        "GoalReference": backlog_item.get("goal_reference") or "north_star",
    }


def main():
    args = parse_args()
    contract = read_json(Path(args.EpicContract))
    backlog = read_json(Path(args.Backlog))
    item = select_backlog_item(backlog)
    if not item:
        die("[rolling-task-planner] no unblocked pending backlog item")

    spec = build_task_spec(contract, item)
    if args.OutputSpec:
        write_json(Path(args.OutputSpec), spec)
        print(f"[rolling-task-planner] wrote {args.OutputSpec}")
    else:
        print(json.dumps(spec, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
