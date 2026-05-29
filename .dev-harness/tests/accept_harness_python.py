#!/usr/bin/env python3
"""Acceptance checks for the Python harness entrypoints.

This test intentionally uses only the Python standard library so it can run on
a fresh Windows checkout without adding a product dependency. It validates both
the .dev-harness Python migration and the meta-harness Python runner.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import py_compile
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEV_HARNESS = REPO_ROOT / "harness-engine" / ".dev-harness"
META_HARNESS = REPO_ROOT / "harness-engine" / "meta-harness"


DEV_HARNESS_ENTRYPOINTS = [
    DEV_HARNESS / "checks" / "build_memory_index.py",
    DEV_HARNESS / "checks" / "dev_gate.py",
    DEV_HARNESS / "checks" / "epic_alignment_gate.py",
    DEV_HARNESS / "checks" / "memory_gate.py",
    DEV_HARNESS / "checks" / "programmatic_harness_selftest.py",
    DEV_HARNESS / "checks" / "review_gate.py",
    DEV_HARNESS / "checks" / "scope_diff_gate.py",
    DEV_HARNESS / "checks" / "write_task_gate.py",
    DEV_HARNESS / "scripts" / "auto_harness_loop.py",
    DEV_HARNESS / "scripts" / "harness_context_summary.py",
    DEV_HARNESS / "scripts" / "new_review_draft.py",
    DEV_HARNESS / "scripts" / "new_task_brief.py",
    DEV_HARNESS / "scripts" / "register_epic.py",
    DEV_HARNESS / "scripts" / "rolling_task_planner.py",
    DEV_HARNESS / "harness_shared.py",
]


META_HARNESS_ENTRYPOINTS = [
    META_HARNESS / "engine" / "run_meta_review.py",
    META_HARNESS / "engine" / "collect-signals.py",
    META_HARNESS / "engine" / "analyze-gaps.py",
    META_HARNESS / "engine" / "build-evidence-packets.py",
    META_HARNESS / "engine" / "semantic-triage.py",
    META_HARNESS / "engine" / "propose-repairs.py",
    META_HARNESS / "engine" / "replay-contracts.py",
    META_HARNESS / "engine" / "render-report.py",
    META_HARNESS / "engine" / "invoke_semantic_role.py",
]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def run_command(name: str, command: list[str], timeout: int = 120) -> CheckResult:
    result = run_raw(command, timeout=timeout)
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        return CheckResult(name, True, first_line(output) or "exit 0")
    return CheckResult(
        name,
        False,
        f"exit {result.returncode}: {first_line(output) or '<no output>'}",
    )


def run_raw(command: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def check_current_gate_parity(
    name: str,
    python_command: list[str],
    powershell_command: list[str],
    expected_tokens: list[str],
    timeout: int = 180,
) -> CheckResult:
    py_result = run_raw(python_command, timeout=timeout)
    ps_result = run_raw(powershell_command, timeout=timeout)
    py_output = py_result.stdout + py_result.stderr
    ps_output = ps_result.stdout + ps_result.stderr

    if py_result.returncode != ps_result.returncode:
        return CheckResult(
            name,
            False,
            f"exit mismatch: python={py_result.returncode} powershell={ps_result.returncode}",
        )

    missing_py = [token for token in expected_tokens if token not in py_output]
    missing_ps = [token for token in expected_tokens if token not in ps_output]
    if missing_py or missing_ps:
        return CheckResult(
            name,
            False,
            f"token mismatch: missing_python={missing_py} missing_powershell={missing_ps}",
        )

    py_first = first_line(py_output)
    ps_first = first_line(ps_output)
    if py_result.returncode == 0:
        return CheckResult(name, True, f"both exit 0: {py_first or ps_first}")
    return CheckResult(
        name,
        True,
        f"both exit {py_result.returncode} with matching gate markers: {py_first or ps_first}",
    )


def first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def check_files_exist(paths: list[Path], label: str) -> CheckResult:
    missing = [rel(path) for path in paths if not path.exists()]
    if missing:
        return CheckResult(label, False, "missing: " + ", ".join(missing))
    return CheckResult(label, True, f"{len(paths)} file(s) present")


def check_compile(paths: list[Path], label: str) -> CheckResult:
    try:
        for path in paths:
            py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        return CheckResult(label, False, str(exc))
    return CheckResult(label, True, f"{len(paths)} file(s) compile")


def check_help(script: Path, expected_tokens: list[str], label: str) -> CheckResult:
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        return CheckResult(label, False, f"help exit {result.returncode}: {first_line(output)}")
    missing = [token for token in expected_tokens if token not in output]
    if missing:
        return CheckResult(label, False, "missing help token(s): " + ", ".join(missing))
    return CheckResult(label, True, "help surface accepted")


def check_no_active_ps1(active_roots: list[Path], archive_roots: list[Path]) -> CheckResult:
    archive_resolved = [root.resolve() for root in archive_roots if root.exists()]
    active_ps1 = []
    for root in active_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.ps1"):
            resolved = path.resolve()
            if any(resolved.is_relative_to(archive) for archive in archive_resolved):
                continue
            active_ps1.append(rel(path))

    if active_ps1:
        return CheckResult("active PowerShell archive check", False, "active ps1: " + ", ".join(active_ps1))
    return CheckResult("active PowerShell archive check", True, "no active .ps1 outside archive tmp")


def check_harness_json_accepts_utf8_bom() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS))
    from harness_shared import read_json

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "bom-config.json"
        path.write_text('{"ok": true}\n', encoding="utf-8-sig")
        try:
            data = read_json(path)
        except Exception as exc:
            return CheckResult("harness JSON UTF-8 BOM compatibility", False, repr(exc))

    if data != {"ok": True}:
        return CheckResult("harness JSON UTF-8 BOM compatibility", False, f"unexpected data: {data!r}")
    return CheckResult("harness JSON UTF-8 BOM compatibility", True, "BOM-prefixed JSON accepted")


def check_epic_alignment_gate_accepts_bom_contract() -> CheckResult:
    task_text = """# Test Task

