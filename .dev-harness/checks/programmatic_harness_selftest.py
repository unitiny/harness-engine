#!/usr/bin/env python3
"""programmatic_harness_selftest.py — Behavioral parity with programmatic_harness_selftest.py"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import find_repo_root, read_text, write_json, ensure_dir


def assert_true(condition, message):
    if not condition:
        raise AssertionError(f"[programmatic-selftest] assertion failed: {message}")


def run_script(script_path, args=None):
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Script failed with exit code {result.returncode}: {script_path}")
    return result.stdout


def run_script_expect_failure(script_path, args=None):
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode != 0


def run_script_failure_output(script_path, args=None):
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        raise AssertionError(f"Script unexpectedly passed: {script_path}")
    return (result.stdout or "") + (result.stderr or "")


def remove_if_present(path):
    try:
        path.unlink()
    except (FileNotFoundError, PermissionError):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--KeepTemp", action="store_true")
    args = parser.parse_args()

    root = find_repo_root()
    harness_root = root / "harness-engine" / ".dev-harness"
    temp_parent = harness_root / "tmp" / "programmatic-harness-selftest"
    temp_root = temp_parent / f"run-{os.getpid()}"

    if temp_root.exists():
        shutil.rmtree(str(temp_root))
    ensure_dir(temp_root)

    try:
        # --- Context Summary ---
        summary_script = harness_root / "scripts" / "harness_context_summary.py"
        summary_output = run_script(summary_script, [
            "--RecentTasks", "2",
            "--RecentReviews", "2",
            "--RecentReceipts", "2",
        ])
        assert_true("HARNESS_CONTEXT_SUMMARY" in summary_output,
                     "context summary should print stable marker")
        assert_true("Token rules" in summary_output,
                     "context summary should print token rules")
        assert_true("new_task_brief.py" in summary_output,
                     "context summary should advertise task generator")
        assert_true("--SpecFile" in summary_output,
                     "context summary should advertise spec-file task generation for long inputs")
        assert_true("SpecFile must contain Title" in summary_output,
                     "context summary should list required spec-file fields")
        assert_true("BLOCKED receipts must include an evaluator/checker repair proposal" in summary_output,
                     "context summary should require evaluator repair for blocked receipts")
        assert_true("new_review_draft.py" in summary_output,
                     "context summary should advertise review generator")
        assert_true("Repo-root command rules" in summary_output,
                     "context summary should print repo-root command rules")
        assert_true("verify file exists before Read" in summary_output,
                     "context summary should require existence checks before guessed reads")
        assert_true("never run harness generators from inside cockpit-api" in summary_output,
                     "context summary should prevent wrong-cwd harness generator calls")
        assert_true("task queue dirs:" in summary_output,
                     "context summary should print canonical task queue directories")
        assert_true("harness-engine/.dev-harness/task-briefs/" in summary_output,
                     "context summary should name canonical task brief directory")
        assert_true("harness-engine/.dev-harness/execution-receipts/" in summary_output,
                     "context summary should name canonical execution receipt directory")
        assert_true("do not use harness-engine/.dev-harness/automation/task-briefs/" in summary_output,
                     "context summary should reject guessed automation task brief directory")
        assert_true("do not use harness-engine/.dev-harness/automation/execution-receipts/" in summary_output,
                     "context summary should reject guessed automation execution receipt directory")

        # --- Task Brief ---
        brief_path = temp_root / "057-2026-05-20-programmatic-harness-smoke.md"
        run_script(harness_root / "scripts" / "new_task_brief.py", [
            "--Title", "Programmatic Harness Smoke",
            "--Slug", "programmatic-harness-smoke",
            "--TaskStream", "harness-token-economy",
            "--RunType", "HARNESS_RUNTIME",
            "--Layer", "harness-engine/.dev-harness",
            "--RiskClass", "LOW",
            "--Intent", "Verify programmatic harness file generation.",
            "--Goal", "Generate a bounded smoke task brief.",
            "--NonGoals", "Do not touch product code.",
            "--AllowedPaths", "harness-engine/.dev-harness/scripts/new_task_brief.py",
            "--ForbiddenPaths", "crates/",
            "--AcceptanceCriteria", "Generated task brief includes scope contract.",
            "--VerificationCommands", "harness-engine/.dev-harness/checks/dev_gate.py -SkipRust -Fast",
            "--StopConditions", "Stop if product code changes are required.",
            "--OutputPath", str(brief_path),
        ])

        brief = read_text(brief_path)
        assert_true("Task Status: UNCLAIMED" in brief,
                     "task brief should be unclaimed")
        assert_true("- Task Stream: harness-token-economy" in brief,
                     "task stream should be recorded")
        assert_true("Allowed files or paths:" in brief,
                     "allowed scope section should exist")
        assert_true("Generated by: scripts/new_task_brief.py" in brief,
                     "generator provenance should be recorded")

        # --- Task Brief from JSON spec file ---
        spec_brief_path = temp_root / "059-2026-05-20-spec-file-smoke.md"
        spec_path = temp_root / "spec-file-smoke.json"
        write_json(spec_path, {
            "Title": "Spec File Smoke",
            "Slug": "spec-file-smoke",
            "TaskStream": "harness-token-economy",
            "RunType": "HARNESS_RUNTIME",
            "Layer": "harness-engine/.dev-harness",
            "RiskClass": "LOW",
            "Intent": "Verify task briefs can be generated from a compact spec file.",
            "Goal": "Generate a task brief without a long shell argument list.",
            "NonGoals": ["Do not touch product code."],
            "AllowedPaths": ["harness-engine/.dev-harness/scripts/new_task_brief.py"],
            "ForbiddenPaths": ["crates/"],
            "AcceptanceCriteria": ["Generated task brief includes spec-file fields."],
            "VerificationCommands": ["python harness-engine/.dev-harness/checks/dev_gate.py --SkipRust --Fast"],
            "StopConditions": ["Stop if spec-file fields cannot be parsed."],
        })
        run_script(harness_root / "scripts" / "new_task_brief.py", [
            "--SpecFile", str(spec_path),
            "--OutputPath", str(spec_brief_path),
        ])

        spec_brief = read_text(spec_brief_path)
        assert_true("# Spec File Smoke" in spec_brief,
                     "spec-file generation should record title")
        assert_true("Generated task brief includes spec-file fields." in spec_brief,
                     "spec-file generation should record acceptance criteria")
        assert_true("harness-engine/.dev-harness/scripts/new_task_brief.py" in spec_brief,
                     "spec-file generation should record allowed paths")
        assert_true("If task status is BLOCKED, the receipt must include an evaluator/checker repair proposal." in spec_brief,
                     "task brief should make blocked evaluator repair mandatory")

        incomplete_spec_path = temp_root / "incomplete-spec-file-smoke.json"
        write_json(incomplete_spec_path, {
            "TaskStream": "harness-token-economy",
            "RunType": "HARNESS_RUNTIME",
            "Layer": "harness-engine/.dev-harness",
            "RiskClass": "LOW",
            "Intent": "Verify actionable generator errors.",
            "Goal": "Fail because Title is absent.",
        })
        spec_error = run_script_failure_output(harness_root / "scripts" / "new_task_brief.py", [
            "--SpecFile", str(incomplete_spec_path),
            "--OutputPath", str(temp_root / "060-2026-05-20-incomplete-spec.md"),
        ])
        assert_true("missing required fields: Title" in spec_error,
                     "missing required spec field should be named")
        assert_true("SpecFile required fields" in spec_error,
                     "missing spec field error should print required fields")
        assert_true("--SpecFile" in spec_error,
                     "missing spec field error should guide spec-file repair")

        # --- Epic contract for alignment test ---
        epic_root = temp_root / "epics" / "epic-program-harness-smoke"
        ensure_dir(epic_root)
        contract_path = epic_root / "contract.json"
        contract = {
            "version": 1,
            "epic_id": "epic-program-harness-smoke",
            "status": "active",
            "north_star": "Verify Program Harness epic alignment.",
            "acceptance_items": [
                {
                    "id": "A1",
                    "description": "Task briefs bind to an epic acceptance item.",
                    "status": "pending",
                }
            ],
            "forbidden_changes": ["Do not touch product code."],
            "completion_rule": {
                "all_acceptance_done": True,
                "final_full_gate_required": True,
                "reviewer_done_required": True,
            },
        }
        write_json(contract_path, contract)

        # --- Epic-aligned task brief ---
        epic_brief_path = temp_root / "058-2026-05-20-epic-alignment-smoke.md"
        run_script(harness_root / "scripts" / "new_task_brief.py", [
            "--Title", "Epic Alignment Smoke",
            "--Slug", "epic-alignment-smoke",
            "--TaskStream", "program-harness",
            "--RunType", "HARNESS_RUNTIME",
            "--Layer", "harness-engine/.dev-harness",
            "--RiskClass", "LOW",
            "--Intent", "Verify generated task briefs can bind to an epic contract.",
            "--Goal", "Generate a bounded epic-aligned smoke task brief.",
            "--NonGoals", "Do not touch product code.",
            "--AllowedPaths", "harness-engine/.dev-harness/scripts/new_task_brief.py",
            "--ForbiddenPaths", "crates/",
            "--AcceptanceCriteria", "Generated task brief includes epic alignment metadata.",
            "--VerificationCommands",
            f"harness-engine/.dev-harness/checks/epic_alignment_gate.py -TaskBrief \"{epic_brief_path}\" -EpicContract \"{contract_path}\"",
            "--StopConditions", "Stop if no matching epic acceptance item exists.",
            "--EpicId", "epic-program-harness-smoke",
            "--AcceptanceItem", "A1",
            "--DesignSection", "Program Harness / Epic Contract",
            "--GoalReference", "north_star",
            "--OutputPath", str(epic_brief_path),
        ])

        epic_brief = read_text(epic_brief_path)
        assert_true("## Epic Alignment" in epic_brief,
                     "task brief should include epic alignment section")
        assert_true("Epic ID: epic-program-harness-smoke" in epic_brief,
                     "task brief should record epic id")
        assert_true("Acceptance Item: A1" in epic_brief,
                     "task brief should record acceptance item id")

        # --- Epic alignment gate (pass) ---
        run_script(harness_root / "checks" / "epic_alignment_gate.py", [
            "--TaskBrief", str(epic_brief_path),
            "--EpicContract", str(contract_path),
        ])

        # --- Register epic ---
        registered_epic_root = temp_root / "registered-epics" / "epic-registered-smoke"
        run_script(harness_root / "scripts" / "register_epic.py", [
            "--EpicId", "epic-registered-smoke",
            "--Title", "Registered Smoke Epic",
            "--Goal", "Verify register-epic creates portable Program Harness files.",
            "--DesignPaths", "docs/event-collection/README.md",
            "--BacklogItems", "Generate files",
            "--BacklogItems", "Run loop",
            "--AcceptanceItems", "A1|Register an epic with goal, design, backlog, and contract.",
            "--AcceptanceItems", "A2|Keep the epic ready for auto-harness-loop.",
            "--ForbiddenChanges", "Do not touch product code.",
            "--OutputRoot", str(registered_epic_root),
            "--Force",
        ])

        assert_true((registered_epic_root / "goal.md").exists(),
                     "registered epic should include goal.md")
        assert_true((registered_epic_root / "design.md").exists(),
                     "registered epic should include design.md")
        assert_true((registered_epic_root / "backlog.md").exists(),
                     "registered epic should include backlog.md")
        assert_true((registered_epic_root / "contract.json").exists(),
                     "registered epic should include contract.json")
        registered_contract = json.loads(read_text(registered_epic_root / "contract.json"))
        assert_true(registered_contract.get("epic_id") == "epic-registered-smoke",
                     "registered contract should record epic id")
        assert_true(len(registered_contract.get("acceptance_items", [])) == 2,
                     "registered contract should include acceptance items")

        # --- Epic alignment gate (should fail) ---
        alignment_failed = run_script_expect_failure(harness_root / "checks" / "epic_alignment_gate.py", [
            "--TaskBrief", str(brief_path),
            "--EpicContract", str(contract_path),
        ])
        assert_true(alignment_failed,
                     "epic-alignment gate should fail when a task lacks epic metadata")

        # --- Review draft ---
        review_path = temp_root / "057-2026-05-20-programmatic-harness-smoke-review.md"
        run_script(harness_root / "scripts" / "new_review_draft.py", [
            "--TaskBrief", str(brief_path),
            "--OutputPath", str(review_path),
            "--ChangedFiles", "harness-engine/.dev-harness/scripts/new_task_brief.py",
            "--GateCommand", "harness-engine/.dev-harness/checks/dev_gate.py -SkipRust -Fast",
            "--GateResult", "not run in selftest",
        ])

        review = read_text(review_path)
        assert_true("## Dual-Model Scope Review" in review,
                     "review draft should include scope review")
        assert_true("Actual changed files" in review,
                     "review draft should list changed files")
        assert_true("Generated by: scripts/new_review_draft.py" in review,
                     "review generator provenance should be recorded")

        # --- Review draft from explicit copied brief path ---
        numbered_brief_path = harness_root / "task-briefs" / "997-2026-05-20-programmatic-harness-smoke-numbered.md"
        remove_if_present(numbered_brief_path)
        shutil.copyfile(str(brief_path), str(numbered_brief_path))
        review_by_number_path = temp_root / "057-2026-05-20-programmatic-harness-smoke-by-number.md"
        run_script(harness_root / "scripts" / "new_review_draft.py", [
            "--TaskBrief", str(numbered_brief_path),
            "--OutputPath", str(review_by_number_path),
            "--ChangedFiles", "harness-engine/.dev-harness/scripts/new_task_brief.py",
        ])
        review_by_number = read_text(review_by_number_path)
        assert_true("Review 997" in review_by_number,
                     "review generator should accept an explicit copied brief path")

        # --- Receipt gate (valid receipt passes) ---
        # Copy brief to real task-briefs so receipt_gate can find it
        real_brief_for_receipt = harness_root / "task-briefs" / "057-2026-05-20-programmatic-harness-smoke.md"
        if not real_brief_for_receipt.exists():
            shutil.copyfile(str(brief_path), str(real_brief_for_receipt))
        receipt_dir = temp_root / "execution-receipts"
        ensure_dir(receipt_dir)
        receipt_path = receipt_dir / "057-2026-05-20-programmatic-harness-smoke-receipt.md"
        receipt_content = """\
