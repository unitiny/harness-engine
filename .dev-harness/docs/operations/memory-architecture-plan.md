# Dev Harness Memory Architecture Plan

Date: 2026-05-15
Status: Phase 1 implemented

## Executive Decision

Do not make a vector database the default memory layer for this repo.

Use a local, Markdown-first, auditable memory system with deterministic indexes.
Add vector search only later as a discardable cache if keyword plus metadata
retrieval fails on real tasks.

The best design for this `.dev-harness` is:

```text
bounded hot context
-> typed canonical memory files
-> generated manifest and indexes
-> cold archive
-> optional local vector/embedding cache
```

## Why This Shape

Research and tool evidence point in the same direction:

- OpenAI Agents tracing treats a run as trace plus spans, including generations,
  tool calls, handoffs, guardrails, and custom events. The harness should keep
  task execution trace separate from durable memory.
- OpenAI graders/evals emphasize explicit grading criteria. Memory quality
  therefore needs checks: retrieval accuracy, freshness, selective forgetting,
  and evidence support.
- MemGPT and Letta-style stateful agents separate in-context memory from
  out-of-context archival or recall memory. The harness should not push all
  memory into the prompt.
- A-MEM supports structured, linked notes with tags and contextual attributes,
  close to a Zettelkasten rather than an append-only chat dump.
- MemoryAgentBench identifies four capabilities for memory agents: accurate
  retrieval, test-time learning, long-range understanding, and selective
  forgetting.
- Experience-following research warns that similar retrieved memories can cause
  agents to repeat previous behavior, including stale or wrong behavior.
- Context-engineering work frames memory as part of a broader context management
  problem, not a pure storage problem.
- Vector search can help semantic retrieval, but dedicated vector stores are not
  automatically warranted for small local corpora.

Local brainstorm consensus:

- GPT argued for Markdown canonical memory, typed directories, deterministic
  indexes, and optional vector cache.
- DeepSeek argued for separate records plus keyword indexes and aggressive
  retention.
- GLM red-teamed both, warning that unbounded "memory" becomes bloat and that
  vector search mostly solves the wrong problem for a small local harness.

Synthesis: use typed directories and bounded batch files, not one giant memory
file and not unlimited one-file-per-observation.

## Proposed Layout

```text
harness-engine/.dev-harness/
  memory/
    README.md
    active/
      active-context.md
      working-set.md
    canon/
      decisions/
        YYYY-MM.md
      constraints/
        YYYY-MM.md
      lessons/
        YYYY-MM.md
      skill-candidates/
        YYYY-MM.md
      facts/
        YYYY-MM.md
    traces/
      YYYY-MM/
        NNN-YYYY-MM-DD-task-slug.md
    archive/
      YYYY/
        YYYY-MM-cold.md
    indexes/
      memory-manifest.json
      memory-index.md
      retrieval-index.json
      stale-report.md
    cache/
      lexical/
      embeddings/
```

Existing files can migrate gradually:

- `active-context.md` -> `memory/active/active-context.md`
- `project-memory.md` -> split into `canon/facts`, `canon/constraints`,
  `canon/lessons`, and `canon/decisions`
- `session-log.md` -> `traces/YYYY-MM/*.md` plus an index
- `skill-candidates.md` -> `canon/skill-candidates/YYYY-MM.md`

Do not perform the migration until a separate implementation task is created.

## File Granularity Rule

Use bounded monthly files per memory type, plus one trace file per task.

Avoid both extremes:

- Bad: one giant `project-memory.md`, because it becomes unreadable and
  over-injected into context.
- Bad: one file per tiny fact forever, because Windows filesystem scans and
  Git diffs become noisy.

Rules:

- Canonical durable memory: one file per type per month.
- Task traces/reviews: one file per task.
- Active context: one bounded file, hard size cap.
- Cold archive: one file per month or year, excluded from default retrieval.
- Generated indexes: machine-generated, disposable, rebuilt by gate.

## Memory Item Schema

Every durable memory item should be a small block:

```yaml
id: mem-YYYYMMDD-short-slug
type: fact | constraint | decision | lesson | skill_candidate | risk
status: active | candidate | superseded | rejected | archived
scope:
  paths: []
  modules: []
  task_types: []
source:
  task: NNN-YYYY-MM-DD-slug
  review: reviews/NNN-YYYY-MM-DD-slug.md
evidence:
  - path_or_url
applies_when:
does_not_apply_when:
expires_at:
supersedes:
summary:
```

Hard limits:

- active context: 4 KB target, 8 KB hard fail
- one memory item: 300 words target, 600 words hard fail
- monthly canonical file: 32 KB warning, 64 KB hard fail
- no raw tool output, secrets, full brainstorm transcript, or large diff

## Retrieval Flow

Before a non-trivial task:

