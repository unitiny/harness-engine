import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import (
    get_field_value,
    get_task_status,
    get_task_number,
    to_slug,
    format_bullets,
    format_checklist,
    find_repo_root,
    find_harness_root,
    read_text,
    write_text,
    ensure_dir,
    today_iso,
    die,
)


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--SpecFile", default="", help="JSON task-brief spec. CLI arguments override fields from this file.")
    p.add_argument("--Title", default="")
    p.add_argument("--Slug", default="")
    p.add_argument("--TaskStream", default="")
    p.add_argument("--RunType", default="")
    p.add_argument("--Layer", default="")
    p.add_argument("--RiskClass", default="")
    p.add_argument("--Intent", default="")
    p.add_argument("--Goal", default="")
    p.add_argument("--NonGoals", action="append", default=[])
    p.add_argument("--AllowedPaths", action="append", default=[])
    p.add_argument("--ForbiddenPaths", action="append", default=[])
    p.add_argument("--AllowedOperations", action="append", default=[])
    p.add_argument("--ForbiddenOperations", action="append", default=[])
    p.add_argument("--AcceptanceCriteria", action="append", default=[])
    p.add_argument("--VerificationCommands", action="append", default=[])
    p.add_argument("--StopConditions", action="append", default=[])
    p.add_argument("--EpicId", default="")
    p.add_argument("--AcceptanceItem", default="")
    p.add_argument("--DesignSection", default="")
    p.add_argument("--GoalReference", default="")
    p.add_argument("--OutputPath", default="")
    p.add_argument("--Force", action="store_true")
    return merge_spec_file(p.parse_args())


SPEC_ALIASES = {
    "Title": ("Title", "title"),
    "Slug": ("Slug", "slug"),
    "TaskStream": ("TaskStream", "taskStream", "task_stream"),
    "RunType": ("RunType", "runType", "run_type"),
    "Layer": ("Layer", "layer"),
    "RiskClass": ("RiskClass", "riskClass", "risk_class"),
    "Intent": ("Intent", "intent"),
    "Goal": ("Goal", "goal"),
    "NonGoals": ("NonGoals", "nonGoals", "non_goals"),
    "AllowedPaths": ("AllowedPaths", "allowedPaths", "allowed_paths"),
    "ForbiddenPaths": ("ForbiddenPaths", "forbiddenPaths", "forbidden_paths"),
    "AllowedOperations": ("AllowedOperations", "allowedOperations", "allowed_operations"),
    "ForbiddenOperations": ("ForbiddenOperations", "forbiddenOperations", "forbidden_operations"),
    "AcceptanceCriteria": ("AcceptanceCriteria", "acceptanceCriteria", "acceptance_criteria"),
    "VerificationCommands": ("VerificationCommands", "verificationCommands", "verification_commands"),
    "StopConditions": ("StopConditions", "stopConditions", "stop_conditions"),
    "EpicId": ("EpicId", "epicId", "epic_id"),
    "AcceptanceItem": ("AcceptanceItem", "acceptanceItem", "acceptance_item"),
    "DesignSection": ("DesignSection", "designSection", "design_section"),
    "GoalReference": ("GoalReference", "goalReference", "goal_reference"),
    "OutputPath": ("OutputPath", "outputPath", "output_path"),
    "Force": ("Force", "force"),
}


SCALAR_FIELDS = [
    "Title",
    "Slug",
    "TaskStream",
    "RunType",
    "Layer",
    "RiskClass",
    "Intent",
    "Goal",
    "EpicId",
    "AcceptanceItem",
    "DesignSection",
    "GoalReference",
    "OutputPath",
]


LIST_FIELDS = [
    "NonGoals",
    "AllowedPaths",
    "ForbiddenPaths",
    "AllowedOperations",
    "ForbiddenOperations",
    "AcceptanceCriteria",
    "VerificationCommands",
    "StopConditions",
]


REQUIRED_FIELDS = [
    "Title",
    "TaskStream",
    "RunType",
    "Layer",
    "RiskClass",
    "Intent",
    "Goal",
]


def format_required_fields_hint(missing):
    required = ", ".join(REQUIRED_FIELDS)
    missing_text = ", ".join(missing)
    return (
        f"[new-task-brief] missing required fields: {missing_text}\n"
        f"[new-task-brief] SpecFile required fields: {required}\n"
        "[new-task-brief] Fix: create a JSON object with these fields, use list values for list fields, "
        "then run new_task_brief.py --SpecFile <path> from repo root."
    )


def get_spec_value(spec, field):
    for key in SPEC_ALIASES[field]:
        if key in spec:
            return spec[key]
    return None


def normalize_list(value, field):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    die(f"[new-task-brief] spec field must be a list: {field}")


