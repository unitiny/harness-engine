# Risk Register

追踪反复出现的开发风险和必要的缓解措施。

## R1: Runtime And Development Harness Confusion

风险：开发流程规则混入运行时策略引擎逻辑。

缓解措施：
- 保持 `harness-engine/.dev-harness/` 和 `harness-engine/` 运行时代码分离。
- 跨引用必须声明是开发时还是运行时。

## R2: Authority Drift

风险：辅助脚本或 AI 文字成为事实上的评分或状态权威。

缓解措施：
- 核心引擎保持权威。
- Rust 核心代码决定模型状态；PowerShell wrapper 只能启动检查，不能决定最终模型状态。

## R3: Evidence Loss

风险：失败版本、API 错误或差结果被删除以减少噪音。

缓解措施：
- 把运行时输出当作事实证据。
- 仅在用户明确指示并有审计记录时清理。

## R4: Eval Theater

风险：检查通过但不解决实际失败模式。

缓解措施：
- Task brief 必须声明 eval 标准。
- 高风险变更需要至少一个失败路径场景。

## R5: Scope Creep

风险：简单任务变成大规模平台重写。

缓解措施：
- 每个 task brief 有 non-goals 和 stop conditions。
- 新平台或服务需要用户明确批准。

## R6: Encoding Damage

风险：现有中文 Markdown 文件编码损坏，广泛重写可能破坏可恢复内容。

缓解措施：
- 避免重写遗留文档，除非任务专门是编码修复。
- 开发 harness 新增内容优先创建干净的 UTF-8 文档。

## R7: OpenAI API Cost And Reliance

风险：过度依赖 OpenAI API 导致成本失控、rate limit、或停服时系统不可用。

缓解措施：
- 所有 API 调用设置 token 和调用次数上限。
- 关键路径必须有 fallback（规则引擎、本地模型、缓存结果）。
- Prompt 版本 git tracked，变更需要 task brief。
- Token 消耗记入 session-log。

## R8: Price Trigger Mistaken For Game Event

风险：把“暴涨后转弱”当作完整交易事件，忽略上币、新闻、meme、板块轮动、短挤压、流动性操纵等不同原因。

缓解措施：
- 价格异常只能作为 trigger。
- 策略决策必须先分类博弈结构。
- MVP 仅验证 `long_crowding_exhaustion`，其他事件类型先过滤或标记为 non-trade。

## R9: Backtest Leakage And False Edge

风险：使用未来高低点定义事件、随机切分样本、重复计算同一轮暴涨、忽略费用滑点和 first-hit 顺序，导致虚假正期望。

缓解措施：
- 所有 trigger 和 rolling feature 只能使用当前时点之前的数据。
- 使用 walk-forward 或时间切分，不使用随机拆分。
- 同一 symbol 同一轮事件必须有 cooldown。
- 做空评估必须记录 first-hit、MAE、MFE、费用、滑点、资金费率和流动性过滤。

## R10: Non-Rust Product Logic Drift

风险：Python、notebook、shell 或其他脚本语言被用于事件检测、标签、回测或评分，绕过 Rust 核心引擎并形成隐性权威。

缓解措施：
- 生产代码默认只允许 Rust。
- PowerShell 只能作为 dev-harness wrapper。
- Dev gate 检查非 Rust 产品代码。
- 新增非 Rust 产品逻辑必须获得用户明确批准并记录在 decision log。
# 2026-05-18: Risk - Microstructure Data Coverage May Be Too Short

Risk:

- Binance public 5m open-interest, taker buy/sell, and long/short endpoints
  are useful for recent pilots but have limited historical availability through
  public REST endpoints. A serious multi-year structure proof may require paid,
  archived, or third-party derivatives data.

Impact:

- Microstructure V4 proof can be underpowered or limited to a short recent
  sample.

Mitigation:

- Start with a 30-day/top-symbol feasibility matrix before implementation.
- Record symbol coverage, missingness, endpoint limits, and whether paid data is
  required before scanning new events.

# 2026-05-18: Risk - Repackaging Price-Only Mean Reversion As Mechanism

Risk:

- Future tasks may add more thresholds, anchors, or price-shape detectors and
  accidentally recreate the same surrogate-reproducible pattern.

