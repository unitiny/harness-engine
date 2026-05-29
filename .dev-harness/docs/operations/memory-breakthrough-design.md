# Harness Memory Breakthrough Design

Date: 2026-05-27
Status: design proposal

## Problem

The current harness has memory directories, generated indexes, and a memory gate, but it is still mostly a passive archive. Agents can record memory decisions in receipts, yet there is no strong loop that:

- extracts reusable memories from execution evidence;
- promotes or rejects candidates through review;
- retrieves only the right memories before task generation;
- detects stale or harmful memories;
- measures whether memory improved future runs.

The result is predictable: agents either ignore memory, over-read broad Markdown, or repeat stale lessons.

## Research Synthesis

Useful patterns from recent memory-agent work:

- MemGPT: treat context as virtual memory with fast and slow tiers, and move information between tiers deliberately.
- Generative Agents and Reflexion: convert raw events and task feedback into higher-level reflections before reuse.
- Voyager: store executable skills and reuse them through environment feedback and self-verification.
- A-MEM: memory should be structured and linked, closer to Zettelkasten than an append-only log.
- MemoryAgentBench and MemBench: memory must be evaluated on retrieval accuracy, long-range understanding, update behavior, efficiency, and forgetting.
- MemOS: memory should be governed like an OS resource, with lifecycle, scheduling, versioning, and operators.

For this harness, the breakthrough is not "add vector DB". The breakthrough is a Memory Control Plane that makes memory write, retrieval, promotion, decay, and replay measurable.

## Proposed Architecture: Memory Control Plane

```text
task execution evidence
  -> memory candidate extractor
  -> typed memory ledger
  -> promotion/rejection gate
  -> retrieval compiler
  -> context pack for planner/task_writer/implementer
  -> memory replay eval
  -> stale/supersede operator
```

## Memory Types

Use typed memory because different memory types have different authority.

1. `fact`: stable repo fact, such as canonical task directories.
2. `constraint`: rule that must be obeyed, such as no cloud vector store by default.
3. `decision`: architectural choice with rollback trigger.
4. `lesson`: reusable failure pattern and prevention rule.
5. `skill_candidate`: repeatable workflow not yet promoted to a global skill.
6. `risk`: known recurring failure mode with detector.
7. `trace`: per-task execution evidence; not injected by default.
8. `context_pack`: generated hot memory bundle for one task; disposable.

## Storage Layout

Keep Markdown as authority and generated indexes as cache.

```text
memory/
  active/
    active-context.md
    context-packs/
      latest.json
      task-NNN.json
  canon/
    facts/YYYY-MM.md
    constraints/YYYY-MM.md
    decisions/YYYY-MM.md
    lessons/YYYY-MM.md
    risks/YYYY-MM.md
    skill-candidates/YYYY-MM.md
  traces/YYYY-MM/NNN-task-slug.md
  indexes/
    memory-manifest.json
    retrieval-index.json
    memory-graph.json
    stale-report.md
    replay-report.md
  cache/
    fts/
    embeddings/
```

## Memory Item Schema

Every promoted memory block must be addressable and testable.

```yaml
id: mem-20260527-short-slug
type: fact | constraint | decision | lesson | risk | skill_candidate
status: candidate | active | superseded | rejected | archived
scope:
  paths: []
  task_streams: []
  run_types: []
trigger:
  when_to_retrieve:
  when_not_to_retrieve:
evidence:
  receipts: []
  reviews: []
  logs: []
assertion:
  summary:
  prevention_rule:
  expected_signal:
lifecycle:
  created_at:
  expires_at:
  supersedes: []
  confidence: low | medium | high
```

## Core Components

### 1. Memory Candidate Extractor

Script: `scripts/memory_candidate_extractor.py`

Input:

- latest task brief;
- execution receipt;
- review;
- gate output;
- meta-harness findings.

Output:

- `memory/canon/*` candidate blocks or `memory/active/context-packs/candidate.json`;
- never promotes directly to active memory.

Rules:

- raw logs are evidence links, not memory text;
- only extract repeated failures, durable constraints, validated decisions, or reusable workflows;
- every candidate must include `when_to_retrieve` and `expected_signal`.

### 2. Memory Promotion Gate

Script: `checks/memory_promotion_gate.py`

Purpose:

- reject memory without evidence;
- reject broad memories with no path/task scope;
- reject "always do X" memories without `when_not_to_retrieve`;
- reject candidate promotion if it conflicts with newer code/gate evidence.

This makes memory less like notes and more like a tested rule system.

### 3. Retrieval Compiler

Script: `scripts/build_context_pack.py`

Input:

- task spec or task brief;
- changed path intent;
- active epic contract;
- latest same-stream predecessor;
- retrieval-index and memory-graph.

Output:

```json
{
  "task": "NNN or planned spec",
  "budget": {"max_items": 8, "max_chars": 6000},
  "included": [
    {"id": "mem-...", "why": "path match + task stream + active status"}
  ],
  "excluded": [
    {"id": "mem-...", "why": "superseded or wrong stream"}
  ],
  "context_text": "bounded hot context"
}
```