# Execution Receipt

## Task
- Task brief: 057-2026-05-20-programmatic-harness-smoke
- Task status before claim: UNCLAIMED
- Task status after completion: DONE
- Implementer: test
- Date: 2026-05-20

## Files Changed
- harness-engine/.dev-harness/scripts/new_task_brief.py

## Summary
- What changed: test change
- Why it matches the brief: test scope

## Acceptance Criteria Status
- [x] Criterion: test passes

## Commands Run
```powershell
echo ok
```
Result:
```text
pass
```

## Scope Check
- Changed only allowed files: yes
- Performed forbidden operations: no
- Dependency or lockfile changes: no
- Generated artifact rewrites: no
- Opportunistic cleanup/refactor: no

## Scope Independent Check
```text
[scope-diff] OK: harness-engine/.dev-harness/scripts/new_task_brief.py
```

## Acceptance Verification
- test passes: command output confirmed

## Deliverable File Existence Check
- `harness-engine/.dev-harness/scripts/new_task_brief.py`: exists (test mock), non-empty

## API Permission Check
N/A: no API changes in this task.

## Security Check
- Secrets added or exposed: no
- Raw model output persisted: no
- Production data or credentials used in prompts: no
- Trust boundary violations: no
- Unauthorized tenant access: no
- AI permission gateway bypass: no

