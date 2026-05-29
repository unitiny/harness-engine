# OpenAI API Policy

本文件规定 Historical Event Trajectory Model 项目中 OpenAI API 的使用策略。

## General Principles

- OpenAI API 是工具，不是权威。最终决策权在确定性引擎代码。
- LLM 输出是 `candidate`，必须经过验证门禁才能成为 `approved` 结果。
- 所有 API 调用必须通过统一的客户端模块，不得散落在各处。
- Prompt 模板必须 git tracked，变更需要 task brief 或 commit message。

## API Client Requirements

- 统一入口：所有调用通过 `harness-engine/openai_client/` 或类似模块。
- 重试策略：指数退避，最大 3 次，记录每次重试。
- Rate limit：遵守 OpenAI API 限制，不得暴力突破。
- 超时：每次请求设置合理超时（默认 60s）。
- 错误处理：API 错误必须捕获、记录、不得静默吞掉。

## Token Budget

每次任务必须声明 token 预算：

- 单次调用：max_tokens 在 prompt 模板或配置中指定。
- 单次任务：在 task brief 中声明预计调用次数和 token 总量。
- 单日限制：默认 100,000 tokens/day，可通过配置调整。
- 超预算处理：到达上限后停止调用，记录到 session-log，等待用户确认。

## Model Selection

| 用途 | 推荐模型 | 说明 |
|---|---|---|
| 事件提取 | gpt-4o | 需要高准确度的结构化提取 |
| 轨迹分析 | gpt-4o | 复杂推理任务 |
| 文档/摘要 | gpt-4o-mini | 低成本文本生成 |
| 辅助编码 | gpt-4o | 代码生成和 review |
| 实验性 prompt | gpt-4o-mini | 先用低成本验证 prompt 质量 |

变更模型选择必须记录在 task brief 或配置文件中。

## Structured Output

- 优先使用 JSON mode 或 function calling。
- 自由文本解析仅作为最后手段。
- 输出 schema 必须定义并版本化。
- 解析失败必须记录，不得静默丢弃。

## Prompt Management

- 所有 prompt 模板存储在 `harness-engine/prompts/` 或类似目录。
- Prompt 文件使用 Markdown 或 YAML 格式。
- 变量使用 `{{variable}}` 模板语法。
- Prompt 变更视为代码变更，需要 review。
- 每个 prompt 文件头部注明用途、输入输出、版本。

## Fallback Strategy

关键路径必须有 fallback：

1. OpenAI API 不可用时，尝试规则引擎或本地模型。
2. 结构化提取失败时，使用正则或模式匹配 fallback。
3. 连续 N 次失败后，暂停并通知用户。
4. 缓存成功的 API 结果作为短期 fallback。

## Security

- API key 只通过环境变量或 `.env` 文件传入，不得硬编码。
- `.env` 文件必须在 `.gitignore` 中。
- 不在日志中记录完整 API response 中的敏感内容。
- Prompt injection 防护：用户输入传入前必须 sanitize。

## Cost Tracking

- 每次 API 调用记录：model、prompt_tokens、completion_tokens、cost_estimate。
- 按 task 和 day 汇总。
- 超过日预算时告警。
- 月度汇总写入 session-log。

## Prohibited Uses

- 不得用 OpenAI API 做实盘交易决策。
- 不得在未批准的 prompt 上运行生产数据。
- 不得绕过 token 预算限制。
- 不得将 API key 共享或嵌入到公开仓库。
- 不得用 Agent 主观判断替代引擎评分和验证。
