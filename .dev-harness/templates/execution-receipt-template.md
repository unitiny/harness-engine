# Execution Receipt Template

Use this after completing a task brief. Keep it factual and short.
Do not include raw model transcripts, chain-of-thought, secrets, or broad
project summaries. This expanded receipt replaces the separate reviewer role —
the implementer self-verifies and records evidence directly.

## Task

- Task brief:
- Task status before claim:
- Task status after completion:
- Implementer:
- Date:

## Files Changed

- `path/to/file`

## Summary

- What changed:
- Why it matches the brief:

## Acceptance Criteria Status

- [ ] Criterion:
- [ ] Criterion:

## Commands Run

```powershell
command
```

Result:

```text
pass/fail/not run, with only the relevant excerpt
```

## Scope Check

- Changed only allowed files: yes/no
- Performed forbidden operations: yes/no
- Dependency or lockfile changes: yes/no
- Generated artifact rewrites: yes/no
- Opportunistic cleanup/refactor: yes/no

## Scope Independent Check

Run `harness-engine/.dev-harness/checks/scope_diff_gate.py` and paste its
output here. Do not self-report scope compliance — use the programmatic check.

```text
(scope_diff_gate.py output)
```

## Acceptance Verification

For each acceptance criterion from the task brief, record how it was verified:

- Criterion 1: (command output / manual check / reason not run)
- Criterion 2: (command output / manual check / reason not run)

## Deliverable File Existence Check

For each file listed in the task brief's `Files Expected` or implied by
acceptance criteria, verify the file exists and is non-empty before marking
the task DONE. This is a mandatory step — task-001 taught us that claiming
"all AC met" while 7 files are missing is the most common delivery gap.

- `path/to/expected/file`: (exists: yes/no, size: N bytes, content check: pass/fail)
- If any expected file is missing or empty, the task MUST NOT be marked DONE.

## API Permission Check

If this task touches API endpoints, record:
- Permission model checked: yes/no/N/A
- Field filtering verified: yes/no/N/A
- Tenant isolation confirmed: yes/no/N/A

If no API changes: "N/A: no API changes in this task."

## Secret And Safety Check

Security Check items:
- Secrets added or exposed: yes/no
- Raw model output persisted: yes/no
- Production data or credentials used in prompts: yes/no
- Trust boundary violations: yes/no
- Unauthorized tenant access: yes/no
- AI permission gateway bypass: yes/no

## Gate Evidence

Record which gates were run and their results:

```text
gate command and output (exit code, pass/fail summary)
```

Frontend/UI tasks cannot be marked DONE with only grep, syntax, file-existence,
or scope-diff evidence. They must include a passing Playwright/browser
acceptance run with the five-layer checks (L1 environment, L2 network, L3
console, L4 DOM, and L5 persistence when applicable), or the task must be
marked BLOCKED with the exact environment/scenario blocker.

## Verification Self-Assessment

- Diff inspected: yes/no
- Scope checked programmatically (scope_diff_gate.py): yes/no
- Receipt claims contradicted by diff: yes/no

## Memory Promotion Decisions

For each governance file, either promote content or explain why not:

- project-memory.md: (promoted content or "no promotion needed: reason")
- decision-log.md: (promoted content or "no promotion needed: reason")
- risk-register.md: (promoted content or "no promotion needed: reason")
- skill-candidates.md: (promoted content or "no promotion needed: reason")

## Deviations From Brief

- None, or list each deviation with reason.

## Assumptions

- None, or list assumptions needing confirmation.

## Blockers

- None, or list the minimum decision needed.
- If blocked, propose the evaluator/checker/gate repair that would catch this
  blocker earlier next time.

## Next-Task Prediction

What should the next similar task observe to prove this work was correct:

- (concrete prediction about future behavior)
