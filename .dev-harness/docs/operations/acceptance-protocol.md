# 验收测试协议

版本: 1.0 | 2026-05-22

## 概述

本协议定义数据中台驾驶舱智能体项目的验收测试规范。所有 UI 功能和 API 端点在交付前必须通过验收场景验证。

## 核心原则

1. **场景驱动验收** — 每个功能有对应的 YAML 验收场景
2. **五层闭环验证** — L1(环境) → L2(网络) → L3(控制台) → L4(DOM) → L5(持久化)
3. **Token 优化** — 使用三级快照模型，仅在失败时生成 FULL 快照
4. **自动化门禁** — 验收结果通过 quality gates 评估，阻塞门禁失败则交付不通过

## 验收场景规范

### 何时编写场景

- 新增 UI 页面或组件 → 创建场景验证 L1-L4
- 新增 API 端点 → 创建场景验证 L2 + L5
- 修改已有功能 → 更新对应场景
- 修复 Bug → 添加回归场景

### 场景文件位置

```
harness-engine/acceptance/scenarios/{feature-name}.yaml
```

### 场景模板

使用 `harness-engine/acceptance/scenarios/auto-acceptance-template.yaml` 作为起点。

### 场景命名规范

- 文件名: 小写短横线分隔（如 `user-login.yaml`, `data-query.yaml`）
- 场景 name: 中文描述（如 "用户登录验证"）
- 标签: 至少包含 `smoke`（冒烟测试）或 `regression`（回归测试）

## 三级快照模型

| 级别 | 大小 | 用途 | 何时使用 |
|------|------|------|---------|
| Minimal | ~300 chars | 页面定位 | 导航步骤、预检查 |
| Summary | ~1-3K chars | 组件验证 | 验证步骤、常规检查 |
| Full | ~5-50K chars | 详细诊断 | **仅失败时自动生成** |

### 禁止行为

- **禁止** `document.body.innerHTML` 全量 DOM 获取（500K+ chars）
- **禁止** 在非诊断步骤使用 `snapshot_level: full`
- **禁止** 连续多次快照来检测变化（用 `wait` 替代）

### 必须行为

- **必须** 使用 `wait` 等待异步操作完成
- **必须** 在数据修改场景中包含 L5 持久化验证
- **必须** 在 YAML 中使用 `${ENV_VAR}` 管理凭据

## 运行验收

### 手动运行

```bash
# 运行所有场景
python harness-engine/acceptance/gates/acceptance_gate.py \
  --scenario-dir harness-engine/acceptance/scenarios \
  --env dev \
  --report-dir harness-engine/acceptance/reports

# 快速失败模式
python harness-engine/acceptance/gates/acceptance_gate.py \
  --scenario-dir harness-engine/acceptance/scenarios \
  --env dev --fail-fast
```

### 通过 dev_gate 运行

验收门禁已集成到 `dev_gate.py`，每次开发门禁检查时自动运行验收场景。

## 质量门禁

质量门禁定义在 `harness-engine/acceptance/config/quality-gates.yaml`：

| 门禁 | 描述 | 阻塞 |
|------|------|------|
| smoke_pass_rate | 所有 smoke 标签场景必须通过 | 是 |
| overall_pass_rate | 80% 以上场景通过 | 是 |
| console_error_free | 无控制台错误 | 是 |
| performance_gate | 单步骤不超过 10 秒 | 否 |

## 验收报告

报告生成在 `harness-engine/acceptance/reports/`，格式为 Markdown。

报告结构：
1. 汇总表（场景名、状态、步骤通过率、耗时）
2. 每场景详情（步骤表、失败诊断、控制台/网络摘要）
3. 总结论和建议

## 与其他 Harness 组件的关系

- **dev_gate.py**: 集成验收门禁作为检查项
- **meta-harness**: 监控验收质量，检测缺失/过时场景
- **角色提示**: architect/implementer/reviewer/test-engineer 均包含验收意识
- **任务简报**: 应包含或引用验收场景

## 持续改进

- meta-harness 定期分析验收信号，检测缺失场景和过时选择器
- 回顾会议中评估验收覆盖率
- 新发现的 Bug 应添加为回归场景
