# Rolling Epic Planning

## Goal

Use a hybrid harness plan: register a stable epic contract and structured backlog once, then generate the next task from current evidence instead of pre-writing every task brief.

## Design

The harness keeps three layers:

1. Epic contract: durable goal, design references, acceptance items, and forbidden changes.
2. Backlog skeleton: structured candidate items with acceptance binding, scope hints, dependencies, and verification hints.
3. Rolling task spec: one generated JSON spec for `new_task_brief.py --SpecFile`, selected from the contract, backlog, current task states, and prior gate evidence.

The rolling planner is deterministic and local. It should not call an LLM. It chooses the first pending backlog item whose dependencies are complete. If no structured backlog exists, it falls back to pending acceptance items. If the prior round failed, the task writer may still create a bounded repair, but the repair must remain inside the active epic and acceptance item.

## Files

- `scripts/register_epic.py`: write both `backlog.md` and `backlog.json`.
- `scripts/rolling_task_planner.py`: compile contract/backlog/current task evidence into a compact task spec JSON.
- `scripts/auto_harness_loop.py`: expose planner output in task-writer prompts and support dry-run planner preview.
- `checks/programmatic_harness_selftest.py`: assert the planner/generator path exists.
- `tests/accept_harness_python.py`: focused unit coverage for planner behavior.

## Acceptance

- Registering an epic with backlog items writes a structured `backlog.json`.
- Planner emits a valid `new_task_brief.py --SpecFile` JSON object for the first pending unblocked backlog item.
- Planner skips backlog items whose dependencies are incomplete.
- Generated tasks contain `## Epic Alignment` and pass `epic_alignment_gate.py`.
- Auto harness dry-run logs the rolling planner command/path instead of relying only on free-form task writer reasoning.
