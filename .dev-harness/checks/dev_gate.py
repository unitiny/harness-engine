import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import harness_shared as hs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--SkipAcceptance", action="store_true")
    parser.add_argument("--SkipEngine", action="store_true")
    parser.add_argument("--SkipRust", action="store_true", help="Legacy alias, ignored")
    parser.add_argument("--Fast", action="store_true")
    args = parser.parse_args()

    root = hs.find_repo_root()
    os.chdir(root)

    print(f"[dev-gate] root: {root}")

    harness_root = root / "harness-engine" / ".dev-harness"

    required = [
        "harness-engine/.dev-harness/README.md",
        "harness-engine/.dev-harness/docs/governance/project-map.md",
        "harness-engine/.dev-harness/docs/governance/decision-log.md",
        "harness-engine/.dev-harness/docs/governance/risk-register.md",
        "harness-engine/.dev-harness/docs/document-governance.md",
        "harness-engine/.dev-harness/docs/operations/roadmap.md",
        "harness-engine/.dev-harness/docs/operations/runbook.md",
        "harness-engine/.dev-harness/docs/operations/eval-protocol.md",
        "harness-engine/.dev-harness/docs/operations/phase-0-acceptance.md",
        "harness-engine/.dev-harness/docs/policies/tool-policy.md",
        "harness-engine/.dev-harness/docs/policies/strategy-development-guide.md",
        "harness-engine/.dev-harness/docs/policies/openai-policy.md",
        "harness-engine/.dev-harness/docs/protocols/self-evolution-protocol.md",
        "harness-engine/.dev-harness/docs/operations/memory-architecture-plan.md",
        "harness-engine/.dev-harness/templates/task-template.md",
        "harness-engine/.dev-harness/templates/review-template.md",
        "harness-engine/.dev-harness/templates/execution-receipt-template.md",
        "harness-engine/.dev-harness/checks/write_task_gate.py",
        "harness-engine/.dev-harness/checks/review_gate.py",
        "harness-engine/.dev-harness/checks/receipt_gate.py",
        "harness-engine/.dev-harness/checks/memory_gate.py",
        "harness-engine/.dev-harness/checks/epic_alignment_gate.py",
        "harness-engine/.dev-harness/checks/scope_diff_gate.py",
        "harness-engine/.dev-harness/checks/programmatic_harness_selftest.py",
        "harness-engine/.dev-harness/checks/build_memory_index.py",
        "harness-engine/.dev-harness/scripts/new_task_brief.py",
        "harness-engine/.dev-harness/scripts/new_review_draft.py",
        "harness-engine/.dev-harness/scripts/harness_context_summary.py",
        "harness-engine/.dev-harness/scripts/auto_harness_loop.py",
        "harness-engine/.dev-harness/scripts/register_epic.py",
        "harness-engine/.dev-harness/automation/README.md",
        "harness-engine/.dev-harness/automation/agent-config.example.json",
        "harness-engine/.dev-harness/automation/auto_state.example.json",
        "harness-engine/.dev-harness/automation/program-state.example.json",
        "harness-engine/.dev-harness/automation/epic-contract.example.json",
        "harness-engine/.dev-harness/checks/epic_alignment_gate.py",
        "harness-engine/.dev-harness/checks/programmatic_harness_selftest.py",
        "harness-engine/.dev-harness/checks/scope_diff_gate.py",
        "harness-engine/.dev-harness/scripts/new_task_brief.py",
        "harness-engine/.dev-harness/scripts/new_review_draft.py",
        "harness-engine/.dev-harness/scripts/harness_context_summary.py",
        "harness-engine/.dev-harness/memory/README.md",
        "harness-engine/.dev-harness/memory/project-memory.md",
        "harness-engine/.dev-harness/memory/active-context.md",
        "harness-engine/.dev-harness/memory/memory-schema.md",
        "harness-engine/.dev-harness/memory/skill-candidates.md",
        "AGENT.MD",
    ]

    for path in required:
        if not Path(path).exists():
            print(f"[dev-gate] missing required file: {path}", file=sys.stderr)
            sys.exit(1)

    policy_checks = [
        ("harness-engine/.dev-harness/README.md", "Stop Conditions", "README defines stop conditions"),
        ("harness-engine/.dev-harness/docs/policies/tool-policy.md", "Blocked Without Explicit User Approval", "tool policy defines blocked operations"),
        ("harness-engine/.dev-harness/docs/operations/eval-protocol.md", "does not evaluate", "eval protocol separates dev eval from model quality"),
        ("harness-engine/.dev-harness/docs/protocols/self-evolution-protocol.md", "Why did the harness fail to constrain this?", "self-evolution protocol requires harness gap analysis"),
        ("harness-engine/.dev-harness/docs/protocols/self-evolution-protocol.md", "Instruction Hierarchy", "self-evolution protocol encodes instruction hierarchy"),
        ("harness-engine/.dev-harness/docs/protocols/self-evolution-protocol.md", "Trace Monitoring", "self-evolution protocol requires trace monitoring"),
        ("harness-engine/.dev-harness/docs/protocols/self-evolution-protocol.md", "Rule Rationale", "self-evolution protocol requires rule rationale"),
        ("harness-engine/.dev-harness/docs/protocols/self-evolution-protocol.md", "Evaluator Repair", "self-evolution protocol requires evaluator repair"),
        ("harness-engine/.dev-harness/docs/protocols/self-evolution-protocol.md", "prediction_contract", "self-evolution protocol requires prediction contracts"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "docs/protocols/self-evolution-protocol.md", "runbook references self-evolution protocol"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "authority order", "runbook requires authority order check"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "repair the evaluator", "runbook requires evaluator repair after failures"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "Close The Task", "runbook requires explicit task closure"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "memory/skill-candidates.md", "runbook routes reusable procedures to skill candidates"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "Dual-Model Workflow", "runbook defines dual-model workflow"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "SHORT_COMMAND_TASK_QUEUE", "runbook defines short-command task queue"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "PREVIOUS_TASK_ACCEPTANCE_GATE", "runbook requires previous task acceptance before writing next task"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "Task Stream", "runbook defines task stream scoped acceptance"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "latest completed or blocked task in the same Task Stream", "runbook limits previous acceptance to same task stream"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "memory_gate.py", "runbook references memory gate"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "latest unclaimed", "runbook defines latest unclaimed task selection"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "AUTO_HARNESS_LOOP", "runbook defines auto harness loop"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "automation/auto_state.json", "runbook routes auto state to automation directory"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "Every round commits locally", "runbook requires local commits for every auto round"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "Codex/GPT acts as architect", "runbook assigns architect role"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "execution receipt", "runbook requires implementer receipt"),
        ("harness-engine/.dev-harness/templates/task-template.md", "Scope Contract", "task template defines scope contract"),
        ("harness-engine/.dev-harness/templates/task-template.md", "Task Status: UNCLAIMED", "task template marks new tasks unclaimed"),
        ("harness-engine/.dev-harness/templates/task-template.md", "Task Stream", "task template requires task stream"),
        ("harness-engine/.dev-harness/templates/task-template.md", "Previous Task Acceptance", "task template requires previous task acceptance context"),
        ("harness-engine/.dev-harness/templates/task-template.md", "latest completed or blocked task in the same stream", "task template limits previous acceptance to same stream"),
        ("harness-engine/.dev-harness/templates/task-template.md", "Acceptance audit performed", "task template requires write-task acceptance audit"),
        ("harness-engine/.dev-harness/templates/task-template.md", "Error-fix tasks included in this brief", "task template includes acceptance-error repair scope"),
        ("harness-engine/.dev-harness/templates/task-template.md", "Do not write a clean follow-on task", "task template blocks ignoring known acceptance errors"),
        ("harness-engine/.dev-harness/templates/task-template.md", "Short-command rule", "task template documents short-command rule"),
        ("harness-engine/.dev-harness/templates/task-template.md", "Forbidden operations unless explicitly approved", "task template blocks forbidden operations"),
        ("harness-engine/.dev-harness/templates/task-template.md", "Required Execution Receipt", "task template requires execution receipt"),
        ("harness-engine/.dev-harness/templates/execution-receipt-template.md", "Scope Check", "execution receipt template captures scope check"),
        ("harness-engine/.dev-harness/templates/execution-receipt-template.md", "Task status before claim", "execution receipt captures task claim transition"),
        ("harness-engine/.dev-harness/templates/execution-receipt-template.md", "Secret And Safety Check", "execution receipt template captures secret safety"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Task Closure Packet", "review template requires task closure packet"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Skill candidate updated or explicitly rejected", "review template forces skill-candidate decision"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Dual-Model Scope Review", "review template includes dual-model scope review"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Task status transition", "review template checks task status transition"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Previous task acceptance used to shape this task", "review template checks previous task acceptance use"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Task stream", "review template records task stream"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Same-stream previous task", "review template records same-stream previous task"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Write-task acceptance audit checked", "review template checks write-task acceptance audit"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Acceptance errors found before task creation", "review template records acceptance errors"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Error-fix scope included in task", "review template checks error fixes are scoped"),
        ("harness-engine/.dev-harness/templates/review-template.md", "Receipt claims contradicted by diff", "review template requires diff-vs-receipt check"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "review_gate.py", "runbook references review gate"),
        ("harness-engine/.dev-harness/README.md", "review_gate.py", "README references review gate"),
        ("AGENT.MD", "Final Response Precondition", "agent guide blocks final response before harness closure"),
        ("AGENT.MD", "automatic post-task hook", "agent guide explains hook substitute"),
        ("AGENT.MD", "Dual-Model Development", "agent guide defines dual-model development"),
        ("AGENT.MD", "SHORT_COMMAND_TASK_QUEUE", "agent guide defines short-command task queue"),
        ("AGENT.MD", "PREVIOUS_TASK_ACCEPTANCE_GATE", "agent guide requires previous task acceptance before writing next task"),
        ("AGENT.MD", "Task Stream", "agent guide defines task stream scoped acceptance"),
        ("AGENT.MD", "WRITE_TASK_ACCEPTANCE_AUDIT", "agent guide requires rigorous write-task acceptance audit"),
        ("AGENT.MD", "Default Harness Activation", "agent guide defines default harness activation"),
        ("AGENT.MD", "DEFAULT_HARNESS_ACTIVE", "agent guide says harness is default active"),
        ("AGENT.MD", "templates/execution-receipt-template.md", "agent guide points to execution receipt template"),
        ("AGENT.MD", "docs/operations/runbook.md", "agent guide points to current runbook path"),
        ("harness-engine/.dev-harness/README.md", "Dual-Model Workflow", "README defines dual-model workflow"),
        ("harness-engine/.dev-harness/README.md", "SHORT_COMMAND_TASK_QUEUE", "README defines short-command task queue"),
        ("harness-engine/.dev-harness/README.md", "PREVIOUS_TASK_ACCEPTANCE_GATE", "README requires previous task acceptance before writing next task"),
        ("harness-engine/.dev-harness/README.md", "Task Stream", "README defines task stream scoped acceptance"),
        ("harness-engine/.dev-harness/README.md", "WRITE_TASK_ACCEPTANCE_AUDIT", "README requires rigorous write-task acceptance audit"),
        ("harness-engine/.dev-harness/README.md", "Default activation rule", "README defines default activation rule"),
        ("harness-engine/.dev-harness/README.md", "DEFAULT_HARNESS_ACTIVE", "README marks default harness active"),
        ("harness-engine/.dev-harness/README.md", "execution-receipt-template.md", "README lists execution receipt template"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "Default harness activation", "runbook defines default harness activation"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "DEFAULT_HARNESS_ACTIVE", "runbook marks default harness active"),
        ("harness-engine/.dev-harness/prompts/architect.md", "bounded implementer", "architect prompt defines bounded implementer role"),
        ("harness-engine/.dev-harness/prompts/architect.md", "DEFAULT_HARNESS_ACTIVE", "architect prompt requires default harness use"),
        ("harness-engine/.dev-harness/prompts/architect.md", "写task", "architect prompt handles write-task short command"),
        ("harness-engine/.dev-harness/prompts/architect.md", "PREVIOUS_TASK_ACCEPTANCE_GATE", "architect prompt checks previous task before writing next task"),
        ("harness-engine/.dev-harness/prompts/architect.md", "same Task Stream", "architect prompt limits previous acceptance to same task stream"),
        ("harness-engine/.dev-harness/prompts/architect.md", "WRITE_TASK_ACCEPTANCE_AUDIT", "architect prompt requires rigorous write-task acceptance audit"),
        ("harness-engine/.dev-harness/prompts/architect.md", "only shared control plane", "architect prompt prevents split long-lived docs"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "execution-receipt-template.md", "implementer prompt requires receipt template"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "DEFAULT_HARNESS_ACTIVE", "implementer prompt requires default harness use"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "执行task", "implementer prompt handles execute-task short command"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "Task Status: UNCLAIMED", "implementer prompt claims unclaimed tasks"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "allowed files", "implementer prompt enforces allowed files"),
        ("harness-engine/.dev-harness/prompts/reviewer.md", "DEPRECATED", "reviewer prompt marked as deprecated"),
        ("harness-engine/.dev-harness/prompts/reviewer.md", "implementer.md", "reviewer deprecation points to implementer"),
        ("harness-engine/.dev-harness/checks/receipt_gate.py", "assert_receipt", "receipt gate validates expanded receipt completeness"),
        ("harness-engine/.dev-harness/templates/execution-receipt-template.md", "Scope Independent Check", "execution receipt template includes scope independent check"),
        ("harness-engine/.dev-harness/templates/execution-receipt-template.md", "Gate Evidence", "execution receipt template includes gate evidence"),
        ("harness-engine/.dev-harness/templates/execution-receipt-template.md", "Security Check", "execution receipt template includes expanded security check"),
        ("harness-engine/.dev-harness/templates/execution-receipt-template.md", "Memory Promotion Decisions", "execution receipt template includes memory promotion decisions"),
        ("harness-engine/.dev-harness/templates/execution-receipt-template.md", "Verification Self-Assessment", "execution receipt template includes verification self-assessment"),
        ("harness-engine/.dev-harness/templates/execution-receipt-template.md", "Next-Task Prediction", "execution receipt template includes next-task prediction"),
        ("harness-engine/.dev-harness/prompts/test-engineer.md", "DEFAULT_HARNESS_ACTIVE", "test engineer prompt requires default harness expectation"),
        ("harness-engine/.dev-harness/prompts/test-engineer.md", "scope_diff_gate.py", "test engineer prompt checks scope diff gate verification"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "最终回复前完成 harness closure", "implementer prompt requires closure before final response"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "Scope Independent Check", "implementer prompt requires scope independent check"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "Memory Promotion Decisions", "implementer prompt handles memory promotion"),
        ("harness-engine/.dev-harness/prompts/architect.md", "最终回复前必须触发或规划 harness closure", "architect prompt requires closure planning"),
        ("harness-engine/.dev-harness/prompts/test-engineer.md", "Final response precondition", "test engineer prompt requires closure evidence"),
        ("harness-engine/.dev-harness/memory/memory-schema.md", "skill-candidates.md", "memory schema defines skill candidates"),
        ("harness-engine/.dev-harness/memory/memory-schema.md", "memory-manifest.json", "memory schema defines manifest index"),
        ("harness-engine/.dev-harness/memory/README.md", "generated indexes", "memory README distinguishes generated indexes"),
        ("harness-engine/.dev-harness/docs/operations/memory-architecture-plan.md", "bounded hot context", "memory plan defines hot context layer"),
        ("harness-engine/.dev-harness/docs/operations/memory-architecture-plan.md", "Default: no vector DB", "memory plan rejects default vector DB"),
        ("harness-engine/.dev-harness/docs/operations/memory-architecture-plan.md", "memory_gate.py", "memory plan requires memory gate"),
        ("harness-engine/.dev-harness/memory/skill-candidates.md", "Trigger condition", "skill candidate ledger records trigger conditions"),
        ("harness-engine/.dev-harness/memory/skill-candidates.md", "Next validation signal", "skill candidate ledger requires validation signal"),
        ("harness-engine/.dev-harness/docs/operations/phase-0-acceptance.md", "not accepted by `cargo test` alone", "phase 0 requires more than cargo test"),
        ("harness-engine/.dev-harness/docs/operations/phase-0-acceptance.md", "available_at <= event_time", "phase 0 enforces point-in-time availability"),
        ("harness-engine/.dev-harness/docs/operations/phase-0-acceptance.md", "reject unapproved root markdown files", "phase 0 enforces harness doc hygiene"),
        ("harness-engine/.dev-harness/docs/document-governance.md", "Do not place task notes", "document governance blocks loose root notes"),
        ("harness-engine/.dev-harness/docs/document-governance.md", "Only `README.md` may live at the root", "document governance defines root whitelist"),
        ("harness-engine/.dev-harness/docs/document-governance.md", "automation/", "document governance classifies automation directory"),
        ("harness-engine/.dev-harness/README.md", "AUTO_HARNESS_LOOP", "README defines auto harness loop"),
        ("harness-engine/.dev-harness/README.md", "agent-config.json", "README points to role model config"),
        ("harness-engine/.dev-harness/automation/README.md", "every round is committed locally", "automation README requires local per-round commits"),
        ("harness-engine/.dev-harness/automation/README.md", "full AI run logs", "automation README requires AI run logs"),
        ("harness-engine/.dev-harness/automation/README.md", "program-state.json", "automation README documents Program Harness state"),
        ("harness-engine/.dev-harness/automation/README.md", "Epic Contract", "automation README documents Epic Contract alignment"),
        ("harness-engine/.dev-harness/automation/agent-config.example.json", "gpt5_planner_reviewer", "agent config supports GPT planner and reviewer provider"),
        ("harness-engine/.dev-harness/automation/agent-config.example.json", "glm_executor", "agent config supports GLM executor provider"),
        ("harness-engine/.dev-harness/automation/agent-config.example.json", "headers", "agent config supports provider headers"),
        ("harness-engine/.dev-harness/automation/program-state.example.json", "active_epic", "program state tracks active epic"),
        ("harness-engine/.dev-harness/automation/epic-contract.example.json", "acceptance_items", "epic contract defines acceptance items"),
        ("harness-engine/.dev-harness/checks/epic_alignment_gate.py", "Acceptance Item", "epic alignment gate checks acceptance item binding"),
        ("harness-engine/.dev-harness/checks/programmatic_harness_selftest.py", "epic_alignment_gate.py", "programmatic selftest covers epic alignment gate"),
        ("harness-engine/.dev-harness/checks/programmatic_harness_selftest.py", "register_epic.py", "programmatic selftest covers epic registration"),
        ("harness-engine/.dev-harness/scripts/register_epic.py", "contract.json", "register epic writes contract"),
        ("harness-engine/.dev-harness/scripts/new_task_brief.py", "Epic Alignment", "task generator emits epic alignment section"),
        ("harness-engine/.dev-harness/scripts/new_task_brief.py", "--SpecFile", "task generator supports spec-file input"),
        ("harness-engine/.dev-harness/scripts/auto_harness_loop.py", "invoke_agent_role", "auto loop invokes role-based AI agents"),
        ("harness-engine/.dev-harness/scripts/auto_harness_loop.py", "preflight", "auto loop implements preflight handling"),
        ("harness-engine/.dev-harness/scripts/auto_harness_loop.py", "Program/Epic context", "auto loop passes epic context to task writer"),
        ("harness-engine/.dev-harness/scripts/auto_harness_loop.py", "add_claude_model_arg", "auto loop forces claude model from agent config"),
        ("harness-engine/.dev-harness/scripts/auto_harness_loop.py", "set_claude_project_settings", "auto loop overrides project Claude settings per role"),
        ("harness-engine/.dev-harness/checks/programmatic_harness_selftest.py", "auto harness loop should not generate self-test log rounds", "programmatic selftest prevents self-test log generation"),
        ("harness-engine/.dev-harness/scripts/new_task_brief.py", "Generated by: scripts/new_task_brief.py", "task brief generator records provenance"),
        ("harness-engine/.dev-harness/scripts/new_review_draft.py", "scope_diff_gate.py", "review draft generator uses scope diff gate"),
        ("harness-engine/.dev-harness/scripts/new_review_draft.py", "--Task", "review draft generator supports short numbered task input"),
        ("harness-engine/.dev-harness/checks/scope_diff_gate.py", "Allowed files or paths:", "scope diff gate reads allowed files"),
        ("harness-engine/.dev-harness/checks/epic_alignment_gate.py", "Epic Alignment", "epic alignment gate checks epic metadata"),
        ("harness-engine/.dev-harness/checks/programmatic_harness_selftest.py", "--SpecFile", "programmatic selftest covers spec-file task generation"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "PROGRAMMATIC_HARNESS_GENERATION", "runbook documents programmatic harness generation"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "--SpecFile", "runbook documents spec-file task generation"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "--Task <NNN>", "runbook documents short review task input"),
        ("harness-engine/.dev-harness/docs/operations/runbook.md", "TOKEN_BOUNDED_CONTEXT", "runbook documents token-bounded context"),
        ("harness-engine/.dev-harness/README.md", "PROGRAMMATIC_HARNESS_GENERATION", "README documents programmatic harness generation"),
        ("harness-engine/.dev-harness/README.md", "--SpecFile", "README documents spec-file task generation"),
        ("harness-engine/.dev-harness/README.md", "--Task NNN", "README documents short review task input"),
        ("harness-engine/.dev-harness/README.md", "TOKEN_BOUNDED_CONTEXT", "README documents token-bounded context"),
        ("harness-engine/.dev-harness/prompts/architect.md", "scripts/new_task_brief.py", "architect prompt requires task generator"),
        ("harness-engine/.dev-harness/prompts/architect.md", "harness_context_summary.py", "architect prompt requires context summary"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "scope_diff_gate.py", "implementer prompt requires scope diff gate"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "harness_context_summary.py", "implementer prompt requires context summary"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "scripts/new_task_brief.py", "implementer prompt routes task edits through generator"),
        ("harness-engine/.dev-harness/prompts/implementer.md", "harness_context_summary.py", "implementer prompt requires context summary"),
        ("harness-engine/.dev-harness/templates/task-template.md", "do not copy this whole template by hand", "task template discourages hand-written briefs"),
        ("harness-engine/.dev-harness/templates/review-template.md", "new_review_draft.py", "review template routes through generator"),
        ("harness-engine/.dev-harness/scripts/harness_context_summary.py", "HARNESS_CONTEXT_SUMMARY", "context summary script prints stable marker"),
        ("harness-engine/.dev-harness/scripts/harness_context_summary.py", "--SpecFile", "context summary advertises spec-file task generation"),
        ("harness-engine/.dev-harness/scripts/harness_context_summary.py", "--Task <NNN>", "context summary advertises short review task input"),
        ("harness-engine/.dev-harness/scripts/harness_context_summary.py", "Repo-root command rules", "context summary prints repo-root command rules"),
        ("harness-engine/.dev-harness/scripts/harness_context_summary.py", "verify file exists before Read", "context summary requires file existence checks"),
        ("harness-engine/.dev-harness/docs/policies/tool-policy.md", "--SpecFile", "tool policy requires spec-file invocation for long task input"),
        ("harness-engine/.dev-harness/docs/policies/tool-policy.md", "Repo-root 命令规则", "tool policy requires repo-root command discipline"),
        ("harness-engine/.dev-harness/docs/policies/tool-policy.md", "new_review_draft.py --Task <NNN>", "tool policy requires short review task input"),
        ("harness-engine/.dev-harness/docs/policies/tool-policy.md", "rg", "tool policy prefers rg over unsupported Grep flags"),
        ("harness-engine/.dev-harness/scripts/auto_harness_loop.py", "Do not encode long JSON", "task writer prompt blocks long shell-quoted generator commands"),
        ("harness-engine/.dev-harness/scripts/auto_harness_loop.py", "verify file exists before Read", "auto loop prompts require file existence checks"),
        ("harness-engine/.dev-harness/scripts/auto_harness_loop.py", "never run harness generators from", "auto loop prompts prevent wrong-cwd generator calls"),
        ("harness-engine/.dev-harness/scripts/auto_harness_loop.py", "new_review_draft.py --Task <NNN>", "reviewer prompt prefers short review task input"),
        ("harness-engine/.dev-harness/checks/programmatic_harness_selftest.py", "harness_context_summary.py", "programmatic selftest covers context summary"),
        ("harness-engine/.dev-harness/docs/governance/project-map.md", "Risk Classes", "project map defines risk classes"),
        ("harness-engine/.dev-harness/docs/policies/openai-policy.md", "Token Budget", "openai policy defines token budget"),
        ("harness-engine/.dev-harness/docs/policies/openai-policy.md", "Prohibited Uses", "openai policy defines prohibited uses"),
        ("AGENT.MD", "Long Crowding Exhaustion", "agent guide states strategy MVP"),
        ("harness-engine/.dev-harness/docs/policies/strategy-development-guide.md", "Leakage Checks", "strategy guide defines leakage checks"),

    ]

    for check_path, pattern, name in policy_checks:
        content = Path(check_path).read_text(encoding="utf-8")
        if re.escape(pattern) == pattern:
            if pattern not in content:
                print(f"[dev-gate] policy check failed: {name}", file=sys.stderr)
                sys.exit(1)
        else:
            if not re.search(pattern, content):
                print(f"[dev-gate] policy check failed: {name}", file=sys.stderr)
                sys.exit(1)

    allowed_root_markdown = ["README.md"]

    unexpected_root_markdown = [
        f for f in harness_root.iterdir()
        if f.is_file() and f.suffix == ".md" and f.name not in allowed_root_markdown
    ]

    if unexpected_root_markdown:
        paths = "\n".join(str(f) for f in unexpected_root_markdown)
        print(f"[dev-gate] unclassified .dev-harness root markdown files found. Only README.md may live at the root. Move files into docs/, templates/, task-briefs/, reviews/, memory/, or prompts/:\n{paths}", file=sys.stderr)
        sys.exit(1)

    task_briefs_dir = harness_root / "task-briefs"
    task_brief_pattern = re.compile(r'^\d{3}-\d{4}-\d{2}-\d{2}-.+\.md$')

    unnumbered_task_briefs = [
        f for f in task_briefs_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and not task_brief_pattern.match(f.name)
    ]

    if unnumbered_task_briefs:
        paths = "\n".join(str(f) for f in unnumbered_task_briefs)
        print(f"[dev-gate] unnumbered task brief files found. Use NNN-YYYY-MM-DD-short-name.md:\n{paths}", file=sys.stderr)
        sys.exit(1)

    prefix_re = re.compile(r'^(\d{3})-')
    task_brief_files = sorted(
        [f for f in task_briefs_dir.iterdir() if f.is_file() and f.suffix == ".md" and prefix_re.match(f.name)],
        key=lambda f: f.name
    )
    prefix_groups = {}
    for f in task_brief_files:
        m = prefix_re.match(f.name)
        if m:
            pfx = m.group(1)
            prefix_groups.setdefault(pfx, []).append(f)

    duplicate_task_prefixes = {pfx: files for pfx, files in prefix_groups.items() if len(files) > 1}

    if duplicate_task_prefixes:
        details = "\n".join(
            f"{pfx}: {', '.join(f.name for f in files)}"
            for pfx, files in duplicate_task_prefixes.items()
        )
        print(f"[dev-gate] duplicate task brief sequence prefixes found:\n{details}", file=sys.stderr)
        sys.exit(1)

    reviews_dir = harness_root / "reviews"

    unnumbered_reviews = [
        f for f in reviews_dir.iterdir()
        if f.is_file() and f.suffix == ".md" and not task_brief_pattern.match(f.name)
    ]

    if unnumbered_reviews:
        paths = "\n".join(str(f) for f in unnumbered_reviews)
        print(f"[dev-gate] unnumbered review files found. Use NNN-YYYY-MM-DD-short-name.md:\n{paths}", file=sys.stderr)
        sys.exit(1)

    review_files = sorted(
        [f for f in reviews_dir.iterdir() if f.is_file() and f.suffix == ".md" and prefix_re.match(f.name)],
        key=lambda f: f.name
    )
    review_prefix_groups = {}
    for f in review_files:
        m = prefix_re.match(f.name)
        if m:
            pfx = m.group(1)
            review_prefix_groups.setdefault(pfx, []).append(f)

    duplicate_review_prefixes = {pfx: files for pfx, files in review_prefix_groups.items() if len(files) > 1}

    if duplicate_review_prefixes:
        details = "\n".join(
            f"{pfx}: {', '.join(f.name for f in files)}"
            for pfx, files in duplicate_review_prefixes.items()
        )
        print(f"[dev-gate] duplicate review sequence prefixes found:\n{details}", file=sys.stderr)
        sys.exit(1)

    bad_path_pattern = re.compile(r"docs/(governance|operations|policies|protocols)/docs/|templates/templates/")

    for dirpath, dirnames, filenames in os.walk(harness_root):
        for fname in filenames:
            if not fname.endswith((".md", ".py")):
                continue
            fpath = Path(dirpath) / fname
            if fpath.resolve() == Path(__file__).resolve():
                continue
            if fpath.name == "dev_gate.py" and fpath.parent.name == "checks":
                continue
            try:
                content = fpath.read_text(encoding="utf-8")
            except Exception:
                continue
            for i, line in enumerate(content.splitlines(), 1):
                if bad_path_pattern.search(line):
                    print(f"[dev-gate] duplicated .dev-harness path references found:\n{fpath}:{i}: {line.strip()}", file=sys.stderr)
                    sys.exit(1)

    checks_dir = harness_root / "checks"
    fast_flag = ["--Fast"] if args.Fast else []
    r = subprocess.run(
        [sys.executable, str(checks_dir / "memory_gate.py")] + fast_flag
    )
    if r.returncode != 0:
        sys.exit(1)

    latest_task_files = sorted(
        [f for f in task_briefs_dir.iterdir() if f.is_file() and f.suffix == ".md"],
        key=lambda f: f.name
    )
    if latest_task_files:
        latest_task = latest_task_files[-1]
        r = subprocess.run(
            [sys.executable, str(checks_dir / "write_task_gate.py"), "--TaskBrief", str(latest_task)]
        )
        if r.returncode != 0:
            sys.exit(1)

    r = subprocess.run(
        [sys.executable, str(checks_dir / "review_gate.py")]
    )
    if r.returncode != 0:
        sys.exit(1)

    # --- Receipt Gate (validates expanded execution receipts) ---
    receipt_gate = checks_dir / "receipt_gate.py"
    if receipt_gate.exists():
        print("[dev-gate] receipt gate")
        r = subprocess.run([sys.executable, str(receipt_gate)])
        if r.returncode != 0:
            sys.exit(1)

    r = subprocess.run(
        [sys.executable, str(checks_dir / "programmatic_harness_selftest.py")]
    )
    if r.returncode != 0:
        sys.exit(1)

    # --- Risk-Aware Acceptance Gate ---
    # MEDIUM+ risk tasks must never skip acceptance — the root cause of task-001 FAIL.
    latest_risk_class = ""
    for tf in reversed(latest_task_files) if latest_task_files else []:
        tc = tf.read_text(encoding="utf-8", errors="replace")
        rm = re.search(r"Risk Class\s*\n\s*(LOW|MEDIUM|HIGH|BLOCKED_WITHOUT_APPROVAL)", tc, re.IGNORECASE)
        if rm:
            latest_risk_class = rm.group(1).upper()
        break

    if args.SkipAcceptance and latest_risk_class in ("MEDIUM", "HIGH", "BLOCKED_WITHOUT_APPROVAL"):
        print(
            f"[dev-gate] --SkipAcceptance is forbidden for {latest_risk_class} risk tasks "
            f"(latest task risk: {latest_risk_class}). Run full acceptance.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.SkipAcceptance and not args.Fast:
        acceptance_gate = root / "harness-engine" / "acceptance" / "gates" / "acceptance_gate.py"
        scenario_dir = root / "harness-engine" / "acceptance" / "scenarios"
        quality_gates = root / "harness-engine" / "acceptance" / "config" / "quality-gates.yaml"
        report_dir = root / "harness-engine" / "acceptance" / "reports"

        if acceptance_gate.exists() and scenario_dir.exists():
            print("[dev-gate] acceptance gate")
            if latest_task_files:
                task_only_cmd = [
                    sys.executable, str(acceptance_gate),
                    "--task-only",
                    "--task-brief", str(latest_task_files[-1]),
                    "--repo-root", str(root),
                ]
                task_only = subprocess.run(task_only_cmd)
                if task_only.returncode == 0:
                    print("[dev-gate] task-scoped acceptance gate passed; full E2E skipped for this task")
                    print("[dev-gate] PASS")
                    return
                if task_only.returncode != 2:
                    sys.exit(1)
                print("[dev-gate] no task-scoped acceptance checker matched; running full E2E acceptance")

            cmd = [
                sys.executable, str(acceptance_gate),
                "--scenario-dir", str(scenario_dir),
                "--env", "dev",
                "--report-dir", str(report_dir),
            ]
            if quality_gates.exists():
                cmd.extend(["--quality-gates", str(quality_gates)])
            r = subprocess.run(cmd)
            if r.returncode != 0:
                sys.exit(1)
        else:
            print("[dev-gate] acceptance gate skipped (no scenarios or gate script found)")
    elif args.Fast:
        print("[dev-gate] acceptance gate skipped (--Fast mode)")

    print("[dev-gate] PASS")


if __name__ == "__main__":
    main()