## Task Status

Task Status: UNCLAIMED

## Epic Alignment

- Epic ID: epic-test
- Acceptance Item: A1 - Test acceptance item.
- Design Section: Design Rule - test
- Goal Reference: Test goal reference with spaces.
"""
    contract = {
        "epic_id": "epic-test",
        "goal": "Test goal reference with spaces.",
        "acceptance_items": [{"id": "A1", "description": "Test acceptance item."}],
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        task_path = temp / "001-test-task.md"
        contract_path = temp / "contract.json"
        task_path.write_text(task_text, encoding="utf-8")
        contract_path.write_text(json.dumps(contract), encoding="utf-8-sig")
        result = run_raw(
            [
                sys.executable,
                str(DEV_HARNESS / "checks" / "epic_alignment_gate.py"),
                "--TaskBrief",
                str(task_path),
                "--EpicContract",
                str(contract_path),
            ],
            timeout=30,
        )

    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        return CheckResult(
            "epic alignment BOM contract",
            False,
            f"exit {result.returncode}: {first_line(output)}",
        )
    if "[epic-alignment-gate] PASS" not in output:
        return CheckResult("epic alignment BOM contract", False, "missing PASS marker")
    return CheckResult("epic alignment BOM contract", True, "BOM-prefixed contract accepted")


def check_epic_alignment_gate_accepts_markdown_labels() -> CheckResult:
    task_text = """# Test Task

## Task Status

Task Status: UNCLAIMED

## Epic Alignment

- **Epic ID**: epic-test
- **Acceptance Item**: A1: Test acceptance item.
- **Design Section**: Design Rule - test
- **Goal Reference**: Test goal reference with spaces.
"""
    contract = {
        "epic_id": "epic-test",
        "goal": "Test goal reference with spaces.",
        "acceptance_items": [{"id": "A1", "description": "Test acceptance item."}],
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        task_path = temp / "001-test-task.md"
        contract_path = temp / "contract.json"
        task_path.write_text(task_text, encoding="utf-8")
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        result = run_raw(
            [
                sys.executable,
                str(DEV_HARNESS / "checks" / "epic_alignment_gate.py"),
                "--TaskBrief",
                str(task_path),
                "--EpicContract",
                str(contract_path),
            ],
            timeout=30,
        )

    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        return CheckResult(
            "epic alignment markdown labels",
            False,
            f"exit {result.returncode}: {first_line(output)}",
        )
    if "[epic-alignment-gate] PASS" not in output:
        return CheckResult("epic alignment markdown labels", False, "missing PASS marker")
    return CheckResult("epic alignment markdown labels", True, "markdown labels accepted")


def check_epic_alignment_allows_unreadable_goal_when_item_matches() -> CheckResult:
    task_text = """# Test Task

## Task Status

Task Status: UNCLAIMED

## Epic Alignment

