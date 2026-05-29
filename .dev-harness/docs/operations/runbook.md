# Development Runbook

This is the default workflow for AI-assisted development in this repository.

## 0. Orient

DEFAULT_HARNESS_ACTIVE
TOKEN_BOUNDED_CONTEXT

Default harness activation: for every non-trivial development task in this
repository, use this runbook even when the user does not mention `.dev-harness`.
Do not wait for an explicit harness request. Skip only for clearly
self-contained chat, pure Q&A, trivial formatting/translation, or explicit user
instruction not to touch files or not to use the harness. If skipped, record or
state the reason briefly.

Start with the bounded context entrypoint before reading long harness history:

```powershell
harness-engine/.dev-harness/scripts/harness_context_summary.py
```

Do not orient by reading every file under `task-briefs/`, `reviews/`,
`execution-receipts/`, or `harness-engine/.dev-harness/**/*.md`. Read the
selected latest task, its same-number receipt/review, and at most the latest
same-stream predecessor unless a gate failure names more files.

Read:

- `AGENT.MD`
- `docs/strategy-overview.md`
- `docs/event-library-mvp.md`
- `docs/rust-development-policy.md`
- `harness-engine/.dev-harness/docs/policies/strategy-development-guide.md`
- `harness-engine/.dev-harness/memory/project-memory.md`
- `harness-engine/.dev-harness/memory/active-context.md`
- `harness-engine/.dev-harness/docs/governance/project-map.md`
- `harness-engine/.dev-harness/docs/operations/roadmap.md`
- `harness-engine/.dev-harness/docs/policies/tool-policy.md`
- `harness-engine/.dev-harness/docs/operations/eval-protocol.md`
- `harness-engine/.dev-harness/docs/protocols/self-evolution-protocol.md`
- `harness-engine/.dev-harness/docs/policies/openai-policy.md`

Then identify:

- target layer;
- risk class;
- authority order and any instruction conflict;
- likely files to change;
- verification path;
- Rust crate or module ownership, when production code is involved;
- event type, labels, cost model, time split, and leakage checks, when strategy logic is involved.

## 1. Plan

For non-trivial work, create or update a task brief:

```text
harness-engine/.dev-harness/task-briefs/NNN-YYYY-MM-DD-short-name.md
```

The brief must include non-goals. Non-goals are the main guardrail against
direction drift.

### Dual-Model Workflow

Use this repo-local workflow when the user wants to save tokens by splitting
planning and implementation across models:

- Codex/GPT acts as architect and memory promoter.
- GLM/Claude or another lower-cost model acts as implementer (with self-verification).
- `brainstorm` is used only for high-uncertainty or high-blast-radius design
  choices, not routine implementation.
- `.dev-harness` is the shared control plane. Do not maintain separate
  long-lived GPT and GLM project documents.
- Code, tests, docs, decision logs, risk registers, Git history, and verified
  artifacts remain the long-term source of truth.

The architect creates a narrow task brief before implementation. The brief must
include allowed files or paths, forbidden changes, non-goals, acceptance
criteria, verification commands, stop conditions, and the expected receipt
format.

The implementer receives the task brief plus the minimum code context needed
for the task. The implementer executes the task, then self-verifies: runs
`scope_diff_gate.py`, checks acceptance criteria, verifies scope, records gate
evidence, and makes memory promotion decisions — all recorded in the expanded
execution receipt. If the brief is ambiguous or requires files outside scope,
the implementer must stop and return a blocker.

### Short Command Task Queue

SHORT_COMMAND_TASK_QUEUE

The user may drive the dual-model flow with only two prompts:

```text
GPT/Codex: дtask
GLM/Claude: ִ��task
```

When GPT/Codex receives `дtask`, it acts as architect. It must read the current
user goal and harness context, then create or update one scoped task brief under
`task-briefs/`. The brief must include `Task Status: UNCLAIMED`, allowed files,
forbidden files, non-goals, observable acceptance criteria, verification
commands, and stop conditions. GPT/Codex should not paste long role
instructions into chat; durable instructions belong in this harness.

PREVIOUS_TASK_ACCEPTANCE_GATE

Before writing a new `UNCLAIMED` task, GPT/Codex must accept or reject the
previous completed task. Use the latest task brief marked `DONE` or `BLOCKED`,
then inspect its execution receipt, review artifact, actual diff, and gate
evidence. If those artifacts are missing or inconsistent with the task status,
write or request the missing review first and do not create the next task. The
new task brief must include a `Previous Task Acceptance` section that records:

```text
previous_task:
previous_status:
review_artifact:
receipt_artifact:
verdict:
gate_evidence:
residual_risks:
impact_on_this_task:
```

When GLM/Claude receives `ִ��task`, it acts as bounded implementer. It must
find the latest task brief whose `Task Status` is `UNCLAIMED`, claim it by
changing status to `CLAIMED`, record implementer and claimed time, then execute
only that brief. On completion it changes status to `DONE` or `BLOCKED` and
returns an execution receipt. If no unclaimed task exists, or the latest
unclaimed task is missing scope or verification fields, return a blocker.

