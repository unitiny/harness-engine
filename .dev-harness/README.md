# Historical Event Trajectory Model — Dev Harness

`.dev-harness/` 是开发本项目本身的控制层，位于 `harness-engine/` 下。
它与运行时策略引擎分离。

三个核心原则：

- 先构建最小可靠 agent loop，再增加多 agent 复杂度。
- 每次运行有清晰目标、工具边界、验证门禁和停止条件。
- 把 eval 和 memory 当作一等项目资产，而非事后补充。
- 生产代码全用 Rust；PowerShell 只作为 dev-harness 启动器。

## Purpose

- 保持开发与系统架构一致。
- 跨 AI session 保留项目记忆。
- 非平凡变更必须经过 brief、实现、验证、review 循环。
- 默认启用 harness：用户不需要主动提 `.dev-harness`，非平凡开发也必须先读并使用本目录。
- 支持高配模型 architect/reviewer 与低配模型 bounded implementer 的双模型开发流。
- 减少架构漂移、重复工作、方向错误。
- 让失败可追溯，避免未来 agent 重复踩坑。

## Directory Map

```text
harness-engine/.dev-harness/
├── README.md
├── checks/
│   └── dev_gate.py
├── docs/
│   ├── document-governance.md
│   ├── governance/
│   │   ├── project-map.md
│   │   ├── decision-log.md
│   │   └── risk-register.md
│   ├── operations/
│   │   ├── roadmap.md
│   │   ├── runbook.md
│   │   ├── eval-protocol.md
│   │   └── phase-0-acceptance.md
│   ├── policies/
│   │   ├── tool-policy.md
│   │   ├── strategy-development-guide.md
│   │   └── openai-policy.md
│   └── protocols/
│       └── self-evolution-protocol.md
├── memory/
│   ├── memory-schema.md
│   ├── project-memory.md
│   ├── active-context.md
│   └── session-log.md
├── prompts/
│   ├── architect.md
│   ├── implementer.md
│   ├── reviewer.md
│   └── test-engineer.md
├── scripts/
│   └── auto_harness_loop.py
├── automation/
│   ├── README.md
│   ├── agent-config.example.json
│   ├── auto_state.example.json
│   └── logs/
├── task-briefs/
├── reviews/
└── templates/
    ├── task-template.md
    ├── execution-receipt-template.md
    └── review-template.md
```

## Required Loop

DEFAULT_HARNESS_ACTIVE

Default activation rule: this loop applies automatically to every non-trivial
development task in the repository, even when the user does not mention
`.dev-harness`. Skip only for clearly self-contained chat, pure Q&A, trivial
formatting/translation, or explicit user instruction not to touch files or not
to use the harness.

1. 读项目文档：`AGENT.MD`、`docs/strategy-overview.md`、`docs/event-library-mvp.md`、`docs/rust-development-policy.md`。
2. 读 harness 文档：`docs/policies/strategy-development-guide.md`、`memory/project-memory.md`、`memory/active-context.md`、`docs/governance/project-map.md`、`docs/operations/roadmap.md`、`docs/policies/tool-policy.md`、`docs/operations/eval-protocol.md`。
3. 分类任务：docs-only、local-code、engine-critical、harness-runtime、meta、runtime-artifact。
4. 按 `docs/document-governance.md` 判定文档归属，不得把任务文档、草稿、review、实现计划直接放到 `.dev-harness` 根目录。
5. 按 `templates/task-template.md` 创建或更新 task brief。
6. 仅实现 scope 内变更。
7. 如果使用低配模型实现，必须让 implementer 按 `templates/execution-receipt-template.md` 返回 execution receipt。
8. 按 `templates/review-template.md` review diff、scope、verification、secret 和 memory promotion。
9. 运行 `checks/write_task_gate.py`、`checks/review_gate.py` 和
   `checks/dev_gate.py`，或说明无法运行的原因。
10. 将结果写入 `memory/session-log.md`。
11. 持久化架构决策写入 `docs/governance/decision-log.md`。

## Dual-Model Workflow

当用户为了节省 token 而拆分模型角色时：

