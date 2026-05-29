# Harness Scripts

This directory contains deterministic helpers used by the repo-local harness.

## Register And Run An Epic

Use `register-epic.ps1` when a large requirement and design are ready. The
script creates the Program Harness Epic files:

- `goal.md`
- `design.md`
- `backlog.md`
- `contract.json`

Example:

```powershell
harness-engine/.dev-harness/scripts/register-epic.ps1 `
  -EpicId epic-my-big-requirement `
  -Title "My Big Requirement" `
  -Goal "Describe the durable goal here." `
  -DesignPaths @(
    "docs/your-design.md",
    "docs/your-acceptance.md"
  ) `
  -BacklogItems @(
    "Current-state audit",
    "Implement next smallest slice",
    "Run verification",
    "Write final verdict"
  ) `
  -AcceptanceItems @(
    "A1|Summarize current state and identify next executable task.",
    "A2|Implement or repair the next report or gate.",
    "A3|Run verification and record gate evidence.",
    "A4|Write final verdict separating engineering PASS from domain verdict."
  ) `
  -ForbiddenChanges @(
    "Do not modify unrelated product code.",
    "Do not weaken acceptance criteria."
  )
```

Then run the loop:

```powershell
harness-engine/.dev-harness/scripts/auto-harness-loop.ps1 `
  -MaxIterations 1 `
  -FullGateEvery 2 `
  -EpicRoot harness-engine/.dev-harness/automation/epics/epic-my-big-requirement `
  -BranchName codex/auto-harness-my-big-requirement
```

The loop reads the Epic goal, design, backlog, and contract; generates a small
task brief; checks Epic alignment; executes it; runs gates; writes logs; and
commits each round locally.

## Script Index

- `register-epic.ps1`: Create portable Epic files from a large requirement and
  design references.
- `auto-harness-loop.ps1`: Run the automated task writer, implementer, reviewer,
  gate, log, and commit loop.
- `new-task-brief.ps1`: Deterministically generate a numbered task brief.
- `new-review-draft.ps1`: Deterministically generate a review draft.

Default behavior is local-only: no push unless explicitly requested through the
loop command.