Task selection rule:

```text
latest unclaimed = newest file by date/name under task-briefs/
                   with "Task Status: UNCLAIMED"
```

Do not claim a task marked `CLAIMED`, `DONE`, or `BLOCKED` unless GPT/Codex
explicitly reopens it by setting `Task Status: UNCLAIMED` with a note.

Use brainstorm only when at least one trigger is present:

- new architecture boundary;
- public API or data model change;
- new dependency, platform, or security-sensitive path;
- strategy validation rule with meaningful blast radius;
- multiple plausible designs with unresolved tradeoffs;
- repeated failure where the harness rule itself may be wrong.

Skip brainstorm for routine bug fixes, small tests, already-approved ADR
execution, documentation cleanup, and mechanical refactors with clear
acceptance criteria.
### Continuous Auto Loop

AUTO_HARNESS_LOOP

Use `harness-engine/.dev-harness/scripts/auto_harness_loop.py` when the user wants uninterrupted task writing and execution.

The automation loop follows the same authority order as the manual dual-model workflow, with additional operational rules:

- State is repository-local at `automation/auto_state.json`.
- Role and provider settings live in `automation/agent-config.json`, created from `automation/agent-config.example.json`. Store real API keys outside the repository when possible; the example config names environment variables.
- `task_writer` attempts Codex CLI first. If the health check fails, it falls back to the configured Claude/GLM writer role.
- `implementer` may execute the generated task without human confirmation.
- The loop creates or reuses one `codex/auto-harness-YYYYMMDD-HHMMSS` branch only after preflight succeeds.
- `.claude/` is local runtime state. Auto-harness status collection, scope gates, review drafts, preflight repair, and automatic commits must exclude `.claude/` paths. Manual edits to tracked Claude commands or skills are outside the automation loop and require explicit human direction.
- Existing dirty workspace changes outside `.claude/` are handled by a preflight AI pass. It may modify those dirty changes, must run a light gate, and must commit a preflight preservation commit before the automation branch is created. If it finds dangerous deletion, secrets, merge conflicts, or unclear cross-project changes outside `.claude/`, it records `BLOCKED_PRECHECK` and stops.
- Every round commits locally, including failed or blocked rounds. Default behavior is no push; `-AutoPush` is explicit opt-in.
- Every round stores raw model stream logs and summary logs under `automation/logs/`. Raw AI output is evidence only and must not be promoted to durable memory without reviewer judgment.
- Light gate runs every round. Full gate runs every configured N rounds and on the final round.
- In-round repair attempts are bounded; default is two attempts. If still failing, the failed round is committed and the next task brief must scope the repair.

## 2. Implement

Keep edits inside scope.

If implementation reveals a larger design issue, update the brief or stop. Do
not silently expand scope.

## 3. Verify

Use the smallest check set that matches the risk class:

- `LOW`: document/file existence checks plus review.
- `MEDIUM`: dev gate fast mode plus targeted Rust tests when relevant.
- `HIGH`: full dev gate plus targeted integration or smoke tests.
- `BLOCKED_WITHOUT_APPROVAL`: do not implement before explicit user approval.

## 4. Review

Use `harness-engine/.dev-harness/templates/review-template.md`.

The reviewer must check:

- instruction hierarchy violations;
- incomplete execution trace;
- logic placed in the wrong layer;
- trust-boundary breaks;
- missing rollback path;
- happy-path-only evals;
- implicit changes to runtime facts;
- new non-Rust product logic;
- confusion between price trigger and strategy event class;
- future leakage, random splits, duplicated samples, or missing trading costs;
- OpenAI API compliance.

## 5. Self-Evolve

Use `harness-engine/.dev-harness/docs/protocols/self-evolution-protocol.md`.

For every partial, failed, risky, or reworked task, answer before closing:

```text
Why did the harness fail to constrain this?
```

Then decide whether the fix belongs in:

- `templates/review-template.md`;
- `docs/operations/runbook.md`;
- `docs/operations/eval-protocol.md`;
- `checks/dev_gate.py`;
- `memory/project-memory.md`;
- `docs/governance/decision-log.md`;
- `docs/governance/risk-register.md`;
- a task-specific review under `reviews/`.

Do not promote a new harness rule without a prediction contract and a validation
signal. Every promoted rule must include its rationale, when it applies, and
when it should not apply.

If a task failed or needed rework, repair the evaluator before closing:

```text
Which check, template, memory, workflow, or policy should have caught this?
```

## 6. Close The Task

Before final response, create a task closure packet:

