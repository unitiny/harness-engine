# Decision Log

持久化开发决策记录。当选择影响架构、工作流、信任边界或长期维护时追加条目。

## 2026-05-11: Create Project And Dev Harness

Decision: 创建 Historical Event Trajectory Model 项目，包含 `docs/`、`harness-engine/`（内含 `.dev-harness/`）。Dev harness 包含 OpenAI 集成策略。

Reason:
- 历史事件轨迹建模是一套独立的策略系统。
- 需要开发 harness 来指导 AI 辅助开发。
- OpenAI API 集成是核心能力，需要专门的策略文档。

Consequences:
- 开发 agent 必须在非平凡开发前读取 `.dev-harness/` 记忆和配置。
- OpenAI API 使用必须遵循 `docs/policies/openai-policy.md`。
- 运行时权威保留在核心引擎，LLM 输出是 candidate。
- 本 harness 不得替代引擎作为建模、评分或状态更新的权威。

## 2026-05-11: MVP Strategy Is Long Crowding Exhaustion

Decision: 第一版历史事件库聚焦 `long_crowding_exhaustion`，即 Binance USDT 永续山寨币暴涨后，多头拥挤、主动买盘衰竭、价格无法继续创新高的做空路径验证。

Reason:
- 泛化的“暴涨后首次转弱”只是价格事件，容易混入上币、新闻、meme、板块轮动、短挤压、庄盘拉升等不同博弈结构。
- 多头拥挤衰竭具有更清晰的资金行为解释，且可先用公开市场数据快速落地。
- 窄场景能更快验证策略是否有真实 edge，避免过早加入新闻、社媒、链上或复杂模型。

Consequences:
- 策略实现必须先区分 price trigger 和 game-structure classification。
- 历史匹配必须优先在同类事件库内完成。
- 回测必须包含无未来函数、时间切分、cooldown、first-hit 标签、费用滑点、资金费率、流动性和 MAE/MFE 检查。
- 模型输出只能是 candidate alert，不能直接成为实盘交易指令。

## 2026-05-11: Product Code Must Be Rust

Decision: Historical Event Trajectory Model 的生产代码统一使用 Rust。数据接入、事件检测、特征、标签、相似度匹配、回测、评分、CLI 和 OpenAI runtime 集成默认都必须由 Rust 实现。

Reason:
- 策略系统需要强类型、可复现、可测试、性能稳定的核心路径。
- 多语言脚本容易绕过核心引擎边界，制造隐性评分权威和难以追踪的数据处理差异。
- Rust/Cargo workspace 更适合把核心域逻辑、数据层、回测层和 CLI 边界拆清楚。

Consequences:
- 新增非 Rust 产品逻辑需要用户明确批准。
- Dev harness 可保留 PowerShell 作为 Windows 本地检查启动器，但不得承载策略逻辑。
- 验证门禁默认使用 Cargo fmt、clippy、test；docs-only 任务可以只跑文档门禁。

## 2026-05-15: Non-Trivial Tasks Require A Closure Packet

Decision: 非平凡 AI 开发任务结束前必须调用 `.dev-harness` 收尾：写 review、追加 session log、决定 project memory、决定 skill candidate、记录验证证据，并给出下一次同类任务的可观察预测。

Reason:
- 只靠最终聊天总结不能让下一次 agent 可靠恢复经验。
- OpenAI agent/eval 实践强调 trace、eval evidence 和 repeatable checks；Reflexion、Generative Agents、Voyager 等研究也都把反馈、记忆或技能库接回后续行为，而不是停在文字反思。
- 本项目需要把这些模式限制在项目边界内，避免未经验证的经验直接变成全局技能或运行时策略权威。

Consequences:
- `memory/skill-candidates.md` 成为可复用流程候选池。
- `dev-gate.ps1` 检查 closure 相关规则是否仍存在。
- 未来非平凡任务 review 必须填写 `Task Closure Packet`。
- 如果 closure packet 变得噪声过大，应通过 review 调整字段，而不是跳过收尾。

## 2026-05-15: Dual-Model Development Uses `.dev-harness` As Shared Control Plane

Decision: 当用户用高配模型指挥、低配模型执行来节省 token 时，采用 Codex/GPT architect-reviewer 和 GLM/Claude bounded implementer 的不对称流程。`.dev-harness` 是唯一共享控制面；不维护 GPT 和 GLM 各自一份长期项目文档。

Reason:
- 多模型各自维护长期文档会产生上下文漂移，后续 agent 难以判断哪个事实有效。
- 低成本 implementer 的价值在于执行窄任务，不在于重新设计架构、晋升记忆或改写方向。
- 可验收的 task brief、execution receipt、review、gate 和 decision/risk/memory promotion 比保存完整辩论或长聊天记录更可靠。

Consequences:
- `docs/operations/runbook.md` 明确 dual-model workflow 和 brainstorm 触发条件。
- `templates/task-template.md` 要求 scope contract、acceptance criteria 和 receipt。
- `templates/execution-receipt-template.md` 成为 implementer 交付格式。
- `templates/review-template.md` 要求 reviewer 做 diff-vs-receipt、scope、verification、secret 和 memory-promotion 检查。
- Implementer 输出只能作为 evidence；长期记忆、决策和风险只能由 architect/reviewer 验收后晋升。

## 2026-05-15: Short Commands Drive The Dual-Model Task Queue

Decision: 将用户侧双模型提示压缩为两个短命令：GPT/Codex 收到 `写task` 时创建或更新最新 task brief 并标记 `Task Status: UNCLAIMED`；GLM/Claude 收到 `执行task` 时自动领取最新未领取 task brief，标记 `CLAIMED`，按 scope 执行后标记 `DONE` 或 `BLOCKED` 并返回 execution receipt。