- Epic ID: epic-test
- Acceptance Item: A1
- Design Section: Authentication Design
- Goal Reference: User can log in and receive a JWT token.
"""
    contract = {
        "epic_id": "epic-test",
        "north_star": "瀹炵幇韬唤+鍗曠郴缁熸煡璇㈤棴鐜",
        "acceptance_items": [{"id": "A1", "description": "鐢ㄦ埛鑳界敤璐﹀彿瀵嗙爜鐧诲綍"}],
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        task_path = temp / "001-test-task.md"
        contract_path = temp / "contract.json"
        task_path.write_text(task_text, encoding="utf-8")
        contract_path.write_text(json.dumps(contract), encoding="utf-8-sig")
        result = run_raw(
            [
                sys.executable,
                str(DEV_HARNESS / "checks" / "epic_alignment_gate.py"),
                "--TaskBrief",
                str(task_path),
                "--EpicContract",
                str(contract_path),
            ],
            timeout=30,
        )

    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        return CheckResult(
            "epic alignment unreadable goal fallback",
            False,
            f"exit {result.returncode}: {first_line(output)}",
        )
    return CheckResult("epic alignment unreadable goal fallback", True, "matching item accepted")


def check_agent_command_resolution() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    resolved = auto_harness_loop.resolve_process_command("claude")
    if not resolved:
        return CheckResult("agent command resolution", False, "claude did not resolve")
    if Path(resolved).name.lower() not in {"claude", "claude.cmd", "claude.exe"}:
        return CheckResult("agent command resolution", False, f"unexpected path: {resolved}")
    return CheckResult("agent command resolution", True, resolved)


def check_agent_config_uses_python_gates() -> CheckResult:
    import json

    config_path = DEV_HARNESS / "automation" / "agent-config.example.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    defaults = config.get("defaults", {})
    gate_commands = {
        "light_gate_command": defaults.get("light_gate_command", ""),
        "full_gate_command": defaults.get("full_gate_command", ""),
    }
    stale = [name for name, command in gate_commands.items() if "dev-gate.ps1" in command]
    missing = [name for name, command in gate_commands.items() if "dev_gate.py" not in command]
    if stale or missing:
        return CheckResult(
            "agent config Python gate commands",
            False,
            f"stale_ps1={stale} missing_dev_gate_py={missing}",
        )
    skip_acceptance = [name for name, command in gate_commands.items() if "--SkipAcceptance" in command]
    if skip_acceptance:
        return CheckResult(
            "agent config Python gate commands",
            False,
            f"risk-aware gates must not skip acceptance: {skip_acceptance}",
        )
    return CheckResult("agent config Python gate commands", True, "example config uses dev_gate.py")


def check_preflight_blocked_precheck_parser() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    success_output = (
        "Goal: do not output BLOCKED_PRECHECK unless unsafe.\n"
        "[RESULT]\n"
        "Light gate passed. Gate result: PASS.\n"
        "[__AUTO_HARNESS_EXIT_CODE:0]"
    )
    if auto_harness_loop.preflight_output_reports_blocked_precheck(success_output):
        return CheckResult(
            "preflight BLOCKED_PRECHECK parser",
            False,
            "prompt echo caused false BLOCKED_PRECHECK",
        )
    blocked_output = "[RESULT]\nBLOCKED_PRECHECK\n[__AUTO_HARNESS_EXIT_CODE:0]"
    if not auto_harness_loop.preflight_output_reports_blocked_precheck(blocked_output):
        return CheckResult(
            "preflight BLOCKED_PRECHECK parser",
            False,
            "explicit result marker was not detected",
        )
    return CheckResult("preflight BLOCKED_PRECHECK parser", True, "only final/result markers block")


def check_preflight_auto_commit_respects_dry_run() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    old_repo_root = auto_harness_loop.RepoRoot
    old_dry_run = auto_harness_loop.DryRun
    old_write_runlog = auto_harness_loop.write_runlog
    old_subprocess_run = auto_harness_loop.subprocess.run
    calls = []
    logs = []

    class Result:
        def __init__(self, returncode=0, stdout=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["git", "status", "--porcelain"]:
            return Result(stdout=" M harness-engine/.dev-harness/scripts/auto_harness_loop.py\n M harness-engine/meta-harness/reports/meta-review-latest.md\n")
        return Result()

    try:
        auto_harness_loop.RepoRoot = str(REPO_ROOT)
        auto_harness_loop.DryRun = True
        auto_harness_loop.write_runlog = lambda level, message: logs.append((level, message))
        auto_harness_loop.subprocess.run = fake_run

        committed = auto_harness_loop.preflight_auto_commit_safe_changes()

        if committed:
            return CheckResult("preflight auto-commit dry-run", False, "dry run reported a commit")
        if any(cmd[:2] == ["git", "add"] or cmd[:2] == ["git", "commit"] for cmd in calls):
            return CheckResult("preflight auto-commit dry-run", False, f"dry run invoked git mutation: {calls}")
        if not any("skip preflight auto-commit" in message for _, message in logs):
            return CheckResult("preflight auto-commit dry-run", False, "dry run skip was not logged")
        return CheckResult("preflight auto-commit dry-run", True, "dry run avoids git add/commit")
    finally:
        auto_harness_loop.RepoRoot = old_repo_root
        auto_harness_loop.DryRun = old_dry_run
        auto_harness_loop.write_runlog = old_write_runlog
        auto_harness_loop.subprocess.run = old_subprocess_run


def check_completed_epic_guard_runs_before_preflight() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    if not hasattr(auto_harness_loop, "guard_completed_epic_before_preflight"):
        return CheckResult(
            "completed epic preflight guard",
            False,
            "missing guard_completed_epic_before_preflight",
        )

    old_repo_root = auto_harness_loop.RepoRoot
    auto_harness_loop.RepoRoot = str(REPO_ROOT)
    state = auto_harness_loop.new_auto_state(5, "codex/test", False, 5)
    epic = {
        "enabled": True,
        "complete": True,
        "id": "epic-done",
        "contract": {"epic_id": "epic-done", "acceptance_items": []},
    }
    logs = []
    old_write_runlog = auto_harness_loop.write_runlog
    old_write_json_file = auto_harness_loop.write_json_file
    old_write_run_summary = auto_harness_loop.write_run_summary
    old_resolve_next = auto_harness_loop.resolve_next_epic_context
    try:
        auto_harness_loop.write_runlog = lambda level, message: logs.append((level, message))
        auto_harness_loop.write_json_file = lambda path, data: None
        auto_harness_loop.write_run_summary = lambda current_state, status: logs.append(("SUMMARY", status))
        auto_harness_loop.resolve_next_epic_context = lambda current_epic: None

        result = auto_harness_loop.guard_completed_epic_before_preflight(epic, state, None)

        if not result.get("handled"):
            return CheckResult("completed epic preflight guard", False, "completed epic was not handled")
        if result.get("epic") is not epic:
            return CheckResult("completed epic preflight guard", False, "completed epic without next_epic should not advance")
        if state.get("status") != "EPIC_COMPLETE_NEEDS_NEXT_RESEARCH_EPIC":
            return CheckResult("completed epic preflight guard", False, f"unexpected state: {state}")
        if not any("stopping before preflight" in message for _, message in logs):
            return CheckResult("completed epic preflight guard", False, "guard did not log preflight early stop")
        return CheckResult("completed epic preflight guard", True, "completed epic stops before preflight")
    finally:
        auto_harness_loop.RepoRoot = old_repo_root
        auto_harness_loop.write_runlog = old_write_runlog
        auto_harness_loop.write_json_file = old_write_json_file
        auto_harness_loop.write_run_summary = old_write_run_summary
        auto_harness_loop.resolve_next_epic_context = old_resolve_next


def check_auto_harness_console_colors() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    old_emit = auto_harness_loop.AgentDisplayEmitHost
    old_buffer = auto_harness_loop.AgentDisplayBuffer
    old_force_color = os.environ.get("FORCE_COLOR")
    old_no_color = os.environ.get("NO_COLOR")
    try:
        os.environ["FORCE_COLOR"] = "1"
        os.environ.pop("NO_COLOR", None)
        auto_harness_loop.AgentDisplayEmitHost = True
        auto_harness_loop.AgentDisplayBuffer = []

        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            auto_harness_loop.write_agent_console_event(
                "task_writer",
                "stdout",
                json.dumps({"type": "system", "subtype": "init", "model": "gpt-5.5"}),
            )
            auto_harness_loop.write_agent_console_event(
                "task_writer",
                "stdout",
                json.dumps({"type": "result", "subtype": "success", "result": "ok"}),
            )

        output = stream.getvalue()
        buffer_text = "\n".join(auto_harness_loop.AgentDisplayBuffer)
        if "\x1b[" not in output:
            return CheckResult("auto harness console colors", False, "forced color did not emit ANSI escapes")
        if "[START]" not in output or "[DONE]" not in output:
            return CheckResult("auto harness console colors", False, "missing colored lifecycle markers")
        if "\x1b[" in buffer_text:
            return CheckResult("auto harness console colors", False, "display log buffer contains ANSI escapes")
        return CheckResult("auto harness console colors", True, "host output colored and log buffer plain")
    finally:
        auto_harness_loop.AgentDisplayEmitHost = old_emit
        auto_harness_loop.AgentDisplayBuffer = old_buffer
        if old_force_color is None:
            os.environ.pop("FORCE_COLOR", None)
        else:
            os.environ["FORCE_COLOR"] = old_force_color
        if old_no_color is None:
            os.environ.pop("NO_COLOR", None)
        else:
            os.environ["NO_COLOR"] = old_no_color


def check_claude_command_uses_configured_model_for_openai_provider() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    config = {
        "providers": {
            "gpt5_planner_reviewer": {
                "model": "gpt-5.5",
                "env": {
                    "OPENAI_BASE_URL": "https://example.invalid/v1",
                    "OPENAI_API_KEY": "replace-me",
                },
            },
        },
        "roles": {
            "task_writer": {
                "provider": "gpt5_planner_reviewer",
                "command": "claude",
                "args": ["--print"],
            },
        },
    }
    role = config["roles"]["task_writer"]
    args = auto_harness_loop.resolve_role_cli_args(config, role)
    if args[:2] != ["--model", "gpt-5.5"]:
        return CheckResult(
            "Claude command configured model",
            False,
            f"missing leading configured model args: {args}",
        )
    return CheckResult("Claude command configured model", True, "OpenAI-provider Claude role gets --model")


def check_task_writer_failure_stops_loop() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    writer = {"ok": False, "role": "task_writer", "exit_code": 1}
    if not auto_harness_loop.should_stop_after_writer_failure(writer, resolved_task_brief_path=""):
        return CheckResult("task writer failure stop policy", False, "failed task_writer would continue rounds")
    explicit = {"ok": True, "role": "explicit_task", "exit_code": 0}
    if auto_harness_loop.should_stop_after_writer_failure(explicit, resolved_task_brief_path="task.md"):
        return CheckResult("task writer failure stop policy", False, "explicit task path would stop incorrectly")
    return CheckResult("task writer failure stop policy", True, "failed task_writer stops automatic loop")


def check_epic_repair_task_not_external_workspace() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    with tempfile.TemporaryDirectory() as temp_dir:
        task_path = Path(temp_dir) / "002-2026-05-25-repair-001-complete-auth-skeleton.md"
        task_path.write_text(
            """# Repair task-001: complete AuthController

