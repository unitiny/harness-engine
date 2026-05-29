# Eval Protocol

本协议评估项目开发工作，不评估模型预测能力；it does not evaluate model prediction quality.

## Eval Layers

### E0: File And Policy Integrity

检查必需的项目和 harness 文件存在，关键规则可见。

示例：
- `harness-engine/.dev-harness/docs/governance/project-map.md` 存在。
- 项目根 README 或 CLAUDE.md 引用 `.dev-harness`。
- `docs/policies/openai-policy.md` 存在且包含 token 预算规则。

### E1: Formatting And Unit Checks

工程格式检查：

- Rust: `cargo fmt --all -- --check`、`cargo clippy --workspace --all-targets -- -D warnings`、`cargo test --workspace`
- 配置文件 YAML/JSON schema 校验
- Prompt 文件格式检查

### E2: Engine Smoke

仅在运行时引擎行为可能受影响时：

- 引擎 stats 查询
- 定向 `pre-iteration` / `post-iteration` 冒烟测试（使用可丢弃输出）

### E3: Trust Boundary Review

手动或 AI review：

- 评分/建模权威被移出核心引擎
- 数据处理逻辑被弱化
- 运行时产物被覆写
- L3 规则被放松
- 数据泄漏风险
- OpenAI prompt 注入风险
- 非 Rust 产品逻辑是否被新增或成为权威路径

### E4: Regression Scenario

高风险引擎/harness 变更需要定义回归场景：

- 格式错误的状态文件
- 缺失的数据路径
- 失败的模型输出
- API 调用失败
- 事件数据加载失败

### E5: Strategy Research Validity

仅在策略检测、标签、匹配、评分或回测行为受影响时：

- 事件触发不使用未来 K 线。
- rolling feature 只使用历史窗口。
- 同一 symbol 同一轮暴涨有 cooldown。
- 训练/验证/测试使用时间切分或 walk-forward。
- 做空标签检查 first-hit，而不只检查窗口结束收益。
- 费用、滑点、资金费率、流动性、MAE/MFE 被纳入报告。
- 历史匹配限制在同一事件类型内，除非任务明确测试跨类型比较。

## Good Eval Properties

- 足够具体以捕获任务可能引入的失败模式。
- 足够小以频繁运行。
- 难以通过改测试而非修系统来通过。
- 高风险工作至少包含一个负面/失败路径检查。

## Eval Anti-Patterns

- 只检查命令退出成功而忽略输出语义。
- 用 Agent 文字替代引擎输出。
- 运行广泛检查而不说明它们应对什么风险。
- 因为新功能失败就弱化测试数据或规则。
- 把 dev-gate 通过当作模型预测准确度的证明。
