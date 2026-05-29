# Video Outline

> **主题**：`blueprint`（Checkpoint Plan 已选定）—— 深藏青底 + 青色强调 + IBM Plex Mono 等宽字体，工程蓝图气质
> **总时长**：约 2 分 58 秒（口播 ~710 字 ÷ 4 字/秒）
> **章节数**：4 章 / 17 步

---

## 1. hook — 为什么需要 harness（4 steps · ~28s）

**信息池**（chapter agent 按需挂角标 / 副标 / pull-quote / mono cue）：
- 对比：AI agent 无人监管 vs 有 harness 的工作流 —— 来源 project README
- 术语：scope 扩散（implementer 修改了 task brief 限定范围外的文件）—— 来源 .dev-harness/README.md scope_diff_gate 说明
- 术语：gate（自动化质量检查脚本，如 scope_diff_gate / dev_gate / write_task_gate）—— 来源 .dev-harness/checks/
- 数字：10+ gate 脚本 —— 来源 .dev-harness/checks/ 目录
- 术语：review（按 review-template.md 对 scope / 验证 / 安全 / memory promotion 的结构化审查）—— 来源 .dev-harness/templates/review-template.md

**开发计划**：

- step 1 (~5s) — 钩子：大字"你让 AI 写代码，然后呢？"居中，背景极简
- step 2 (~7s) — scope 扩散可视化：文件树示意，部分文件标红（被误改）
- step 3 (~7s) — "跑通了"反差：大字引号 + 下方 gate 未通过的 checklist
- step 4 (~9s) — 核心定义：harness 三要素（task brief / gate / review）一线排列

口播节选：
> harness 就是给 AI 上工程纪律。scope 锁在 task brief，质量卡在 gate，结果交给 review。

---

## 2. dev-harness — Dev Harness：执行层（5 steps · ~60s）

**信息池**：
- 流程：task brief → implement → gate → review → commit —— 来源 .dev-harness/README.md Required Loop
- 双模型：高配模型（GPT-5.5）当 architect/reviewer，低配模型（GLM-5.1）当 implementer —— 来源 automation/agent-config.json
- gate 名单：scope_diff_gate / dev_gate / write_task_gate / review_gate / receipt_gate / memory_gate / epic_alignment_gate —— 来源 .dev-harness/checks/
- 五层验收：L1 页面可达 → L2 API 状态码 → L3 控制台无错 → L4 DOM 可见可交互 → L5 数据刷新后持久 —— 来源 acceptance/core/layers.py
- 术语：scope contract（task brief 中 allowed files / acceptance criteria / verification command / stop conditions）—— 来源 templates/task-template.md
- 术语：execution receipt（implementer 交付的结构化验证记录）—— 来源 templates/execution-receipt-template.md
- 风险等级：LOW / MEDIUM / HIGH / BLOCKED_WITHOUT_APPROVAL —— 来源 .dev-harness/README.md
- authority hierarchy：system instructions → AGENT.MD → task brief → repo files → tool outputs → model suggestions —— 来源 self-evolution-protocol.md

**开发计划**：

- step 5 (~10s) — Dev Harness 总览：loop 流程图（task brief → 执行 → gate → review → 提交），每节点标注对应脚本/目录
- step 6 (~12s) — 双模型架构：左侧 architect（高配）写 task / 审 review，右侧 implementer（低配）领 task / 交 receipt，中间 task brief 连接
- step 7 (~14s) — gate 体系：列举真实 gate 名（scope_diff_gate / dev_gate / write_task_gate / receipt_gate / memory_gate / epic_alignment_gate），每个一行简注
- step 8 (~12s) — 五层验收：L1-L5 从上到下展开，每层一句话 + 图标状态
- step 9 (~12s) — scope contract：task brief 结构拆解，allowed files / acceptance criteria / verification command / stop conditions 四字段

口播节选：
> 双模型分工。高配模型当 architect，写 task、审 review。低配模型当 implementer，领 task 干活。

---

## 3. meta-harness — Meta Harness：观测层（5 steps · ~60s）