1. Read `AGENT.MD`.
2. Read `.dev-harness/README.md` and runbook.
3. Query `memory/indexes/memory-manifest.json` by task type, path/module,
   status, freshness, and tags.
4. Read only the top linked memory items.
5. If no good hit, read recent task traces for the same scope.
6. If still ambiguous, ask or run targeted search.

Default retrieval should be hybrid lexical plus metadata:

```text
path/module match > task type match > exact keyword > recency > semantic cache
```

Vector retrieval, if added later, is only a tie-breaker. It must return memory
IDs that are re-read from Markdown before use.

## Vector Database Decision

Default: no vector DB.

Add a vector or embedding cache only when all are true:

1. Memory corpus exceeds practical lexical retrieval.
2. At least three real tasks missed relevant memories that keyword/metadata
   indexing should have found.
3. A replay eval shows vector/hybrid retrieval improves recall without adding
   stale or wrong memories.
4. The vector store is local, rebuildable, and non-authoritative.

Recommended future options:

- Phase 1: generated JSON manifest plus ripgrep.
- Phase 2: SQLite FTS5 index, local and rebuildable.
- Phase 3: optional `sqlite-vec` or other local vector extension.

Do not use a cloud vector store for dev harness memory by default.

## Anti-Bloat Lifecycle

On every task closure:

1. Write the task trace/review.
2. Decide whether any memory item deserves promotion.
3. Add only scoped memory with `applies_when` and `does_not_apply_when`.
4. Mark stale items as `superseded` instead of editing history silently.
5. Rebuild manifest/indexes.
6. Gate size limits and broken links.

Weekly or every 10 tasks:

- Compact trace summaries.
- Move cold records to archive.
- Produce `stale-report.md`.
- Reject low-value skill candidates.

## Gate Checks To Add Later

Future implementation should add a dedicated memory gate:

```powershell
harness-engine/.dev-harness/checks/memory_gate.py
```

Checks:

- required directories exist
- memory items follow schema
- no active memory exceeds size caps
- no generated index is stale relative to source files
- no active item lacks evidence
- no active item lacks `applies_when`
- no rejected/superseded item is retrieved by default
- no secrets appear in memory files
- task closure packet links to memory decisions

`dev_gate.py` should call `memory_gate.py` in fast mode once implemented.

## Migration Plan

Phase 0: Design only.

- Keep current files.
- Add this plan.
- Do not migrate memory yet.

Phase 1: Directory skeleton and index.

- Create `memory/active`, `memory/canon`, `memory/traces`,
  `memory/archive`, `memory/indexes`, and `memory/cache`.
- Add `memory-manifest.json` generator.
- Keep old files as compatibility sources.

Implementation status: completed on 2026-05-15.

- Added `checks/build_memory_index.py`.
- Added `checks/memory_gate.py`.
- Added Phase 1 directory skeleton under `memory/`.
- `dev_gate.py` now invokes `memory_gate.py`.
- Generated `memory/indexes/memory-manifest.json`,
  `retrieval-index.json`, `memory-index.md`, and `stale-report.md`.

Phase 2: Split canonical memory.

- Split `project-memory.md` into typed canonical monthly files.
- Keep a pointer file for compatibility.
- Gate size and schema.

Phase 3: Retrieval command.

- Add a local retrieval helper that returns a small context pack for a task.
- Prefer PowerShell wrapper plus Rust implementation only if retrieval becomes
  product-grade logic.

Phase 4: Optional FTS/vector cache.

- Add SQLite FTS5 first.
- Add vector cache only after replay evidence shows need.

## Rejection Criteria

Reject this plan if:

- the user wants a cloud-hosted multi-user memory service;
- the repo grows into a large corpus where local indexes are insufficient;
- vector recall beats lexical/metadata retrieval in replay tests without
  increasing stale-memory failures;
- monthly files cause merge conflicts in real multi-agent use.

## Sources

- OpenAI Agents SDK tracing: https://openai.github.io/openai-agents-python/tracing/
- OpenAI graders: https://developers.openai.com/api/docs/guides/graders
- OpenAI retrieval/vector stores: https://developers.openai.com/api/docs/guides/retrieval
- MemGPT: https://arxiv.org/abs/2310.08560
- Letta stateful agents: https://docs.letta.com/guides/core-concepts/stateful-agents
- A-MEM: https://arxiv.org/abs/2502.12110
- MemoryAgentBench: https://arxiv.org/abs/2507.05257
- Experience-following behavior: https://arxiv.org/abs/2505.16067
- Context Engineering survey: https://arxiv.org/abs/2507.13334
- Lucene vector search: https://arxiv.org/abs/2308.14963
- MemOS: https://arxiv.org/abs/2505.22101
- Contextual Memory Virtualisation: https://arxiv.org/abs/2602.22402