Reason:
- 用户不应反复复制长角色提示；稳定规则应沉淀在 `.dev-harness`。
- `task-briefs/` 已经是 scoped work 的共享目录，适合作为轻量任务队列。
- 显式 status 字段比聊天上下文更容易 review、恢复和防止两个 implementer 同时执行同一任务。

Consequences:
- `templates/task-template.md` 必须保留 `Task Status` 字段。
- Implementer prompt 必须支持 `执行task` 自动领取最新 `UNCLAIMED` 任务。
- Review 必须记录 task status transition。
- 这仍是人工/agent 驱动队列，不引入后台服务或自动调度器。
- `写task` 创建下一张任务前必须先验收上一张最新 `DONE` 或 `BLOCKED` 任务；新任务必须记录 `Previous Task Acceptance`，否则容易脱离上一个实现结果制定计划。
# 2026-05-18: Pivot Structure-Proof Research Toward Microstructure Alignment

Decision:

- Do not continue price-only `long_crowding_exhaustion` detector repair as the
  primary route after V1/V2/V3 surrogate failures.
- Treat the current event library as descriptive/research-only.
- Next development should first test derivatives/microstructure alignment:
  price pump plus OI, funding, taker-flow, basis, long/short, liquidation or
  depth state.
- The next proof design should use a V4 cross-variable surrogate that preserves
  price dynamics while destroying the temporal alignment between price and
  derivatives mechanism variables.

Rationale:

- V1 return-bucket surrogate reproduced the mechanism direction rate.
- V2 symbol-return buckets became sparse/single-class and did not repair the
  finding.
- V3 FFT/IAAFT surrogate reproduced the post-pump return proxy.
- Brainstorm consensus ranked derivatives/microstructure alignment above
  further price-only detector work.

Consequences:

- No TP/SL, backtest, alerting, or live-trading task may use the current
  price-only structure-proof result as authorization.
- Negative-control labels may be auxiliary only; they cannot rescue the S2
  surrogate failure.
- The next task should be data feasibility and V4 surrogate design.

# 2026-05-18: Enforce Review And Scientific Verdict Separation

Decision:

- Add `checks/review-gate.ps1`.
- Run latest-task `write-task-gate.ps1` and `review-gate.ps1` from
  `dev-gate.ps1`.
- Require reviews to separate execution verdict from research/scientific
  verdict.

Rationale:

- Task 040 showed that a receipt-like review can lack standard `Verdict` and
  `Verification` sections.
- Structure-proof tasks can execute successfully while their scientific result
  is negative.

Consequences:

- Future latest reviews must include `Scientific Verdict` fields.
- Proxy metrics or incomplete feature recomputation must block promotion unless
  a later task repairs the gate or narrows the claim.
- `dev-gate` can fail even when file hygiene passes if latest task closure is
  incomplete.

# 2026-05-18: Microstructure 30-Day Pilot GO With Public Data

Decision:

- A 30-day top-50 USDT perpetual altcoin pilot is feasible using Binance
  public REST endpoints only.
- Klines (5m) provide taker buy volume with full history.
- Funding rate has full history at native funding interval (1h/4h/8h).
- OI history, taker ratio, L/S ratios, and basis are limited to 30 days / 1
  month and must be collected continuously for multi-year use.
- Liquidation REST endpoint is deprecated; use OI drop + funding spike proxy.
- Depth/order book is snapshot-only; no historical data.

Consequences:

- V4 pilot implementation task can proceed with public data only.
- Continuous collection of 30-day-limited endpoints should start immediately.
- Multi-year proof requires either accumulated continuous collection or paid data.
- No trading authorization is implied by data availability.

# 2026-05-18: Pre-Register V4 Cross-Variable Surrogate Before Implementation

Decision:

- V4 null model is pre-registered: preserve price path, circular-shift each
  derivatives variable independently per symbol with random offset >= 24 bars.
- Primary metric: mean_downside_mfe_8h.
- Significance gate: p <= 0.01, MDE >= 30 bps, bootstrap CI > 0, symbol
  robustness >= 60%.
- Four verdict values: V4_DATA_BLOCKED, V4_SURROGATE_FAIL,
  V4_SURROGATE_PASS_RESEARCH_ONLY, V4_SURROGATE_PASS_CANDIDATE.
- Detection rule, symbol universe, and cooldown are frozen before outcome
  inspection.

Consequences:

- The V4 implementation task must use exactly this null and these metrics.
- Any deviation requires a new design doc and review.
- No outcome inspection may occur until the implementation task runs.
- No V4 verdict authorizes live trading.

## 2026-05-19: V4 Surrogate Passes All Gates on Expanded Pilot

Decision: V4 cross-variable surrogate test run against expanded 103-symbol × 45-day offline pilot produces `V4_SURROGATE_PASS_CANDIDATE` verdict.

Reason:
- 461 real events across 96/103 symbols (well above 30 minimum).
- P-value = 0.0020 (1 of 1000 surrogates ≥ real).
- Effect = 46.2 bps > 30 bps MDE threshold.
- Bootstrap 95% CI = [26.1, 69.9] bps (entirely positive).
- Symbol robustness = 100% (96/96 symbols with positive direction).
- All four pre-registered gates pass: p-value, MDE, bootstrap CI, symbol robustness.
- No thresholds were tuned. Detection rule, null model, and statistical gates are frozen.

Consequences:
- Global verdicts `non_random_structure_passed` and `structure_proof_passed_for_research_backtest` remain `false` until independent review confirms no lookahead, correct null construction, valid statistics.
- This is the strongest pre-registered V4 verdict, but it is still RESEARCH_ONLY and NO_TRADE.
- Next step: independent review task must verify implementation before any promotion.