def load_spec_file(path):
    spec_path = Path(path)
    try:
        spec = json.loads(read_text(spec_path))
    except json.JSONDecodeError as exc:
        die(f"[new-task-brief] invalid JSON spec file {spec_path}: {exc}")
    if not isinstance(spec, dict):
        die(f"[new-task-brief] spec file must contain a JSON object: {spec_path}")
    return spec


def merge_spec_file(args):
    if args.SpecFile:
        spec = load_spec_file(args.SpecFile)
        for field in SCALAR_FIELDS:
            if getattr(args, field):
                continue
            value = get_spec_value(spec, field)
            if value is not None:
                setattr(args, field, str(value))
        for field in LIST_FIELDS:
            if getattr(args, field):
                continue
            value = get_spec_value(spec, field)
            setattr(args, field, normalize_list(value, field))
        value = get_spec_value(spec, "Force")
        if value is not None:
            args.Force = args.Force or bool(value)

    missing = [field for field in REQUIRED_FIELDS if not getattr(args, field)]
    if missing:
        die(format_required_fields_hint(missing))
    return args


def read_task(file_path):
    content = _read_text(file_path)
    return {
        "file": file_path,
        "number": get_task_number(file_path),
        "content": content,
        "status": get_task_status(content),
        "stream": get_field_value(content, "Task Stream"),
    }