Retrieval ranking:

```text
hard constraint match
> same task stream
> same path/module
> same failure class
> fresh active context
> lexical match
> optional semantic cache
```

### 4. Memory Graph

Generated file: `memory/indexes/memory-graph.json`

Edges:

- `supersedes`
- `caused_by`
- `prevents`
- `applies_to_path`
- `observed_in_task`
- `validated_by_gate`

The graph is not for fancy visualization. It lets the gate answer: "why did this memory appear in context, and what evidence supports it?"

### 5. Memory Replay Eval

Script: `checks/memory_replay.py`

Replay recent tasks with a known expected memory set:

- If task touches `auto_harness_loop.py`, retrieval must include loop/provider/routing constraints.
- If task touches acceptance gate, retrieval must include product-vs-harness failure routing lessons.
- If task touches memory, retrieval must include anti-bloat and schema constraints.

Metrics:

- required_recall: required memories retrieved / required memories;
- stale_precision: stale or superseded memories retrieved / all retrieved;
- context_budget_chars;
- repair_repeat_rate: whether a previously memorized failure reappeared.

Promotion rule:

- memory changes are accepted only if replay recall improves or stale retrieval does not regress.

### 6. Stale/Supersede Operator

Script: `scripts/memory_lifecycle.py`

Actions:

- mark expired candidates as rejected;
- mark conflicting old lessons as superseded;
- archive trace summaries older than N tasks;
- produce `stale-report.md` with exact reasons.

Do not delete memory silently. Supersede it.

## Integration With Rolling Epic Planner

The rolling task planner should consume a context pack, not raw memory.

```text
rolling_task_planner.py
  -> build_context_pack.py --TaskSpec next-task.json
  -> append bounded memory_context to planner spec
  -> new_task_brief.py --SpecFile
```

The implementer prompt should receive:

- task brief;
- compact context pack;
- no broad memory scans.

## Breakthrough Features

### Memory As Code

Memory entries behave like code:

- typed schema;
- evidence links;
- gates;
- replay tests;
- version/supersede chain.

### Negative Memory

Store what not to retrieve. Each memory item has `when_not_to_retrieve`. This prevents stale broad lessons from poisoning unrelated tasks.

### Prediction-Backed Memory

Each promoted memory must say what observable signal should improve. Example:

```text
expected_signal: future task_writer runs use --SpecFile and have fewer shell quoting failures
```

Meta-harness can later verify whether this happened.

### Two-Key Promotion

Memory becomes active only when both are true:

1. candidate appears in receipt/review evidence;
2. memory promotion gate validates schema, scope, and replay behavior.

### Hot Context Budget

No agent reads memory directly by default. Agents read generated context packs capped by item count and character budget.

## Implementation Phases

### Phase 1: Context Pack MVP

- Add `scripts/build_context_pack.py`.
- Add schema parsing for current compat memory files and typed canon files.
- Add retrieval by path, task stream, and keywords.
- Emit `memory/active/context-packs/latest.json`.
- Wire `auto_harness_loop.py` task_writer and implementer prompts to mention context pack path.

Acceptance:

- a task touching `auto_harness_loop.py` retrieves the known auto-loop memories;
- context pack stays under 6 KB;
- stale/superseded memory is excluded.

### Phase 2: Promotion Gate

- Add `checks/memory_promotion_gate.py`.
- Extend receipt/review closure to write memory candidates.
- Gate candidate schema, evidence, scope, and anti-bloat rules.

Acceptance:

- candidate without evidence fails;
- candidate without `when_not_to_retrieve` fails;
- valid candidate passes and appears in retrieval index.

### Phase 3: Replay Eval

- Add `checks/memory_replay.py`.
- Define 5-10 local replay fixtures from real harness tasks.
- Add metrics to `memory/indexes/replay-report.md`.

Acceptance:

- replay checks required recall and stale precision;
- memory changes that degrade replay fail fast gate.

### Phase 4: Optional FTS, No Vector By Default

- Add SQLite FTS5 only if lexical metadata misses real memories.
- Add vector cache only after replay proves benefit.
- Markdown remains authority.

## Rejection Criteria

Reject this design if:

- memory gate becomes slower than normal fast dev gate budget;
- agents start reading broad memory files again;
- replay shows stale memories increase wrong repairs;
- vector cache becomes authoritative instead of rebuildable.

## Sources

- MemGPT: https://arxiv.org/abs/2310.08560
- Generative Agents: https://arxiv.org/abs/2304.03442
- Reflexion: https://arxiv.org/abs/2303.11366
- Voyager: https://arxiv.org/abs/2305.16291
- A-MEM: https://arxiv.org/abs/2502.12110
- MemoryAgentBench: https://arxiv.org/abs/2507.05257
- MemBench: https://arxiv.org/abs/2506.21605
- MemOS: https://arxiv.org/abs/2507.03724
