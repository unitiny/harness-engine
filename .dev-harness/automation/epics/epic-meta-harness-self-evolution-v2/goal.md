# Epic: Meta-Harness Self-Evolution v2

将 meta-harness 从"被动观测 + 手动消费"升级为"准确感知 + 自动闭环 + 持续进化"的自改进系统。当前 meta-harness 存在三类致命缺陷：

1. **传感器失准** — 运行时轨迹时长为伪值(size/80)、review 采集量恒为 0、diff 证据为硬编码占位符、acceptance 质量规则有 YAML 但无代码
2. **反馈环路断裂** — 22 个 proposal 堆积未清理、无一晋升、auto loop 不触发 meta-review、memory/skill 系统空转
3. **鉴别力缺失** — offline fixture 100% true_positive 无筛选价值、contract replay 指标错配、无 agent 行为漂移信号

## North Star

Meta-harness 每次运行后自动产出 **可执行的修复候选**，关闭 "observe -> triage -> propose -> replay -> apply" 全链路，使 harness 在无需人工干预的情况下持续修正自身的检查规则、门禁阈值和信号采集策略。

## Safety Boundary

- 不削弱现有 authority-boundary.yaml 中任何 `may_not` 规则
- 不修改 auto_harness_loop.py 的核心 task_writer / implementer / gate 循环逻辑
- 不引入新的 LLM provider 或硬编码 API key
- 所有 promotion 仍需 human review（auto_promote 保持 false）
- 不修改 .dev-harness/ 下已有的 gate 脚本的验收标准