- Codex/GPT 是 architect 和 memory promoter。
- GLM/Claude 或其他低成本模型是 implementer（含自验证）。
- `.dev-harness` 是唯一共享控制面；不要维护 GPT 和 GLM 各自一份长期项目文档。
- Implementer 接收 task brief、最小代码上下文和扩展版 receipt 模板。
- Implementer 负责自验证：运行 scope_diff_gate、检查验收标准、记录 gate evidence、做内存晋升决策。
- Receipt 是完整的验证记录，包含开发交付和自验证证据。
- 对研究/策略验证任务，代理指标、surrogate/null-world 失败、未完整重算特征等情况必须阻止 promotion，
  除非后续任务明确修复该 gate 或重定义事件。

### Programmatic Harness Generation

PROGRAMMATIC_HARNESS_GENERATION
TOKEN_BOUNDED_CONTEXT

To save tokens without weakening execution quality, agents should prefer
programmatic harness file generation over free-form long Markdown when the
artifact is structurally predictable.

- Use `scripts/harness_context_summary.py` before broad exploration. It lists
  the latest small set of task briefs, reviews, execution receipts, generator
  tools, and working-tree status.
- Use `scripts/new_task_brief.py` to generate task brief skeletons from
  parameters such as title, task stream, scope, acceptance criteria, and
  verification commands.
- Use `scripts/new_review_draft.py` to generate review drafts from the task
  brief, changed files, and gate evidence.
- Use `checks/scope_diff_gate.py` to compare actual changed files against the
  task brief's `Allowed files or paths` before trusting receipt or review text.
- AI should fill judgement fields: goal wording, non-goals, acceptance meaning,
  findings, verdict, residual risk, and promotion decision. Scripts should fill
  numbering, paths, status scaffolding, diff facts, and repeated boilerplate.
- Do not orient by reading every Markdown file under `task-briefs/`, `reviews/`,
  `execution-receipts/`, or all of `.dev-harness`. Read only the selected latest
  task, its same-number receipt/review, and necessary same-stream predecessor
  unless a gate failure names more files.

### Auto Harness Loop

AUTO_HARNESS_LOOP

`scripts/auto_harness_loop.py` is the repository-local automation entrypoint
for continuous dual-model harness execution.

Default behavior:

- Preflight existing dirty workspace changes before creating the automation
  branch. The preflight agent may repair existing uncommitted changes, then it
  must run a light gate and create a preflight commit. Dangerous changes become
  `BLOCKED_PRECHECK`.
- Create or reuse one `codex/auto-harness-YYYYMMDD-HHMMSS` branch after
  preflight succeeds.
- Store state in `automation/auto_state.json` and raw/summary AI logs in
  `automation/logs/`.
- Use role-based model configuration from `automation/agent-config.json`; the
  task-writer role should try Codex first and fall back to Claude/GLM when the
  Codex CLI health check fails.
- Let the implementer role execute the generated task automatically.
- Run a light gate every round, and a full gate every configured N rounds or on
  the final round.
- Try in-round repair at most two times by default. If verification still
  fails, commit the failed round and let the next `写task` create a repair task.
- Commit every round locally, including `FAILED`, `BLOCKED`, and preflight
  commits. Do not push unless `-AutoPush` is explicitly provided.

Raw model output must remain in automation logs. Promote only reviewed facts,
decisions, risks, or reusable procedures through the normal memory and review
process.

#### Example: Running the Event-Collection Microstructure Feasibility Epic

```powershell
# Standard run — 3 iterations, full gate every 2 rounds, local-only (no push)
python harness-engine/.dev-harness/scripts/auto_harness_loop.py --MaxIterations 3 --EpicId epic-event-collection-microstructure-feasibility --EpicRoot harness-engine/.dev-harness/automation/epics/epic-event-collection-microstructure-feasibility --BranchName codex/auto-harness-event-collection --FullGateEvery 2

# Dry-run — preview what the loop would do without executing
python harness-engine/.dev-harness/scripts/auto_harness_loop.py --DryRun --MaxIterations 1 --EpicId epic-event-collection-microstructure-feasibility --EpicRoot harness-engine/.dev-harness/automation/epics/epic-event-collection-microstructure-feasibility --BranchName codex/auto-harness-event-collection

# Preflight only — check workspace cleanliness before starting
python harness-engine/.dev-harness/scripts/auto_harness_loop.py --PreflightOnly --EpicId epic-event-collection-microstructure-feasibility --EpicRoot harness-engine/.dev-harness/automation/epics/epic-event-collection-microstructure-feasibility --BranchName codex/auto-harness-event-collection

# Single round with light gate only (fast iteration)
python harness-engine/.dev-harness/scripts/auto_harness_loop.py --MaxIterations 1 --LightGateOnly --EpicId epic-event-collection-microstructure-feasibility --EpicRoot harness-engine/.dev-harness/automation/epics/epic-event-collection-microstructure-feasibility --BranchName codex/auto-harness-event-collection
```

