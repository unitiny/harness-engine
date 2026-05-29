# Dev Harness Document Governance

`.dev-harness` is a control system, not a loose notes folder. New documents must
be classified before they are created, and the target directory must match the
document's job.

## Root Directory Policy

The `.dev-harness` root is reserved for the single entrypoint document.

Allowed root markdown files:

- `README.md`

Only `README.md` may live at the root. Do not place task notes, stable manuals,
design drafts, implementation plans, ad hoc research, review outputs, or
one-off acceptance notes in the root.

## Directory Ownership

- `docs/governance/`: system map, decisions, risks, and document governance.
- `docs/operations/`: runbooks, roadmaps, eval protocol, and acceptance gates.
- `docs/policies/`: tool, OpenAI, Rust, and strategy-development policies.
- `docs/protocols/`: reusable harness protocols and lifecycle rules.
- `templates/`: reusable task and review templates.
- `task-briefs/`: one file per scoped task, named
  `NNN-YYYY-MM-DD-short-name.md`.
- `reviews/`: review reports, audit notes, and post-implementation findings,
  named `NNN-YYYY-MM-DD-short-name.md` when tied to a task.
- `memory/`: durable project memory, active context, memory schema, and session
  log.
- `memory/active/`: bounded hot context.
- `memory/canon/`: typed durable memory split by decision, constraint, fact,
  lesson, and skill candidate.
- `memory/traces/`: per-task trace records produced by closure packets.
- `memory/archive/`: cold memory excluded from default retrieval.
- `memory/indexes/`: generated manifest and retrieval indexes.
- `memory/cache/`: discardable retrieval accelerators.
- `prompts/`: role prompts used by agents.
- `checks/`: executable harness checks and gate scripts.
- `scripts/`: thin local launchers for harness automation.
- `automation/`: repo-local automation state, role/model config examples, and
  AI run logs. Raw AI logs are evidence artifacts, not durable memory.

Project strategy documentation belongs under the repository-level `docs/`
directory, not under `.dev-harness`, unless the document is explicitly about the
development harness itself.

## Creation Workflow

Before creating a markdown file under `.dev-harness`, answer these questions:

1. Is this a durable harness operating rule?
2. Is this a task-specific brief?
3. Is this a review or audit output?
4. Is this memory or active context?
5. Is this a role prompt?
6. Is this executable check documentation?

If the answer is unclear, default to a `docs/` subdirectory for stable harness
docs or `task-briefs/` for task-scoped work. Do not default to the root.

## Gate Requirement

`checks/dev-gate.ps1` enforces the root markdown whitelist. A new root markdown
file must be moved into the right subdirectory. Expanding the root whitelist is
a governance change and must be recorded in
`docs/governance/decision-log.md`.

`checks/dev-gate.ps1` also enforces numbered task and review artifacts. Files
directly under `task-briefs/` and `reviews/` must start with a three-digit task
sequence prefix, for example `016-2026-05-15-numbered-task-review-artifacts.md`.
Use the same prefix for a task brief and its matching review so agents can find
the task lifecycle by directory sort without a full text search.