Impact:

- The project could waste cycles on false-positive research and drift toward
  backtest tuning before structure proof.

Mitigation:

- Require pre-registered V4 nulls that preserve price dynamics and destroy only
  proposed mechanism alignment.
- Forbid TP/SL and execution work until `microstructure_alignment_candidate`
  or stronger verdict exists.

# 2026-05-18: Risk - Execution PASS Misread As Scientific PASS

Risk:

- A task can be implemented correctly while the research hypothesis fails, but
  later agents may treat the execution PASS as proof promotion.

Impact:

- Failed structure-proof evidence could be consumed by backtest, strategy, or
  live-trading tasks.

Mitigation:

- `review-gate.ps1` requires a `Scientific Verdict` section with execution
  verdict, research/scientific verdict, promotion allowed, blocked claims, and
  proxy metric limitations.
- `dev-gate.ps1` now runs latest-task `write-task-gate.ps1` and
  `review-gate.ps1`.

# 2026-05-18: Risk - V4 Pilot Event Count May Be Too Low

Risk:

- The pre-registered V4 detection rule requires simultaneous conditions
  (return_4h_z >= 2, oi_delta_4h_z >= 1.5, taker_buy_delta < 0, etc.).
  A 30-day pilot across top-50 symbols may produce fewer than 30 events.

Impact:

- V4 null test would be underpowered or unrunnable.

Mitigation:

- The V4 design includes a V4_DATA_BLOCKED verdict for < 30 events.
- If event count is too low, adjust symbol universe or relax one threshold
  (document the relaxation), but do not weaken the null model.

# 2026-05-18: Risk - Forward-Filling Funding Rate Creates Implicit Step Function

Risk:

- Funding rate events occur at 1h/4h/8h intervals depending on symbol.
  Forward-filling to 5m resolution creates a step function that may not
  capture intra-period funding pressure changes.

Impact:

- Funding-based features may be stale by up to 8 hours, reducing V4
  sensitivity to rapid crowding dynamics.

Mitigation:

- Document forward-fill behavior in V4 design.
- Consider funding rate as a slow-state variable rather than a fast signal.
- If the pilot shows no effect, investigate whether higher-frequency funding
  symbols (1h interval) show stronger results.

## R14: Binance API Domain Blocked From Development Network

Risk: fapi.binance.com and api.binance.com are unreachable from the development
network (TCP connection timeout on port 443). This blocks microstructure pilot
data collection via the `/futures/data/*` analytics endpoints.

Evidence (2026-05-18, task 046):

- DNS resolves: fapi.binance.com -> 108.160.165.9 / 199.59.148.147.
- TCP port 443: connection timeout (15s). SYN packets dropped/filtered.
- ureq errors: "Connection refused" and "os error 10054 (remote host force-closed)".
- api.binance.com: similarly blocked (curl exit code 35).
- data.binance.vision: fully reachable (HTTP 200, AWS CloudFront).

Root cause: firewall/network-level domain blocking (likely GFW on China mainland ISP).

Impact:

- V4 surrogate implementation is blocked until real microstructure rows can be collected.
- Event library, similarity, calibration, and existing structure proofs are unaffected.
- Historical kline/funding data via data.binance.vision remains accessible.

Mitigation:

- Set `HTTPS_PROXY` or `https_proxy` environment variable to a working proxy/VPN that
  can reach `fapi.binance.com:443`. The existing `build_agent()` in `public_data.rs`
  already supports proxy via `ureq::Proxy`.
- Alternatively, run the smoke from a network without domain-level blocking.
- No code changes required for proxy support.

Alternative Path (2026-05-18, task 047):

- data.binance.vision exposes a `metrics` directory with daily 5m-resolution futures
  metrics (OI, LS ratios, taker LS volume ratio) that replaces 3 of 4 blocked fapi
  analytics endpoints.
- Basis can be computed from markPriceKlines and indexPriceKlines (both available).
- All 10 V4 variables are derivable from data.binance.vision-only sources without
  fapi dependency. Historical depth: metrics from 2024-01, klines from 2020-01.
- T+1 delivery (daily zip files) is acceptable for research purposes.
- Risk status: MITIGATED via offline data path. Proxy/VPN no longer required for V4.
