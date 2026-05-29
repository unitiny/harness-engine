# Tool Policy

工具按可能造成的损害分级。

## Low-Risk Tools

默认允许：

- 只读文件搜索和检查。
- `harness-engine/.dev-harness/` 和 `docs/` 内的 Markdown 编辑。
- Rust `cargo fmt --check`、`cargo clippy`、`cargo test`。
- 对现有状态的 stats 查询。

## Medium-Risk Tools

task brief 中指名后允许：

- 编辑 `harness-engine/` 运行时脚本或 prompt。
- 编辑 Rust crate 内的非核心辅助代码。
- 编辑非核心引擎辅助代码。
- 运行构建命令产生 artifact。
- 更新配置默认值。
- OpenAI API 非关键调用（如摘要、文档生成）。

## High-Risk Tools

需要明确 task brief 论证和更强验证：

- 编辑引擎核心建模/预测逻辑。
- 编辑评分、数据处理、状态持久化。
- 编辑事件检测、标签生成、相似度匹配、回测或交易价值评分逻辑。
- 编辑数据缓存行为或事件数据选择。
- 运行修改模型状态的命令。
- OpenAI API 关键调用（如事件提取、轨迹预测 prompt chain）。

## Blocked Without Explicit User Approval

- 放松 `constitution/` 规则。
- 删除失败的模型输出或历史结果。
- 覆写历史事件数据。
- 为提升性能而弱化验证、惩罚或样本范围。
- 为提升回测表现而弱化费用、滑点、流动性、first-hit、MAE/MFE 或无未来函数检查。
- 添加新的外部平台、数据库、队列、web 服务或云依赖。
- 新增非 Rust 产品逻辑，除非用户明确批准。
- 修改 OpenAI API key、账单限制或模型选择策略。
- 在生产数据上运行未经批准的 OpenAI prompt。

## Pre-Tool Validation Rules

工具调用前的强制检查，防止 meta-harness 检测到的 tool_efficiency_risk：

- **文件读取前验证**：读取任何非 `.dev-harness` 模板文件前，先确认文件存在（`ls` 或 `test -f`）。不要盲目读取不确定路径的文件，避免 `[TOOL OUTPUT: ERROR] File does not exist` 错误和后续重试浪费 token。
- **Bash 命令可用性**：执行 shell 命令前确认工具已安装（如 `python3` vs `python`，`rg` vs `grep`）。如果返回 exit code 127，不要重试相同命令。
- **生成器脚本参数格式**：调用 `new_task_brief.py` 时，确保 list 字段（如 `StopConditions`、`AcceptanceCriteria`）使用正确的 repeat-option 格式。如果返回 `spec field must be a list` 错误，使用 `--SpecFile` 文件接口替代内联参数。
- **Repo-root 命令规则**：harness 脚本和检查默认从 repo root 调用，或使用 repo-root absolute path；不要在 `cockpit-api/` 内调用 `harness-engine/.dev-harness/...`。如果 `cd cockpit-api` 失败一次，先重新定位 repo root，不要继续重试相对路径。
- **路径一致性**：注意工作目录（Windows `E:` vs WSL `/mnt/e/`）。agent 在 WSL 环境下运行时，所有路径必须使用 POSIX 格式。

## Command Rules

- 优先使用非破坏性命令。
- 优先使用 `rg` 搜索。
- 生成 task brief 时，短输入可直接调用 `new_task_brief.py`；长输入或多列表项必须先写 JSON spec，再用 `new_task_brief.py --SpecFile <path>` 调用。
- 不要把长 JSON、长 Markdown 或大量重复列表参数塞进 shell 命令；用文件接口减少引号错误和 token 消耗。
- 生成 review draft 时，优先用 `new_review_draft.py --Task <NNN>` 让脚本定位 task brief；不要手猜 `081` 这类裸路径。
- 搜索文本时优先用本地 `rg`；不要把其它环境的 Grep 参数（例如 unsupported flags）套到当前工具上。
- 不要用内联 Python、notebook 或脚本语言做评分、验收或结果查找。
- 生产代码默认使用 Rust；PowerShell 只允许作为 dev-harness 包装器。
- 使用正式引擎接口做状态和结果操作。
- OpenAI API 调用必须遵循 `docs/policies/openai-policy.md`。

## OpenAI API Usage Rules

- 所有 OpenAI API 调用必须通过统一的 API 客户端模块。
- Prompt 版本必须可追溯（git tracked）。
- 模型选择必须记录在 task brief 或配置文件中。
- Token 消耗必须记录到 session-log。
- 不允许在循环中无限制调用 OpenAI API；必须设置 max_tokens 和 max_calls 预算。
- 结构化输出（JSON mode / function calling）优先于自由文本解析。
- 失败的 API 调用（错误、超时、rate limit）必须记录，不得静默重试。
