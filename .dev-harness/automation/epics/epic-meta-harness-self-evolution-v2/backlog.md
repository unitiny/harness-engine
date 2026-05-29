# Meta-Harness Self-Evolution v2 Backlog

## Phase 1: Fix Broken Sensors（优先级最高）

1. 修复 review 采集 — `collect_reviews()` 多模式匹配，确保现有 2 个 review 文件被正确采集 (A1)
2. 修复运行时轨迹时长 — 替换 size/80 伪值，标记 estimated 且不触发误告警 (A2)
3. 实现 diff 证据分析 — 从 receipt/git 提取实际变更数据替换占位符 (A3)
4. 实现 acceptance 质量检测器 — 5 个 detector 函数 + signal 采集 (A4)

## Phase 2: Close Feedback Loop

5. Proposal 生命周期管理 — 过期清理 + last_seen_signal_date + expired 目录 (A5)
6. Auto loop 集成 meta-review 触发 — `--with-meta-review` 参数 + post-loop 执行 (A6)
7. Memory 写回 — session-log 追加 + skill-candidates 候选提取 + active-context 更新 (A7)

## Phase 3: Improve Discrimination

8. 智能 offline fixture — 基于 rubric 规则的多 verdict 判定 (A8)
9. Contract replay 指标对齐 — delivery quality 使用正确 metric (A9)

## Phase 4: Validation

10. 补充 meta-harness 单元测试 — detector / pipeline / regression (A10)

---

**预计 task brief 数量**: 10-14 个（A4 和 A10 可能拆分为 2-3 个 brief）
**依赖关系**: Phase 1 必须先完成；Phase 2 和 Phase 3 可并行；A10 贯穿全程
**风险**: A6 涉及修改 auto_harness_loop.py 核心脚本，需谨慎 scope 控制