**信息池**：
- 定位：Meta-Harness observes recent harness artifacts, diagnoses quality gaps, and proposes candidate improvements. It does NOT modify active .dev-harness files —— 来源 meta-harness/README.md
- 七步 pipeline：collect-signals → analyze-gaps → build-evidence-packets → semantic-triage → propose-repairs → replay-contracts → render-report —— 来源 meta-harness/README.md Pipeline Steps
- 四类缺口：token_waste / ai_guidance_gap / delivery_quality_risk / missing_evaluator_coverage —— 来源 meta-harness/knowledge/gap-taxonomy.yaml
- 术语：prediction contract（提案中声明的预期未来行为 + 可测量信号 + 回放方法）—— 来源 self-evolution-protocol.md
- proposal 状态：candidate_semantic_supported / candidate_rule_only / candidate_needs_human_review / rejected_false_positive / rejected_benign_exception —— 来源 meta-harness/README.md
- 规则状态：candidate → validated → active —— 来源 self-evolution-protocol.md Promotion Rules
- authority boundary：may propose, may not promote/edit —— 来源 meta-harness/README.md Authority Boundary

**开发计划**：

- step 10 (~8s) — 引入：大字"harness 谁来查？" + Meta Harness 定义（只看不动手）
- step 11 (~12s) — 七步 pipeline：横向流程图，每步名 + 一行注释，逐步揭示
- step 12 (~14s) — 四类缺口：token 浪费 / AI 指引缺口 / 交付质量风险 / 评估覆盖不足，每类一个真实案例示意
- step 13 (~12s) — 预测合约：提案卡片结构（预期行为 + 可测量信号 + 回放方法），不是"建议改进"而是可量化预测
- step 14 (~14s) — 回放验证：基线数据 vs 当前数据对比，candidate → validated → active 三级晋升，隔离标记

口播节选：
> 关键机制是预测合约。每个提案都带承诺："改这条规则后 token 浪费率降到多少。"不是"建议改进"，是可量化预测。

---

## 4. self-evolve — 自进化闭环（3 steps · ~32s）

**信息池**：
- 自进化 core loop：execution trace → outcome judgement → failure classification → harness gap analysis → proposed harness change → prediction contract → validation/replay → promote/quarantine/reject —— 来源 self-evolution-protocol.md
- gap types：missing_rule / weak_rule / missing_checker / missing_memory / bad_tool_policy / bad_workflow / missing_eval / none —— 来源 self-evolution-protocol.md
- rule rationale：每条 promoted rule 必须包含 why it exists / risk it prevents / when it should not apply —— 来源 self-evolution-protocol.md Rule Rationale
- patch targets：checker / workflow / eval / memory / template / tool_policy / instruction —— 来源 self-evolution-protocol.md Patch Targets
- 核心提问："Why did the harness fail to constrain this?" —— 来源 self-evolution-protocol.md
- 收尾必答：本次任务有什么可复用经验？应沉淀为 project memory / skill candidate / checker / template / runbook 规则，还是不沉淀？—— 来源 .dev-harness/README.md Task Closure Packet

**开发计划**：

- step 15 (~13s) — 双层闭环图：dev harness 外环 + meta harness 内环，产出物流动箭头连接
- step 16 (~11s) — 核心提问："harness 哪没拦住？" + gap type 列表（missing_rule / weak_rule / missing_checker / missing_memory / missing_eval）
- step 17 (~8s) — 收束：三级晋升（candidate → validated → active）+ CTA "去 GitHub 搜 harness-engine"

口播节选：
> 规则不能"听起来有道理"就上线。candidate、validated、active 三级。每升一级都要证据和回放。

---

## 素材清单

### 1. hook
- ✓ 无需外部素材（纯文字 + 图形示意）

### 2. dev-harness
- ✓ gate 名单来自项目 checks/ 目录（纯文字列举）
- ✓ 双模型架构示意（纯图形）
- ✓ 五层验收模型（纯文字列表）
- ⚠️ task brief 结构示意（可用项目 templates/task-template.md 内容作为数据源）

### 3. meta-harness
- ✓ pipeline 步骤名来自 README（纯文字）
- ✓ 四类缺口来自 gap-taxonomy.yaml（纯文字）
- ✓ 预测合约结构示意（纯图形）
- ⚠️ 回放验证数据对比图（placeholder 数据即可）

### 4. self-evolve
- ✓ 双层闭环图（纯图形）
- ✓ gap type 列表（纯文字）
- ✓ 三级晋升示意（纯图形）