### Short Command Task Queue

SHORT_COMMAND_TASK_QUEUE

用户可用极短提示驱动双模型工作流：

```text
GPT/Codex: 写task
GLM/Claude: 执行task
```

`写task` 表示 architect/reviewer 读取当前目标和 harness 上下文，创建或更新
`task-briefs/` 下最新的 scoped task brief，并把 `Task Status` 设为
`UNCLAIMED`。除非用户另有说明，GPT 不应把完整长提示交给 implementer；长规则
沉淀在 `.dev-harness`。

PREVIOUS_TASK_ACCEPTANCE_GATE

在创建下一张 `UNCLAIMED` task brief 前，`写task` 必须先检查上一张最新
`DONE` 或 `BLOCKED` 的 task brief：读取其 execution receipt、review artifact、
实际 diff 和 gate evidence。若上一任务没有 review 或 receipt，或者验收结果与
状态不一致，先补验收或返回 blocker，而不是继续写下一张任务。下一张 task brief
必须包含 `Previous Task Acceptance` 小节，说明上一任务 verdict、证据路径、残余风险
和它如何影响本任务 scope。

`执行task` 表示 bounded implementer 自动领取最新 `Task Status: UNCLAIMED`
的 task brief。领取时必须把状态更新为 `CLAIMED`，记录 implementer、claimed_at
和 allowed scope；完成后把状态更新为 `DONE` 或 `BLOCKED`，并按
`templates/execution-receipt-template.md` 返回 receipt。

如果没有未领取任务，或最新未领取任务缺少 allowed files、acceptance criteria、
verification command、stop conditions，implementer 必须停止并返回 blocker。

Brainstorm 只用于高风险或高不确定决策：架构边界、公开 API 或数据模型、新依赖、安全敏感路径、策略验证规则、多个方案难以取舍、重复失败说明 harness 规则可能有问题。日常 bug、小测试、机械重构和已确认方案执行应跳过 brainstorm。

## Task Closure Packet

每次非平凡任务结束前必须显式调用一次 harness 收尾，而不是只在最终回复里口头总结。

收尾包最少包含：

- review：按 `templates/review-template.md` 在 `reviews/` 记录 execution trace、验证结果、自进化判断和残余风险。
- memory：按 `memory/memory-schema.md` 判断是否更新 `session-log.md`、`project-memory.md`、`active-context.md`、`decision-log.md` 或 `risk-register.md`。
- review gate：运行 `checks/review_gate.py`，确保最新 review 不是单纯
  receipt，且包含 scientific verdict、blocked claims 和 proxy metric
  limitations。
- skill candidate：如果本次任务产生了可复用操作模式、检查器模式、调试流程或 prompt/tool 习惯，先写入 `memory/skill-candidates.md`，不得直接升级成全局 skill。
- eval evidence：记录运行过的 gate、测试、人工检查或为什么无法运行。
- dual-model evidence：如果用了 implementer，记录 task brief、execution receipt、实际 diff scope、reviewer 复验结果和 memory promotion 决策。

收尾时必须回答：

```text
本次任务有什么可复用经验？
它应该沉淀为 project memory、skill candidate、checker、template、runbook 规则，还是不沉淀？
下次同类任务可观察到什么行为变化，证明沉淀有效？
```

## Stop Conditions

遇到以下情况必须停下来询问用户：

- 任务需要修改不可变规则（constitution 层）。
- 验证失败暗示架构误解而非简单 bug。
- 实现需要引入新平台或长运行服务。
- 实现需要新增非 Rust 产品代码。
- 变更会影响历史事件数据的完整性或可复现性。
- 变更会把价格触发器当成最终博弈事件，或把不同暴涨原因混入同一个匹配池。
- 变更会弱化无未来函数、时间切分、费用滑点、流动性或 first-hit 标签检查。
- OpenAI API 使用超出 `docs/policies/openai-policy.md` 规定范围。

