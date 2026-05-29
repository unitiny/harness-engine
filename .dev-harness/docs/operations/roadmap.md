# Development Roadmap

本路线图是构建 Historical Event Trajectory Model 本身，不是运行时策略。

## P0 Reliability

- 让核心引擎成为稳定、可测试的建模和轨迹预测权威。
- 核心引擎、数据处理、回测、CLI 和 OpenAI runtime 集成全部使用 Rust。
- 保持事件数据加载、缓存行为、评分和状态更新可复现。
- 添加冒烟检查，在运行时产物缺失或格式错误时快速失败。
- 建立端到端事件生命周期：事件数据 -> 提取 -> 建模 -> 轨迹预测 -> 评分 -> 输出。

## P1 Trust And Verification

- 加强验证门禁：数据质量、样本充分性、成本压力、异常处理。
- 改进结果 schema，让失败可保留且机器可读。
- 确保每个模型版本有足够上下文复现决策。
- 接受标准从"最佳评分"转向证据支撑：样本充分性、时间稳定性、成本压力、鲁棒性。

## P2 Developer Velocity

- 维护 `harness-engine/.dev-harness/` 记忆，让 AI agent 不重复发现同一架构。
- 添加聚焦的 dev gate：Rust/Cargo 检查、配置校验、引擎冒烟测试。
- 保持 task brief 小而 scoped、可 review。
- 先用半自动开发：task brief、scoped 实现、dev gate、review、记忆更新。
- 在核心生命周期骨架有测试和确定性验收门禁后，再加入全自动化循环。

## P3 OpenAI Integration

- 建立统一的 OpenAI API 客户端模块。
- Prompt 版本化管理，所有 prompt 文件 git tracked。
- 结构化输出（JSON mode / function calling）优先。
- 实现 token 消耗追踪和预算控制。
- 为关键路径准备 fallback：规则引擎、本地模型、缓存结果。
- 建立 prompt 变更的 review 流程。

## P4 Observability

- 从本地 JSONL trace 开始。
- 记录模型决策、API 调用、评分质量、衰减/淘汰决策。
- 考虑外部可观测性平台仅在本地 trace 不够时。

## Development Track

### D0: Development Rail

- 保持 `harness-engine/.dev-harness/` 作为半自动工程轨道。
- 每个非平凡任务需要 brief、non-goals、验证路径、review、记忆更新。
- 不允许自动编码 agent 不经 task brief 和 stop conditions 就做广泛架构变更。

### D1: Minimal Event Lifecycle Skeleton

- 创建 Cargo workspace 和 Rust crate 边界。
- 定义事件数据 schema。
- 实现或 stub：
  - `EventDataLoader`
  - `EventExtractor`（OpenAI 集成）
  - `TrajectoryModel`
  - `PredictionEngine`
  - `ScoringEngine`
  - `ValidationGate`
  - `OutputLedger`
- 运行一个手工事件通过完整生命周期：

```text
event data -> extraction -> modeling -> trajectory prediction
  -> scoring -> validation report -> output record
```

### D2: OpenAI Integration Layer

- Rust 统一 API 客户端，支持重试、rate limit、token 追踪。
- Prompt 模板管理。
- 结构化输出解析。
- Fallback 策略。
- API 调用审计日志。

### D3: Validation And Quality

- 数据质量检查。
- 预测准确度验证。
- 异常检测和鲁棒性测试。
- OpenAI prompt 质量评估。

### D4: Controlled Automation

- 仅对窄范围、可测试的任务添加自动化循环。
- 允许的自动化任务示例：
  - 实现 prompt 模板加载器
  - 添加一个验证 metric
  - 添加评分 breakdown 字段
  - 添加冒烟测试
- 需要明确批准才能自动化的任务：
  - 重设计架构
  - 绕过验证门禁
  - 修改 OpenAI prompt 策略
  - 变更数据完整性保证

## Current Direction

优先：事件生命周期骨架、可靠性、验证门禁和 OpenAI 集成层，再做 UI、仪表盘、云部署、全自动化循环或新 agent 平台。

技术栈优先级：

- 全部产品代码使用 Rust。
- 新代码优先组织为 Cargo workspace。
- 非 Rust 仅允许文档、配置、prompt、数据和 dev-harness wrapper。

策略研究优先级：

- 先建立 `long_crowding_exhaustion` 历史事件库。
- 先用公开市场数据验证窄场景：5m K 线、成交额、taker buy ratio、资金费率、BTC/ETH 同步性和板块同步性。
- 先做同类事件 kNN 轨迹匹配和 first-hit 回测。
- 在窄场景没有样本外正期望前，不扩展到新闻、社媒、链上、多事件大分类或复杂模型。