## Intent

Repair task 001 by implementing AuthController, middleware, routes, seeds, and specs.

## Task Status

Task Status: UNCLAIMED

## Run Type

repair

## Goal

Complete the cockpit-api Rails API-only skeleton.

## Scope Contract

Allowed files or paths:

- cockpit-api/

Forbidden files or paths:

- openclacky/
- harness-engine/
""",
            encoding="utf-8",
        )
        if auto_harness_loop.test_external_workspace_repair_task(str(task_path)):
            return CheckResult(
                "epic repair task guard",
                False,
                "ordinary epic repair task was classified as external-workspace repair",
            )

        external_path = Path(temp_dir) / "003-claude-worktree-cleanup.md"
        external_path.write_text(
            """# Repair .claude worktree blocker

## Intent

Clean up .claude/worktrees/agent-* and settings.local.json scope blocker.
""",
            encoding="utf-8",
        )
        if not auto_harness_loop.test_external_workspace_repair_task(str(external_path)):
            return CheckResult(
                "epic repair task guard",
                False,
                "external workspace repair was not classified",
            )

    return CheckResult("epic repair task guard", True, "ordinary epic repairs are allowed")


def check_epic_alignment_command_uses_python() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    command = auto_harness_loop.build_epic_alignment_gate_command("task.md", "contract.json")
    normalized_command = command.replace("\\", "/")
    expected_gate = "harness-engine/.dev-harness/checks/epic_alignment_gate.py"
    if expected_gate not in normalized_command:
        return CheckResult("epic alignment command Python launch", False, f"missing gate path: {command}")
    if normalized_command.startswith("harness-engine/.dev-harness/checks/epic_alignment_gate.py"):
        return CheckResult("epic alignment command Python launch", False, "gate command runs .py directly")
    if Path(sys.executable).name not in command:
        return CheckResult("epic alignment command Python launch", False, f"missing Python executable: {command}")
    return CheckResult("epic alignment command Python launch", True, "gate command launches through Python")


def check_auto_harness_loop_reads_markdown_epic_id() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    with tempfile.TemporaryDirectory() as temp_dir:
        task_path = Path(temp_dir) / "015-test-task.md"
        task_path.write_text(
            """# Test Task