def main():
    args = parse_args()
    root = find_repo_root()
    harness_root = find_harness_root()
    task_root = harness_root / "task-briefs"
    review_root = harness_root / "reviews"

    if not args.Slug:
        args.Slug = to_slug(args.Title)

    date = today_iso()

    if args.OutputPath:
        target_path = Path(args.OutputPath)
        m = re.match(r"^(\d{3})-", target_path.name)
        task_number = int(m.group(1)) if m else 0
    else:
        latest_number = 0
        if task_root.exists():
            for f in task_root.iterdir():
                if f.is_file() and f.suffix == ".md":
                    n = get_task_number(f)
                    if n is not None and n > latest_number:
                        latest_number = n
        task_number = latest_number + 1
        target_path = task_root / f"{task_number:03d}-{date}-{args.Slug}.md"

    if target_path.exists() and not args.Force:
        die(f"[new-task-brief] output already exists. Use -Force to overwrite: {target_path}")

    previous = None
    if task_root.exists():
        candidates = []
        for f in task_root.iterdir():
            if f.is_file() and f.suffix == ".md":
                t = read_task(f)
                if (
                    t["number"] is not None
                    and t["number"] < task_number
                    and t["stream"] == args.TaskStream
                    and t["status"] in ("DONE", "BLOCKED")
                ):
                    candidates.append(t)
        if candidates:
            candidates.sort(key=lambda t: t["number"])
            previous = candidates[-1]

    if previous:
        previous_name = previous["file"].name
        previous_status = previous["status"]
        review = None
        if review_root.exists():
            for f in sorted(review_root.iterdir()):
                if f.is_file() and f.name.startswith(f"{previous['number']:03d}-") and f.suffix == ".md":
                    review = f
        review_artifact = (
            f"harness-engine/.dev-harness/reviews/{review.name}" if review else "missing - review required before execution"
        )
        receipt_artifact = "inline or review-linked receipt in previous task"
        verdict = "review required"
        if review:
            review_content = _read_text(review)
            vm = re.search(r"(?ms)^##\s+Verdict\s*\r?\n(?P<body>.*?)(?=^##\s+|\Z)", review_content)
            if vm:
                first_line = vm.group("body").strip().split("\n")[0].strip()
                if first_line:
                    verdict = first_line
    else:
        previous_name = "none - first task in this stream"
        previous_status = "not applicable"
        review_artifact = "not applicable"
        receipt_artifact = "not applicable"
        verdict = "not applicable"

    lines = []
    lines.append(f"# {args.Title}")
    lines.append("")
    lines.append("<!-- Generated by: scripts/new_task_brief.py -->")
    lines.append("")
    lines.append("## Intent")
    lines.append("")
    lines.append(args.Intent)
    lines.append("")
    lines.append("## Task Status")
    lines.append("")
    lines.append("Task Status: UNCLAIMED")
    lines.append("")
    lines.append("- Architect:")
    lines.append(f"- Created At: {date}")
    lines.append("- Claimed By:")
    lines.append("- Claimed At:")
    lines.append("- Completed At:")
    lines.append("- Status Note:")
    lines.append(f"- Task Stream: {args.TaskStream}")
    lines.append("")
    lines.append("## Previous Task Acceptance")
    lines.append("")
    lines.append(f"- Previous task: {previous_name}")
    lines.append(f"- Same-stream previous task: {previous_name}")
    lines.append(f"- Previous status: {previous_status}")
    lines.append(f"- Review artifact: {review_artifact}")
    lines.append(f"- Receipt artifact: {receipt_artifact}")
    lines.append(f"- Verdict: {verdict}")
    lines.append("- Gate evidence: to be verified by write-task gate")
    lines.append("- Residual risks: to be assessed by architect/reviewer")
    lines.append("- Impact on this task: task scoped by this generated brief")
    lines.append("- Acceptance audit performed: yes")
    lines.append("- Errors found: none known at generation time")
    lines.append("- Error-fix tasks included in this brief: none unless listed in Goal or Acceptance Criteria")
    lines.append("")
    lines.append("## Run Type")
    lines.append("")
    lines.append(args.RunType)
    lines.append("")
    lines.append("## Layer")
    lines.append("")
    lines.append(args.Layer)
    lines.append("")
    lines.append("## Risk Class")
    lines.append("")
    lines.append(args.RiskClass)
    lines.append("")
    lines.append("## Goal")
    lines.append("")
    lines.append(args.Goal)
    lines.append("")
    if args.EpicId or args.AcceptanceItem or args.DesignSection or args.GoalReference:
        lines.append("## Epic Alignment")
        lines.append("")
        lines.append(f"- Epic ID: {args.EpicId if args.EpicId else 'none'}")
        lines.append(f"- Acceptance Item: {args.AcceptanceItem if args.AcceptanceItem else 'none'}")
        lines.append(f"- Design Section: {args.DesignSection if args.DesignSection else 'none'}")
        lines.append(f"- Goal Reference: {args.GoalReference if args.GoalReference else 'none'}")
        lines.append("- Scope Drift Check: this task must stay within the named epic contract and acceptance item")
        lines.append("")
    lines.append("## Non-Goals")
    lines.append("")
    lines.extend(format_bullets(args.NonGoals))
    lines.append("")
    lines.append("## Scope Contract")
    lines.append("")
    lines.append("Allowed files or paths:")
    lines.append("")
    lines.extend(format_bullets(args.AllowedPaths))
    lines.append("")
    lines.append("Forbidden files or paths:")
    lines.append("")
    lines.extend(format_bullets(args.ForbiddenPaths))
    lines.append("")
    lines.append("Allowed operations:")
    lines.append("")
    lines.extend(format_bullets(args.AllowedOperations, fallback="edit only files listed in allowed scope"))
    lines.append("")
    lines.append("Forbidden operations unless explicitly approved:")
    lines.append("")
    combined_forbidden = args.ForbiddenOperations + [
        "opportunistic refactors",
        "dependency or lockfile changes",
        "secret/config rewrites",
        "changes outside the allowed file list",
    ]
    seen = set()
    unique_forbidden = []
    for item in combined_forbidden:
        if item not in seen:
            seen.add(item)
            unique_forbidden.append(item)
    lines.extend(format_bullets(unique_forbidden))
    lines.append("")
    lines.append("## Acceptance Criteria")
    lines.append("")
    lines.extend(format_checklist(args.AcceptanceCriteria))
    if args.Layer.lower() == "frontend" or any("openclacky/lib/clacky/web" in path for path in args.AllowedPaths):
        lines.extend(format_checklist([
            "Visible UI copy is localized for the target users; no raw i18n keys such as `dashboard.title` or `sidebar.dashboard` appear in rendered text",
            "Authenticated pages expose a visible user identity area, avatar/menu affordance, and logout action when login is in scope or already required",
            "Acceptance scenarios or tests cover visible text quality and authenticated user controls, not only DOM existence or data loading",
        ]))
    lines.append("")
    lines.append("## Required Execution Receipt")
    lines.append("")
    lines.append("Use `harness-engine/.dev-harness/templates/execution-receipt-template.md` or an inline receipt with the same fields.")
    lines.append("If task status is BLOCKED, the receipt must include an evaluator/checker repair proposal.")
    lines.append("")
    lines.append("## Verification")
    lines.append("")
    if args.VerificationCommands:
        for command in args.VerificationCommands:
            lines.append("```bash")
            lines.append(command)
            lines.append("```")
            lines.append("")
    else:
        lines.append("```bash")
        lines.append("harness-engine/.dev-harness/checks/dev_gate.py -SkipRust -Fast")
        lines.append("```")
        lines.append("")
    lines.append("## Stop Conditions")
    lines.append("")
    lines.extend(format_bullets(args.StopConditions, fallback="Required changes exceed allowed files or operations."))
    lines.append("")
    lines.append("## Rollback")
    lines.append("")
    lines.append("Revert only the files changed for this task, preserving unrelated user changes.")

    ensure_dir(target_path.parent)
    write_text(target_path, "\n".join(lines))
    print(f"[new-task-brief] wrote {target_path}")


if __name__ == "__main__":
    main()