## Quick-Reference: Running Commands

All commands are run from the **repository root** directory. Single-line format for direct paste into PowerShell.

### Scripts

```powershell
# ── Automated harness loop (main entrypoint) ──
python harness-engine/.dev-harness/scripts/auto_harness_loop.py --MaxIterations 3 --EpicId <epic-id> --EpicRoot harness-engine/.dev-harness/automation/epics/<epic-id> --BranchName codex/auto-harness-<name> --FullGateEvery 2

# Dry-run only (no execution, just plan)
python harness-engine/.dev-harness/scripts/auto_harness_loop.py --DryRun --MaxIterations 1 --EpicId <epic-id> --EpicRoot harness-engine/.dev-harness/automation/epics/<epic-id> --BranchName codex/auto-harness-<name>

# Preflight check only (verify workspace cleanliness)
python harness-engine/.dev-harness/scripts/auto_harness_loop.py --PreflightOnly --EpicId <epic-id> --EpicRoot harness-engine/.dev-harness/automation/epics/<epic-id> --BranchName codex/auto-harness-<name>

# ── Register a new Epic ──
python harness-engine/.dev-harness/scripts/register_epic.py --EpicId <epic-id> --Title "Epic Title" --Goal "Goal description" --DesignPaths "[\"docs/design.md\"]" --BacklogItems "[\"Step 1\", \"Step 2\"]" --AcceptanceItems "[\"A1|Acceptance criterion 1\"]" --ForbiddenChanges "[\"Do not modify X\"]" --OutputRoot harness-engine/.dev-harness/automation/epics/<epic-id>

# ── Generate a task brief ──
python harness-engine/.dev-harness/scripts/new_task_brief.py --Title "Task title" --TaskStream <stream> --RunType <run-type> --Layer <layer> --RiskClass <risk-class> --Intent "One-line intent" --Goal "Goal description" --AcceptanceCriteria "[\"AC1\", \"AC2\"]" --VerificationCommands "[\"python harness-engine/.dev-harness/checks/dev_gate.py --Fast\"]"

# ── Generate a review draft ──
python harness-engine/.dev-harness/scripts/new_review_draft.py --TaskBrief harness-engine/.dev-harness/task-briefs/NNN-slug.md --ChangedFiles "[\"path/to/file1.py\"]" --GateCommand "python harness-engine/.dev-harness/checks/dev_gate.py --Fast" --GateResult "PASS"

# ── Summarize current harness context ──
python harness-engine/.dev-harness/scripts/harness_context_summary.py
python harness-engine/.dev-harness/scripts/harness_context_summary.py --RecentTasks 5 --TaskStream <stream>
```

### Checks / Gates

```powershell
# ── Dev gate (main quality gate) ──
python harness-engine/.dev-harness/checks/dev_gate.py                         # full check
python harness-engine/.dev-harness/checks/dev_gate.py --Fast                  # fast mode
python harness-engine/.dev-harness/checks/dev_gate.py --SkipRust              # skip Rust-specific checks
python harness-engine/.dev-harness/checks/dev_gate.py --SkipEngine            # skip engine checks

# ── Write-task gate (validate a task brief) ──
python harness-engine/.dev-harness/checks/write_task_gate.py --TaskBrief harness-engine/.dev-harness/task-briefs/NNN-slug.md

# ── Review gate (validate a review) ──
python harness-engine/.dev-harness/checks/review_gate.py --Review harness-engine/.dev-harness/reviews/NNN-slug.md
python harness-engine/.dev-harness/checks/review_gate.py --AllLatestStreams

# ── Scope diff gate (check changed files vs task brief scope) ──
python harness-engine/.dev-harness/checks/scope_diff_gate.py --TaskBrief harness-engine/.dev-harness/task-briefs/NNN-slug.md --ChangedFiles "[\"path/to/file1.py\", \"path/to/file2.py\"]"
python harness-engine/.dev-harness/checks/scope_diff_gate.py --TaskBrief harness-engine/.dev-harness/task-briefs/NNN-slug.md --ReportOnly

# ── Memory gate ──
python harness-engine/.dev-harness/checks/memory_gate.py
python harness-engine/.dev-harness/checks/memory_gate.py --Fast

# ── Epic alignment gate ──
python harness-engine/.dev-harness/checks/epic_alignment_gate.py --TaskBrief harness-engine/.dev-harness/task-briefs/NNN-slug.md --EpicContract harness-engine/.dev-harness/automation/epics/<epic-id>/contract.json

# ── Build memory index ──
python harness-engine/.dev-harness/checks/build_memory_index.py
python harness-engine/.dev-harness/checks/build_memory_index.py --Fast

# ── Programmatic harness self-test ──
python harness-engine/.dev-harness/checks/programmatic_harness_selftest.py
python harness-engine/.dev-harness/checks/programmatic_harness_selftest.py --KeepTemp
```