## Epic Alignment

- **Epic ID**: epic-test
- **Acceptance Item**: A1
""",
            encoding="utf-8",
        )
        epic_id = auto_harness_loop.get_task_epic_id(str(task_path))

    if epic_id != "epic-test":
        return CheckResult(
            "auto harness markdown Epic ID",
            False,
            f"expected epic-test, got {epic_id!r}",
        )
    return CheckResult("auto harness markdown Epic ID", True, "markdown Epic ID accepted")


def check_auto_harness_writer_prompt_uses_rolling_planner() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    prompt = auto_harness_loop.build_writer_prompt(
        {"max_iterations": 1},
        1,
        "none",
        {
            "enabled": True,
            "complete": False,
            "id": "epic-roll",
            "contract_path": "contract.json",
            "goal_path": "goal.md",
            "design_path": "design.md",
            "backlog_path": "backlog.md",
            "planner_spec_path": "tmp/rolling-next-task.json",
            "contract": {"acceptance_items": [{"id": "A1", "description": "Do it", "status": "pending"}]},
            "goal_text": "Goal",
            "design_text": "Design",
            "backlog_text": "Backlog",
            "design_doc_files": [],
        },
    )
    if "rolling_task_planner.py" not in prompt:
        return CheckResult("auto harness rolling planner prompt", False, "missing rolling_task_planner.py")
    if "--SpecFile tmp/rolling-next-task.json" not in prompt:
        return CheckResult("auto harness rolling planner prompt", False, "missing planner spec command")
    return CheckResult("auto harness rolling planner prompt", True, "task writer is steered to planner spec")


def check_auto_harness_direct_writer_can_generate_from_planner_spec() -> CheckResult:
    sys.path.insert(0, str(DEV_HARNESS / "scripts"))
    import auto_harness_loop

    old_repo_root = auto_harness_loop.RepoRoot
    old_run_console_log = auto_harness_loop.RunConsoleLog
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        spec_path = temp / "next-task.json"
        task_path = temp / "001-rolling-direct.md"
        auto_harness_loop.RepoRoot = str(REPO_ROOT)
        auto_harness_loop.RunConsoleLog = str(temp / "console.log")
        spec_path.write_text(json.dumps({
            "Title": "Rolling Direct Task",
            "TaskStream": "harness",
            "RunType": "HARNESS_RUNTIME",
            "Layer": "harness-engine/.dev-harness",
            "RiskClass": "LOW",
            "Intent": "Verify direct planner spec task generation.",
            "Goal": "Generate a task brief directly from planner spec.",
            "AllowedPaths": ["harness-engine/.dev-harness/scripts/rolling_task_planner.py"],
            "AcceptanceCriteria": ["Generated task includes epic alignment."],
            "VerificationCommands": ["python harness-engine/.dev-harness/tests/accept_harness_python.py --skip-full-dev-gate --skip-meta-pipeline"],
            "EpicId": "epic-roll",
            "AcceptanceItem": "A1",
            "DesignSection": "Backlog B1",
            "GoalReference": "north_star",
            "OutputPath": str(task_path),
        }), encoding="utf-8")

        try:
            writer = auto_harness_loop.invoke_programmatic_task_writer(str(spec_path), str(temp))

            if not writer.get("ok"):
                return CheckResult("programmatic task writer", False, str(writer))
            if not task_path.exists():
                return CheckResult("programmatic task writer", False, "task file was not generated")
            content = task_path.read_text(encoding="utf-8")
            if "Epic ID: epic-roll" not in content or "Acceptance Item: A1" not in content:
                return CheckResult("programmatic task writer", False, "generated task lacks epic alignment")
            return CheckResult("programmatic task writer", True, "planner SpecFile generated task directly")
        finally:
            auto_harness_loop.RepoRoot = old_repo_root
            auto_harness_loop.RunConsoleLog = old_run_console_log


def check_register_epic_writes_structured_backlog() -> CheckResult:
    with tempfile.TemporaryDirectory() as temp_dir:
        epic_root = Path(temp_dir) / "epic-structured"
        result = run_raw([
            sys.executable,
            str(DEV_HARNESS / "scripts" / "register_epic.py"),
            "--EpicId",
            "epic-structured",
            "--Title",
            "Structured Epic",
            "--Goal",
            "Build with rolling tasks.",
            "--BacklogItems",
            "A1|auth|Implement auth proxy|cockpit-api/app/controllers/auth_controller.rb|bundle exec rspec spec/requests/auth_spec.rb",
            "--BacklogItems",
            "A2|dashboard|Wire dashboard agent|openclacky/lib/clacky/web/dashboard.js|ruby -c openclacky/lib/clacky/web/dashboard.js",
            "--AcceptanceItems",
            "A1|User can authenticate.",
            "--AcceptanceItems",
            "A2|Dashboard can ask the agent.",
            "--OutputRoot",
            str(epic_root),
            "--Force",
        ])
        output = result.stdout + result.stderr
        if result.returncode != 0:
            return CheckResult("structured backlog registration", False, f"exit {result.returncode}: {first_line(output)}")
        backlog_path = epic_root / "backlog.json"
        if not backlog_path.exists():
            return CheckResult("structured backlog registration", False, "missing backlog.json")
        backlog = json.loads(backlog_path.read_text(encoding="utf-8"))

    if len(backlog.get("items", [])) != 2:
        return CheckResult("structured backlog registration", False, f"unexpected backlog: {backlog}")
    first = backlog["items"][0]
    if first.get("acceptance_item") != "A1" or first.get("task_stream") != "auth":
        return CheckResult("structured backlog registration", False, f"wrong first item: {first}")
    if "cockpit-api/app/controllers/auth_controller.rb" not in first.get("allowed_paths", []):
        return CheckResult("structured backlog registration", False, f"missing allowed path: {first}")
    return CheckResult("structured backlog registration", True, "backlog.json written")


def check_rolling_task_planner_selects_first_unblocked_item() -> CheckResult:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        contract_path = temp / "contract.json"
        backlog_path = temp / "backlog.json"
        output_path = temp / "next-task.json"
        contract_path.write_text(json.dumps({
            "epic_id": "epic-roll",
            "north_star": "Deliver rolling task planning.",
            "acceptance_items": [
                {"id": "A1", "description": "First item.", "status": "done"},
                {"id": "A2", "description": "Second item.", "status": "pending"},
            ],
            "forbidden_changes": ["Do not touch secrets."],
        }), encoding="utf-8")
        backlog_path.write_text(json.dumps({
            "items": [
                {
                    "id": "B1",
                    "title": "First done",
                    "acceptance_item": "A1",
                    "task_stream": "auth",
                    "status": "done",
                    "allowed_paths": ["cockpit-api/app/controllers/auth_controller.rb"],
                    "verification_commands": ["bundle exec rspec spec/requests/auth_spec.rb"],
                },
                {
                    "id": "B2",
                    "title": "Second pending",
                    "acceptance_item": "A2",
                    "task_stream": "dashboard",
                    "status": "pending",
                    "depends_on": ["B1"],
                    "allowed_paths": ["openclacky/lib/clacky/web/dashboard.js"],
                    "verification_commands": ["ruby -c openclacky/lib/clacky/web/dashboard.js"],
                },
            ]
        }), encoding="utf-8")
        result = run_raw([
            sys.executable,
            str(DEV_HARNESS / "scripts" / "rolling_task_planner.py"),
            "--EpicContract",
            str(contract_path),
            "--Backlog",
            str(backlog_path),
            "--OutputSpec",
            str(output_path),
        ])
        output = result.stdout + result.stderr
        if result.returncode != 0:
            return CheckResult("rolling task planner selection", False, f"exit {result.returncode}: {first_line(output)}")
        spec = json.loads(output_path.read_text(encoding="utf-8"))

    if spec.get("Title") != "Second pending":
        return CheckResult("rolling task planner selection", False, f"wrong title: {spec}")
    if spec.get("AcceptanceItem") != "A2":
        return CheckResult("rolling task planner selection", False, f"wrong acceptance item: {spec}")
    if spec.get("AllowedPaths") != ["openclacky/lib/clacky/web/dashboard.js"]:
        return CheckResult("rolling task planner selection", False, f"wrong allowed paths: {spec}")
    return CheckResult("rolling task planner selection", True, "first unblocked pending item selected")


def check_rolling_task_planner_blocks_unmet_dependencies() -> CheckResult:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        contract_path = temp / "contract.json"
        backlog_path = temp / "backlog.json"
        contract_path.write_text(json.dumps({
            "epic_id": "epic-roll",
            "north_star": "Deliver rolling task planning.",
            "acceptance_items": [{"id": "A2", "description": "Second item.", "status": "pending"}],
        }), encoding="utf-8")
        backlog_path.write_text(json.dumps({
            "items": [
                {
                    "id": "B2",
                    "title": "Blocked pending",
                    "acceptance_item": "A2",
                    "task_stream": "dashboard",
                    "status": "pending",
                    "depends_on": ["B1"],
                    "allowed_paths": ["openclacky/lib/clacky/web/dashboard.js"],
                }
            ]
        }), encoding="utf-8")
        result = run_raw([
            sys.executable,
            str(DEV_HARNESS / "scripts" / "rolling_task_planner.py"),
            "--EpicContract",
            str(contract_path),
            "--Backlog",
            str(backlog_path),
        ])
        output = result.stdout + result.stderr

    if result.returncode == 0:
        return CheckResult("rolling task planner dependency block", False, "planner passed with unmet dependency")
    if "no unblocked pending backlog item" not in output:
        return CheckResult("rolling task planner dependency block", False, f"unexpected output: {first_line(output)}")
    return CheckResult("rolling task planner dependency block", True, "unmet dependency blocks item")


def run_dev_harness_checks(include_full_gate: bool) -> list[CheckResult]:
    checks = [
        check_no_active_ps1(
            [DEV_HARNESS, META_HARNESS],
            [
                DEV_HARNESS / "engine" / "tmp" / "powershell-archive",
                META_HARNESS / "engine" / "tmp" / "powershell-archive",
            ],
        ),
        check_files_exist(DEV_HARNESS_ENTRYPOINTS, ".dev-harness python files"),
        check_compile(DEV_HARNESS_ENTRYPOINTS, ".dev-harness python compile"),
        check_harness_json_accepts_utf8_bom(),
        check_epic_alignment_gate_accepts_bom_contract(),
        check_epic_alignment_gate_accepts_markdown_labels(),
        check_epic_alignment_allows_unreadable_goal_when_item_matches(),
        check_agent_command_resolution(),
        check_agent_config_uses_python_gates(),
        check_preflight_blocked_precheck_parser(),
        check_preflight_auto_commit_respects_dry_run(),
        check_completed_epic_guard_runs_before_preflight(),
        check_auto_harness_console_colors(),
        check_claude_command_uses_configured_model_for_openai_provider(),
        check_task_writer_failure_stops_loop(),
        check_epic_repair_task_not_external_workspace(),
        check_epic_alignment_command_uses_python(),
        check_auto_harness_loop_reads_markdown_epic_id(),
        check_auto_harness_writer_prompt_uses_rolling_planner(),
        check_auto_harness_direct_writer_can_generate_from_planner_spec(),
        check_register_epic_writes_structured_backlog(),
        check_rolling_task_planner_selects_first_unblocked_item(),
        check_rolling_task_planner_blocks_unmet_dependencies(),
        check_help(
            DEV_HARNESS / "checks" / "dev_gate.py",
            ["--SkipRust", "--SkipEngine", "--Fast"],
            ".dev-harness dev_gate help",
        ),
        check_help(
            DEV_HARNESS / "scripts" / "auto_harness_loop.py",
            ["--MaxIterations", "--PreflightOnly", "--DryRun"],
            ".dev-harness auto_harness_loop help",
        ),
        check_help(
            DEV_HARNESS / "scripts" / "new_task_brief.py",
            ["--SpecFile", "--Title", "--TaskStream", "--RiskClass"],
            ".dev-harness new_task_brief help",
        ),
        check_help(
            DEV_HARNESS / "scripts" / "rolling_task_planner.py",
            ["--EpicContract", "--Backlog", "--OutputSpec"],
            ".dev-harness rolling_task_planner help",
        ),
        check_help(
            DEV_HARNESS / "scripts" / "new_review_draft.py",
            ["--Task", "--TaskBrief", "--ChangedFiles"],
            ".dev-harness new_review_draft help",
        ),
        run_command(
            ".dev-harness programmatic selftest",
            [sys.executable, str(DEV_HARNESS / "checks" / "programmatic_harness_selftest.py")],
            timeout=180,
        ),
    ]

    if include_full_gate:
        checks.append(
            run_command(
                ".dev-harness fast dev gate",
                [sys.executable, str(DEV_HARNESS / "checks" / "dev_gate.py"), "--SkipRust", "--Fast"],
                timeout=180,
            )
        )

    return checks


def run_meta_harness_checks(run_pipeline: bool) -> list[CheckResult]:
    checks = [
        check_files_exist(META_HARNESS_ENTRYPOINTS, "meta-harness python files"),
        check_compile(META_HARNESS_ENTRYPOINTS, "meta-harness python compile"),
        check_help(
            META_HARNESS / "engine" / "run_meta_review.py",
            ["--MetaRoot", "--Limit", "--Offline", "--SkipReplay"],
            "meta-harness run_meta_review help",
        ),
    ]

    if run_pipeline:
        checks.append(
            run_command(
                "meta-harness offline pipeline",
                [
                    sys.executable,
                    str(META_HARNESS / "engine" / "run_meta_review.py"),
                    "--Limit",
                    "1",
                    "--Offline",
                    "--SkipReplay",
                ],
                timeout=180,
            )
        )

    return checks


def print_results(results: list[CheckResult]) -> None:
    print("[accept-harness-python] results")
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {result.name}: {result.detail}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-full-dev-gate",
        action="store_true",
        help="Skip dev_gate.py --SkipRust --Fast when only smoke acceptance is needed.",
    )
    parser.add_argument(
        "--skip-meta-pipeline",
        action="store_true",
        help="Skip the offline meta-harness pipeline and only check its Python surfaces.",
    )
    args = parser.parse_args()

    results = []
    results.extend(run_dev_harness_checks(include_full_gate=not args.skip_full_dev_gate))
    results.extend(run_meta_harness_checks(run_pipeline=not args.skip_meta_pipeline))
    print_results(results)

    failures = [result for result in results if not result.ok]
    if failures:
        print(f"[accept-harness-python] FAIL: {len(failures)} failing check(s)")
        return 1

    print("[accept-harness-python] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
