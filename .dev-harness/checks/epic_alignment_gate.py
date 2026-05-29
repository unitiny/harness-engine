import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import (
    get_field_value,
    normalize_inline_value,
    get_leading_token,
    read_json,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--TaskBrief", required=True)
    parser.add_argument("--EpicContract", required=True)
    args = parser.parse_args()

    try:
        task_path = Path(args.TaskBrief).resolve()
        contract_path = Path(args.EpicContract).resolve()
        task_content = task_path.read_text(encoding="utf-8", errors="replace")
        contract = read_json(contract_path)

        if not re.search(r"(?im)^##\s+Epic Alignment\s*$", task_content):
            print(f"[epic-alignment-gate] task lacks Epic Alignment section: {args.TaskBrief}", file=sys.stderr)
            sys.exit(1)

        epic_id = normalize_inline_value(get_field_value(task_content, "Epic ID"))
        acceptance_item = get_leading_token(get_field_value(task_content, "Acceptance Item"))
        design_section = get_field_value(task_content, "Design Section")
        goal_reference = normalize_inline_value(get_field_value(task_content, "Goal Reference"))

        if not epic_id or epic_id == "none":
            print("[epic-alignment-gate] missing Epic ID", file=sys.stderr)
            sys.exit(1)
        if not acceptance_item or acceptance_item == "none":
            print("[epic-alignment-gate] missing Acceptance Item", file=sys.stderr)
            sys.exit(1)
        if not design_section or design_section == "none":
            print("[epic-alignment-gate] missing Design Section", file=sys.stderr)
            sys.exit(1)
        if not goal_reference or goal_reference == "none":
            print("[epic-alignment-gate] missing Goal Reference", file=sys.stderr)
            sys.exit(1)

        if contract.get("epic_id") != epic_id:
            print(
                f"[epic-alignment-gate] task Epic ID '{epic_id}' does not match contract '{contract.get('epic_id')}'",
                file=sys.stderr,
            )
            sys.exit(1)

        matching = [item for item in contract.get("acceptance_items", []) if item.get("id") == acceptance_item]
        if len(matching) < 1:
            print(f"[epic-alignment-gate] Acceptance Item '{acceptance_item}' not found in contract", file=sys.stderr)
            sys.exit(1)

        def goal_in_contract(goal, contract):
            if goal in contract:
                return True
            for v in contract.values():
                if isinstance(v, str) and (goal == v or goal in v or v in goal):
                    return True
            return False

        if not goal_in_contract(goal_reference, contract):
            print(
                f"[epic-alignment-gate] WARN: Goal Reference '{goal_reference}' not found in contract; "
                "Epic ID and Acceptance Item matched.",
                file=sys.stderr,
            )

        print(f"[epic-alignment-gate] PASS: {epic_id} / {acceptance_item}")

    except SystemExit:
        raise
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