## Gate Evidence
```text
dev_gate.py --Fast exit 0
```

## Verification Self-Assessment
- Diff inspected: yes
- Scope checked programmatically (scope_diff_gate.py): yes
- Receipt claims contradicted by diff: no

## Memory Promotion Decisions
- project-memory.md: no promotion needed: test task
- decision-log.md: no promotion needed: test task
- risk-register.md: no promotion needed: test task
- skill-candidates.md: no promotion needed: test task

## Deviations From Brief
- None

## Assumptions
- None

## Blockers
- None

## Next-Task Prediction
- Next task should observe that the test changes compile and pass
"""
        receipt_path.write_text(receipt_content, encoding="utf-8")

        run_script(harness_root / "checks" / "receipt_gate.py", [
            "--Receipt", str(receipt_path),
        ])

        # --- Receipt gate (incomplete receipt fails) ---
        bad_receipt_path = receipt_dir / "058-2026-05-20-bad-receipt.md"
        bad_receipt_path.write_text("# Bad Receipt\n\n## Task\n- Task status after completion: DONE\n", encoding="utf-8")
        failed = run_script_expect_failure(harness_root / "checks" / "receipt_gate.py", [
            "--Receipt", str(bad_receipt_path),
        ])
        assert_true(failed, "receipt gate should fail for incomplete receipt")

        blocked_receipt_path = receipt_dir / "057-2026-05-20-blocked-no-eval-repair.md"
        blocked_receipt_path.write_text(
            receipt_content.replace(
                "- Task status after completion: DONE",
                "- Task status after completion: BLOCKED",
            ).replace(
                "## Blockers\n- None",
                "## Blockers\n- BLOCKED: test blocker; needs human decision",
            ),
            encoding="utf-8",
        )
        failed = run_script_expect_failure(harness_root / "checks" / "receipt_gate.py", [
            "--Receipt", str(blocked_receipt_path),
        ])
        assert_true(failed, "receipt gate should require evaluator repair for BLOCKED receipts")

        misplaced_receipt_path = harness_root / "task-briefs" / "057-2026-05-20-misplaced-receipt.md"
        misplaced_receipt_path.write_text(receipt_content, encoding="utf-8")
        failed = run_script_expect_failure(harness_root / "checks" / "receipt_gate.py", [
            "--Receipt", str(misplaced_receipt_path),
        ])
        assert_true(failed, "receipt gate should reject receipts under task-briefs")

        # --- Scope diff gate (pass) ---
        run_script(harness_root / "checks" / "scope_diff_gate.py", [
            "--TaskBrief", str(brief_path),
            "--ChangedFiles", "harness-engine/.dev-harness/scripts/new_task_brief.py",
        ])

        local_scope_output = run_script(harness_root / "checks" / "scope_diff_gate.py", [
            "--TaskBrief", str(brief_path),
            "--ChangedFiles", ".claude/settings.local.json",
        ])
        assert_true("LOCAL_EXCLUDED .claude/settings.local.json" in local_scope_output,
                     "scope-diff gate should exclude local .claude runtime state")

        runtime_scope_output = run_script(harness_root / "checks" / "scope_diff_gate.py", [
            "--TaskBrief", str(brief_path),
            "--ChangedFiles", "cockpit-api/tmp/cache/bootsnap/load-path-cache",
            "--ChangedFiles", "harness-engine/.dev-harness/automation/auto_state.json",
            "--ChangedFiles", "harness-engine/.dev-harness/automation/logs/run-20260525-125537-W37684/latest.txt",
            "--ChangedFiles", "harness-engine/.dev-harness/memory/indexes/memory-index.md",
            "--ChangedFiles", "harness-engine/meta-harness/signals/latest/run_metrics.json",
            "--ChangedFiles", "harness-engine/meta-harness/reports/meta-review-20260525-163134.md",
            "--ChangedFiles", "harness-engine/meta-harness/reports/meta-review-latest.md",
            "--ChangedFiles", "harness-engine/meta-harness/replays/results/replay-20260525-163134.json",
            "--ChangedFiles", "harness-engine/meta-harness/evidence-packets/latest/manifest.json",
            "--ChangedFiles", "harness-engine/meta-harness/experience/latest/summary.json",
            "--ChangedFiles", "openclacky",
        ])
        assert_true("LOCAL_EXCLUDED cockpit-api/tmp/cache/bootsnap/load-path-cache" in runtime_scope_output,
                     "scope-diff gate should exclude Rails bootsnap runtime cache")
        assert_true("LOCAL_EXCLUDED harness-engine/.dev-harness/automation/auto_state.json" in runtime_scope_output,
                     "scope-diff gate should exclude harness automation runtime state")
        assert_true("LOCAL_EXCLUDED harness-engine/.dev-harness/automation/logs/run-20260525-125537-W37684/latest.txt" in runtime_scope_output,
                     "scope-diff gate should exclude harness run logs")
        assert_true("LOCAL_EXCLUDED harness-engine/.dev-harness/memory/indexes/memory-index.md" in runtime_scope_output,
                     "scope-diff gate should exclude generated memory indexes")
        assert_true("LOCAL_EXCLUDED harness-engine/meta-harness/signals/latest/run_metrics.json" in runtime_scope_output,
                     "scope-diff gate should exclude meta latest signal cache")
        assert_true("LOCAL_EXCLUDED harness-engine/meta-harness/reports/meta-review-20260525-163134.md" in runtime_scope_output,
                     "scope-diff gate should exclude timestamped meta reports")
        assert_true("LOCAL_EXCLUDED harness-engine/meta-harness/reports/meta-review-latest.md" in runtime_scope_output,
                     "scope-diff gate should exclude latest meta reports")
        assert_true("LOCAL_EXCLUDED harness-engine/meta-harness/replays/results/replay-20260525-163134.json" in runtime_scope_output,
                     "scope-diff gate should exclude timestamped meta replays")
        assert_true("LOCAL_EXCLUDED harness-engine/meta-harness/evidence-packets/latest/manifest.json" in runtime_scope_output,
                     "scope-diff gate should exclude meta latest evidence cache")
        assert_true("LOCAL_EXCLUDED harness-engine/meta-harness/experience/latest/summary.json" in runtime_scope_output,
                     "scope-diff gate should exclude meta latest experience cache")
        assert_true("LOCAL_EXCLUDED openclacky" in runtime_scope_output,
                     "scope-diff gate should exclude dirty submodule marker")

        # --- Scope diff gate (should fail) ---
        failed = run_script_expect_failure(harness_root / "checks" / "scope_diff_gate.py", [
            "--TaskBrief", str(brief_path),
            "--ChangedFiles", "crates/hetm-cli/src/main.rs",
        ])
        assert_true(failed,
                     "scope-diff gate should fail for a changed file outside allowed scope")

        # --- Static checks on auto_harness_loop.py ---
        py_loop_path = harness_root / "scripts" / "auto_harness_loop.py"
        if py_loop_path.exists():
            loop_text = read_text(py_loop_path)
            assert_true("SelfTestAgentStream" not in loop_text,
                         "auto harness loop should not expose agent stream self-test mode")
            assert_true("round-000-selftest" not in loop_text,
                         "auto harness loop should not generate self-test log rounds")
            assert_true("stream_selftest" not in loop_text,
                         "auto harness loop should not generate stream_selftest role logs")
            assert_true("Set-ClaudeProjectSettings" in loop_text or "set_claude_project_settings" in loop_text,
                         "auto harness loop should override project Claude settings per role")
            assert_true("Get-ProviderFamily" in loop_text or "get_provider_family" in loop_text,
                         "auto harness loop should distinguish OpenAI and Anthropic providers")
            assert_true("anthropic" in loop_text.lower(),
                         "auto harness loop should only pass --model to Claude for Anthropic-compatible providers")
            assert_true("OPENAI_MODEL" in loop_text,
                         "auto harness loop should route OpenAI-compatible model names through environment settings")
            assert_true("Resolve-NextEpicContext" in loop_text or "resolve_next_epic_context" in loop_text,
                         "auto harness loop should resolve next epic continuation from a completed contract")
            assert_true("EPIC_COMPLETE_ADVANCED_TO_NEXT" in loop_text,
                         "auto harness loop should advance completed epics when next_epic is configured")
            assert_true("completed epic advanced to next_epic" in loop_text,
                         "auto harness loop should log completed epic continuation")
            assert_true("Test-TaskMatchesEpic" in loop_text or "test_task_matches_epic" in loop_text,
                         "auto harness loop should verify resumed tasks match the active epic")
            assert_true("latest task does not match active epic" in loop_text,
                         "auto harness loop should skip stale latest tasks from unrelated epics")
            assert_true("rolling_task_planner.py" in loop_text,
                         "auto harness loop should prepare rolling task specs from structured backlog")
            assert_true("backlog_json_path" in loop_text,
                         "auto harness loop should resolve structured backlog.json")
            assert_true("planner_spec_path" in loop_text,
                         "auto harness loop should pass prepared planner SpecFile to task_writer")
            assert_true("TASK_WRITER_MISSING_EPIC_ALIGNED_TASK" in loop_text,
                         "auto harness loop should fail clearly if task_writer does not create an active-epic task")
            assert_true("Invoke-GitCaptured" in loop_text or "invoke_git_captured" in loop_text,
                         "auto harness loop should capture git stderr without native command stderr noise")
            assert_true("RedirectStandardError" in loop_text or "redirect_standard_error" in loop_text or "stderr" in loop_text,
                         "auto harness loop should read git stderr as process output")
            assert_true("Join-ProcessArguments" in loop_text or "join_process_arguments" in loop_text,
                         "auto harness loop should support captured git invocation on Windows Python")
            assert_true("ArgumentList.Add" not in loop_text,
                         "auto harness loop should not depend on ProcessStartInfo.ArgumentList")
            assert_true("Test-ExternalWorkspaceRepairTask" in loop_text or "test_external_workspace_repair_task" in loop_text,
                         "auto harness loop should keep external workspace repair guard")
            assert_true("TitleOrIntent" in loop_text or "title_or_intent" in loop_text,
                         "auto harness loop should distinguish repair intent from forbidden path mentions")
            assert_true("product_acceptance" in loop_text,
                         "auto harness loop should classify product acceptance failures distinctly")
            assert_true("Acceptance gate failures are product/task failures first" in loop_text,
                         "auto harness repair prompt should not steer product failures into harness repair")

        # --- Task-scoped acceptance gate wiring ---
        acceptance_gate_path = root / "harness-engine" / "acceptance" / "gates" / "acceptance_gate.py"
        task_checker_path = root / "harness-engine" / "acceptance" / "gates" / "task_scoped_checker.py"
        dev_gate_path = harness_root / "checks" / "dev_gate.py"
        acceptance_gate_text = read_text(acceptance_gate_path)
        task_checker_text = read_text(task_checker_path)
        dev_gate_text = read_text(dev_gate_path)
        assert_true("--task-only" in acceptance_gate_text,
                     "acceptance gate should expose task-only mode")
        assert_true("run_task_only_gate" in acceptance_gate_text,
                     "acceptance gate should expose a reusable task-only function")
        assert_true("cockpit_gateway" in task_checker_text,
                     "task scoped checker should cover cockpit_gateway task acceptance")
        assert_true("no browser or app server required" in task_checker_text,
                     "task scoped checker should document local-only acceptance")
        assert_true("--task-only" in dev_gate_text,
                     "dev gate should try task-scoped acceptance before full E2E")
        assert_true("full E2E skipped for this task" in dev_gate_text,
                     "dev gate should skip full E2E only after task-scoped acceptance passes")

        print("[programmatic-selftest] PASS")

    finally:
        numbered_brief_path = harness_root / "task-briefs" / "997-2026-05-20-programmatic-harness-smoke-numbered.md"
        remove_if_present(numbered_brief_path)
        selftest_brief_path = harness_root / "task-briefs" / "057-2026-05-20-programmatic-harness-smoke.md"
        remove_if_present(selftest_brief_path)
        misplaced_receipt_path = harness_root / "task-briefs" / "057-2026-05-20-misplaced-receipt.md"
        remove_if_present(misplaced_receipt_path)
        if not args.KeepTemp and temp_root.exists():
            shutil.rmtree(str(temp_root))


if __name__ == "__main__":
    main()
