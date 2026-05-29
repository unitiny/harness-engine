# Project Map

本文件告诉 AI 开发 agent 变更应该放在哪里。

## System Layers

- `constitution/`: L3 不可变规则、反作弊策略、验收门禁。仅在用户明确批准后修改。
- `meta/`: L2 改进运行时 harness 自身的元控制层。
- `harness-engine/`: L1 运行时策略引擎、OpenAI 集成、编排逻辑。
- `harness-engine/.dev-harness/`: 开发 harness，指导本项目开发。
- `docs/`: 设计、需求、实现笔记、研究笔记。
- `AGENT.MD`: 项目级 agent 指南，记录策略核心和开发边界。
- `docs/rust-development-policy.md`: Rust-only 产品代码政策。
- `crates/`: Rust workspace 的默认生产代码位置（创建代码时优先使用）。
- `data/`: 历史事件数据、轨迹数据、模型输出。只读事实，不可随意修改。

## Placement Rules

- 事件建模、轨迹预测、评分逻辑属于 `harness-engine/` 核心引擎。
- 新增生产代码默认使用 Rust 和 Cargo workspace；优先放在 `crates/`。
- 策略思路、MVP 事件库、研究假设属于 `docs/` 和 `AGENT.MD`。
- 策略开发流程护栏属于 `harness-engine/.dev-harness/docs/policies/strategy-development-guide.md`。
- OpenAI API 调用、prompt 管理、agent 编排属于 `harness-engine/`。
- 运行时编排脚本、配置中心属于 `harness-engine/`。
- Meta-optimization 属于 `meta/`。
- 反作弊规则和验收门禁属于 `constitution/`。
- 开发流程、项目记忆、架构护栏属于 `harness-engine/.dev-harness/`。

## Agent Loop Roles

这些是开发角色，不是常驻服务：

- Architect：决定层级、信任边界、最小设计。
- Implementer：实现 scope 内变更。
- Test Engineer：选择聚焦的验证方式。
- Reviewer：检查 bug、架构漂移、反作弊问题、缺失的测试。

小任务默认一个 agent/角色。仅在任务足够大、独立 review 有价值时拆分角色。

## Risk Classes

- LOW：文档、注释、prompt 措辞、非权威辅助脚本。
- MEDIUM：运行时 harness 脚本、配置默认值、非核心引擎辅助。
- HIGH：引擎核心逻辑、数据加载、评分、模型训练、OpenAI prompt chain。
- BLOCKED_WITHOUT_APPROVAL：L3 规则放松、删除事实结果、修改历史数据、为提升性能而弱化成本或惩罚。

## Do Not

- 不要让策略生成 agent 编辑引擎规则、评分权重或历史结果。
- 不要把价格触发器当成最终博弈事件分类。
- 不要将不同暴涨原因混入一个历史匹配池后直接下结论。
- 不要删除失败版本或覆写事实输出来让进度看起来更好。
- 不要混合开发 harness 规则与运行时策略规则。
- 不要在 Rust/Cargo 和现有 PowerShell dev-harness wrapper 能处理时引入新框架。
- 不要新增 Python/JavaScript/TypeScript/notebook 等非 Rust 产品逻辑，除非用户明确批准。
- 不要把 eval 通过当作模型预测能力的证明；eval 通过只代表工程变更满足门禁。

## Development Preference

使用最小可靠机制：

1. Rust 核心引擎代码保证正确性。
2. Cargo workspace 管理生产 crate。
3. PowerShell 只做本地 dev-harness 启动器，不承载策略逻辑。
3. Markdown 和 JSON 做持久化 AI 记忆。
4. 仅在本地机制证明不足后才引入外部平台。
5. OpenAI API 调用必须遵循 `docs/policies/openai-policy.md`。