### Tests / Acceptance

```powershell
# ── Harness Python acceptance test ──
python harness-engine/.dev-harness/tests/accept_harness_python.py
python harness-engine/.dev-harness/tests/accept_harness_python.py --skip-full-dev-gate
python harness-engine/.dev-harness/tests/accept_harness_python.py --skip-meta-pipeline
```

### Typical Workflow Sequence

```powershell
# 1. Check current context
python harness-engine/.dev-harness/scripts/harness_context_summary.py

# 2. Register an epic (once)
python harness-engine/.dev-harness/scripts/register_epic.py --EpicId ... --Title ... --Goal ...

# 3. Write a task brief
python harness-engine/.dev-harness/scripts/new_task_brief.py --Title ... --TaskStream ... --RunType ... --Layer ... --RiskClass ... --Intent "..." --Goal "..."

# 3b. For long input, avoid shell quoting waste by using a JSON spec file
python harness-engine/.dev-harness/scripts/new_task_brief.py --SpecFile path/to/task-spec.json

# 4. Validate the task brief
python harness-engine/.dev-harness/checks/write_task_gate.py --TaskBrief harness-engine/.dev-harness/task-briefs/NNN-slug.md

# 5. (Implementer executes task)

# 6. Scope check after changes
python harness-engine/.dev-harness/checks/scope_diff_gate.py --TaskBrief harness-engine/.dev-harness/task-briefs/NNN-slug.md --ChangedFiles "[...]"

# 7. Run dev gate
python harness-engine/.dev-harness/checks/dev_gate.py --Fast

# 8. Generate review draft
python harness-engine/.dev-harness/scripts/new_review_draft.py --TaskBrief harness-engine/.dev-harness/task-briefs/NNN-slug.md --ChangedFiles "[...]"

# 8b. Safer short form for numbered tasks
python harness-engine/.dev-harness/scripts/new_review_draft.py --Task NNN --ChangedFiles "[...]"

# 9. Validate review
python harness-engine/.dev-harness/checks/review_gate.py --Review harness-engine/.dev-harness/reviews/NNN-slug.md

# 10. Run full auto loop (steps 3-9 automated)
python harness-engine/.dev-harness/scripts/auto_harness_loop.py --MaxIterations 3 --EpicId ... --EpicRoot harness-engine/.dev-harness/automation/epics/... --BranchName codex/auto-harness-... --FullGateEvery 2
```

## Boundary

- 本 harness 指导项目开发。
- 不得替代引擎作为事件建模、轨迹预测、评分的权威。
- 不得把 dev harness 文档当作策略回测或交易信号的权威。
- 运行时产物（模型输出、事件数据、轨迹记录）是事实，不是草稿。

WRITE_TASK_ACCEPTANCE_AUDIT

`写task` must perform rigorous acceptance before writing the next task. If the audit finds an error in the previous task, current harness state, evidence, review, gate, numbering, scope, or verification, the new task must include fixing or explicitly blocking on that error as part of its own scope. Do not write a clean follow-on task while leaving known acceptance errors outside the brief.

TASK_STREAM_SCOPED_ACCEPTANCE

Task briefs now use Task Stream scoped acceptance. `Previous Task Acceptance` checks the latest closed task in the same stream. Unrelated streams, such as `structure-proof` and `harness-write-task-governance`, do not block each other unless a brief explicitly declares a dependency.