1. Complete the expanded execution receipt under `execution-receipts/` (or inline in the task brief) with all verification fields: scope independent check, acceptance verification, security check, gate evidence, memory promotion decisions, next-task prediction.
2. Append the session fact to `memory/session-log.md`.
3. Promote durable lessons to `memory/project-memory.md` only when they have clear trigger conditions.
4. Add reusable procedure candidates to `memory/skill-candidates.md` when the lesson looks like a future skill, but keep it as `candidate` until replayed.
5. Add architecture decisions or risks only when they affect future design or repeated failure modes.
6. Run `checks/dev_gate.py -SkipRust -Fast` for docs/harness-only work, or the stronger gate required by the risk class.

The closure packet must make a concrete prediction about the next similar task.
Example:

```text
Next time a task modifies harness workflow rules, dev-gate should fail if the
runbook, review template, and self-evolution protocol drift out of sync.
```

## 7. Memorize

Update:

- `memory/session-log.md`: what happened in this session;
- `memory/project-memory.md`: durable lessons with trigger conditions;
- `memory/skill-candidates.md`: reusable procedures that may later become skills;
- `docs/governance/decision-log.md`: long-term architecture decisions;
- `docs/governance/risk-register.md`: repeated or newly discovered risks.

Do not store secrets, raw model outputs, large diffs, or unsupported claims.

## 8. Stop

Stop when:

- the task is implemented and verified;
- the task is blocked by required approval;
- the task brief is proven wrong;
- verification exposes a deeper architecture issue.

## Phase 1 Memory Gate Addendum

For memory-affecting work, `checks/memory_gate.py` is part of the closure path and runs through `checks/dev_gate.py`. It rebuilds `memory/indexes/memory-manifest.json`, `retrieval-index.json`, `memory-index.md`, and `stale-report.md` from Markdown sources. Generated indexes are retrieval aids, not authority; agents must follow links back to source Markdown before acting on memory.

## Task Stream Scoped Acceptance Addendum

Task Stream is required for every new task brief. `PREVIOUS_TASK_ACCEPTANCE_GATE` applies to the latest completed or blocked task in the same Task Stream, not to the numerically latest task across the whole repository.

This prevents unrelated streams from blocking each other. Example: a `harness-write-task-governance` task does not inherit acceptance from an in-progress `structure-proof` task unless the new brief explicitly depends on that business task.

When writing a task, record:

- Task Stream
- Same-stream previous task
- why cross-stream tasks are or are not relevant

Run `checks/write_task_gate.py -TaskBrief <path>` for new task briefs that change task creation, queueing, or harness governance.

## Review And Scientific Verdict Gate

REVIEW_SCIENTIFIC_VERDICT_GATE

Execution receipts are evidence, not review authority. A file under `reviews/`
must contain the standard review sections, including `Verdict`, `Verification`,
and `Scientific Verdict` when the task touches research proof, validation,
model scoring, event labels, or strategy claims.

Separate these values explicitly:

```text
execution_verdict = did the task run and stay in scope?
research_verdict  = did the hypothesis/proof/data claim pass?
promotion_allowed = may later tasks consume this as proof?
blocked_claims    = claims future tasks must not make
```

If a task uses proxy metrics, incomplete feature recomputation, or a
surrogate/null-world test fails, promotion must remain blocked until a later
task explicitly repairs that gate or changes the event definition.

Task closure should run `checks/write_task_gate.py` for the current task brief
and `checks/review_gate.py` for review structure. `dev_gate.py` also runs
these checks for the latest task/review in fast harness validation.
### Programmatic Harness Generation

PROGRAMMATIC_HARNESS_GENERATION
TOKEN_BOUNDED_CONTEXT

Prefer programmatic generation for predictable harness artifacts. The AI should provide parameters and judgement, while scripts generate stable structure and derive facts from the repository.

Default tools:

- `harness-engine/.dev-harness/scripts/harness_context_summary.py`: prints a small, latest-N context summary so agents avoid broad directory reads.
- `harness-engine/.dev-harness/scripts/new_task_brief.py`: creates numbered task brief skeletons with status, stream, previous same-stream acceptance, scope contract, verification, and stop conditions.
- `harness-engine/.dev-harness/scripts/new_task_brief.py --SpecFile <path>`: creates the same brief from a bounded JSON spec, preferred when title, scope, criteria, or commands would otherwise create a long shell-quoted invocation.
- `harness-engine/.dev-harness/scripts/new_review_draft.py`: creates review drafts from a task brief, changed files, and gate result. Prefer `--Task <NNN>` for numbered tasks so the script resolves the full task path.
- `harness-engine/.dev-harness/checks/scope_diff_gate.py`: verifies changed files against the task brief's `Allowed files or paths`.

Use free-form AI writing only for fields that require judgement: intent, non-goals, acceptance meaning, findings, verdicts, residual risks, scientific interpretation, and memory promotion decisions.

Do not encode long JSON, long Markdown, or many repeated list options directly in Bash or PowerShell. Write a temporary JSON spec with a file edit tool, call `new_task_brief.py --SpecFile <path>`, then remove the temporary spec if it is not meant to be tracked.
