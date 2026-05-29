# Auto Harness Automation

This directory contains the repo-local state and reusable configuration for the
automatic harness loop.

The loop is intentionally repository-local:

- each repository owns its own `auto_state.json`;
- long-running work can be grouped into epics through `program-state.json` and
  an epic `contract.json`;
- each run creates or reuses one `codex/auto-harness-YYYYMMDD-HHMMSS` branch;
- every round is committed locally, including failed rounds;
- remote push is disabled unless explicitly requested;
- full AI run logs are stored under `automation/logs/`.
- `.claude/` is treated as local runtime state and is excluded from
  auto-harness status collection, scope gates, review drafts, preflight repair,
  and automatic commits.

## Files

- `agent-config.example.json`: portable role/provider template. Copy it to
  `agent-config.json` and fill provider environment variable names, values, or
  per-provider header fields for the local machine. Do not commit real API
  keys.
- Agent calls are not time-limited unless a role or `defaults` sets a positive
  `timeout_seconds` / `agent_timeout_seconds` value.
- `auto_state.example.json`: state schema reference. The script creates
  `auto_state.json` when it runs.
- `program-state.example.json`: portable Program Harness state schema for
  running multiple large requirements/design specs as queued epics.
- `epic-contract.example.json`: reusable Epic Contract schema. Each task brief
  produced inside an epic must bind to one acceptance item.
- `logs/`: per-run replayable AI session evidence. Raw streams are evidence,
  and rendered console logs are for human review.

## Log Layout

Each script start creates one run directory:

```text
logs/run-YYYYMMDD-HHMMSS-WPID/
  console.log
  latest.txt
  round-001/
    console.log
    task_writer/
      console.log
    implementer/
      console.log
```

Directory-level console logs are the review path:

- `run-*/console.log`: loop control flow, command/gate output, and pointers to
  role logs. It does not duplicate full role transcripts.
- `round-*/console.log`: command/gate output that is unique to that round. It is
  omitted when the round has no unique command output.
- `round-*/<role>/console.log`: complete terminal-style log for that role
  across all phases in the round.

The log tree intentionally keeps only `console.log` files plus `latest.txt`.
There are no `call-*` folders and no sidecar prompt, stream, summary, or
metadata files. If one role runs multiple phases, such as `main` and
`repair-1`, those phases are appended into the same role `console.log` with a
`phase=` header.

`latest.txt` points at the latest role directory during a running loop.

Preflight output is written into the run-level `console.log`; it does not create
an extra `round-000-*` directory. Programmatic self-tests write their run
directories under `.dev-harness/tmp/` or an explicit `-LogRootOverride`, so
running gates does not pollute the human-facing `automation/logs/` history.

## Default Flow

1. Preflight dirty workspace handling outside `.claude/`.
2. Create or reuse `codex/auto-harness-YYYYMMDD-HHMMSS`.
3. If an epic is active, load its goal, design, backlog, and contract.
4. Write task brief with the `task_writer` role, using the configured GPT
   planner/reviewer provider and process-local env injection. Provider
   injection clears conflicting OpenAI/Anthropic model variables from previous
   role calls, mirrors the selected provider into Claude CLI's `ANTHROPIC_*`
   env/settings, and passes `--model` from `agent-config.json` so role config
   wins over user-level Claude defaults.
5. Run the epic alignment gate when an epic contract is present.
6. Execute task with the `implementer` role, using the configured GLM executor
   provider and process-local env injection.
7. Run light gate every round, and full gate every `FullGateEvery` rounds or on
   the final round.
8. On failed verification, retry repair inside the current round up to
   `MaxFixAttempts`.
9. Append gate output into the same round and run `console.log` files.
10. Commit the round result, even when failed or blocked.
11. Continue immediately until `MaxIterations` is reached.

Manual edits to tracked `.claude/commands` or `.claude/skills` remain possible,
but they are not part of automatic harness cleanup or commit behavior.

## Example

```powershell
harness-engine/.dev-harness/scripts/auto_harness_loop.py -MaxIterations 5
```

Epic-driven loop:

```powershell
harness-engine/.dev-harness/scripts/auto_harness_loop.py `
  -MaxIterations 5 `
  -EpicRoot harness-engine/.dev-harness/automation/epics/epic-example
```

```powershell
harness-engine/.dev-harness/scripts/auto_harness_loop.py `
  -MaxIterations 5 `
  -FullGateEvery 2 `
  -EpicRoot harness-engine/.dev-harness/automation/epics/epic-event-collection-structure-proof `
  -BranchName codex/auto-harness-event-collection
```

Use `-AutoPush` only when remote updates are explicitly desired.
