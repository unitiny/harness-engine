# Meta-Harness Self-Evolution v2 Design

## Authoritative Docs

- meta-harness/README.md
- meta-harness/config.yaml
- meta-harness/knowledge/ (全部 9 个 YAML 规则文件)
- .dev-harness/docs/protocols/self-evolution-protocol.md

## Architecture

### Phase 1: Fix Broken Sensors (A1-A4)

#### A1: Review Collection Fix
- **Root cause**: `collect_reviews()` 仅匹配 `{task_number}-*.md` 模式，当 review 文件不以任务号开头时返回 0 条
- **Fix**: 扩展为多模式扫描：`{task_number}-*.md` + 内容分析（文件内引用 task number）+ 目录全扫 fallback
- **File**: `meta-harness/engine/collect-signals.py` — `collect_reviews()` 函数
- **Verification**: 对现有 2 个 review 文件能采集到 2 条（当前为 0）

#### A2: Runtime Trace Duration Fix
- **Root cause**: `duration_ms = int(stat.st_size / 80) + line_count` 是伪值；`started_at`/`ended_at` 都取 `st_mtime`
- **Fix**: 使用文件系统时间差（span 起止文件的 mtime delta）+ console log 内时间戳解析 + 无数据时标记 `estimated: true` 并跳过 latency hotspot 检测
- **File**: `meta-harness/engine/collect-signals.py` — `collect_runtime_traces()` 函数
- **Verification**: 产出的 `duration_ms` 要么来自真实时间差，要么标记 `estimated: true` 且不触发 hotspot 告警

#### A3: Diff Evidence Implementation
- **Root cause**: `"diff_evidence_summary": "(diff analysis not yet automated)"` 恒为占位符
- **Fix**: 从 execution-receipts 中提取 `files_changed` 列表 + 从 git diff 获取变更统计（+lines/-lines）+ 有 receipt 时从 receipt body 提取 change_summary
- **File**: `meta-harness/engine/build-evidence-packets.py` — `build_gate_summary()` 函数
- **Verification**: evidence packet 中 `diff_evidence_summary` 包含实际文件名和变更行数

#### A4: Acceptance Quality Detectors
- **Root case**: `acceptance-quality-rules.yaml` 定义 5 条规则（ACC-R001~R005）但 `analyze-gaps.py` 无对应 detector 函数
- **Fix**: 新增 5 个 detector 函数 + `collect-signals.py` 读取 `acceptance/reports/` 目录
- **File**: `meta-harness/engine/analyze-gaps.py` + `meta-harness/engine/collect-signals.py`
- **Detectors**:
  - `detect_missing_acceptance_scenario` (ACC-R001): epic 有 UI 需求但无对应 YAML scenario
  - `detect_stale_selector` (ACC-R002): scenario selector 引用已删除的 DOM class/id
  - `detect_missing_l5_check` (ACC-R003): scenario 有 DOM 操作但无 persistence layer 验证
  - `detect_unnecessary_full_snapshot` (ACC-R004): smoke 场景不应含 fullPage snapshot
  - `detect_missing_smoke_tag` (ACC-R005): 关键 scenario 缺少 `tags: [smoke]`

### Phase 2: Close Feedback Loop (A5-A7)

#### A5: Proposal Lifecycle Management
- **Root cause**: `propose-repairs.py` 只写不删，22 个候选堆积，无过期清理
- **Fix**:
  - 新增 `cleanup_stale_proposals()`: 移除 source finding 不在当前信号窗口内的 proposal
  - 新增 `max_proposal_age_days` config（默认 14 天）
  - 为每个 proposal 添加 `last_seen_signal_date` 元数据
  - 超龄 proposal 移入 `proposals/expired/`（非直接删除）
- **File**: `meta-harness/engine/propose-repairs.py` + `meta-harness/config.yaml`
- **Verification**: 连续运行 2 次 meta-review，第 2 次不应包含第 1 次已失效的 proposal

#### A6: Auto-Trigger Meta-Review
- **Root cause**: `auto_harness_loop.py` 无任何 meta-harness 集成，meta-review 必须手动运行
- **Fix**:
  - 在 `auto_harness_loop.py` 的 post-loop 阶段（所有 round 完成后）增加可选的 meta-review 触发
  - 新增 `--with-meta-review` CLI 参数（默认 off，不破坏现有行为）
  - 产出 meta-review report 后自动 attach 到 auto loop commit
- **File**: `.dev-harness/scripts/auto_harness_loop.py`
- **Verification**: `auto_harness_loop.py --with-meta-review` 在 loop 结束后自动生成 `meta-review-latest.md`

#### A7: Memory Writeback
- **Root cause**: 22 个任务完成后 skill-candidates.md 为空、session-log.md 为空、project-memory.md 为 "pending"
- **Fix**:
  - `render-report.py` 末尾新增 `writeback_memory()` 函数
  - 从 meta-review findings 中提取可复用模式写入 `skill-candidates.md`（status: candidate）
  - 每次 meta-review 运行追加一条到 `session-log.md`
  - 发现高风险 gap 时更新 `active-context.md` 的 current_focus
- **File**: `meta-harness/engine/render-report.py`
- **Verification**: 运行 meta-review 后 `session-log.md` 新增一条记录

### Phase 3: Improve Discrimination (A8-A9)

#### A8: Smarter Offline Fixture Verdicts
- **Root cause**: `build_fixture_verdict()` 对几乎所有 finding 返回 `true_positive`，无筛选力
- **Fix**: 基于 `semantic-triage-rubric.yaml` 实现确定性规则：
  - `token_waste` + BLOCKED task → `benign_exception`（失败任务中的 token 浪费是次要问题）
  - `missing_evaluator_coverage` + 重复出现 >3 次 → `true_positive`（系统性问题）
  - `ai_guidance_gap` + 首次出现 → `needs_human_review`（不确定是否为真问题）
  - `delivery_quality_risk` + 无 review 证据 → `needs_human_review`（传感器失效导致，非真 finding）
- **File**: `meta-harness/engine/semantic-triage.py` — `build_fixture_verdict()` 函数
- **Verification**: offline 模式产出至少 2 种不同 verdict 类型

#### A9: Contract Replay Metric Alignment
- **Root cause**: `delivery_quality_risk` 类 proposal 回放 `timeout_count_per_run` 而非 `review_without_diff_count`
- **Fix**:
  - 新增 `review_without_diff_count` 和 `acceptance_coverage` 到 run metrics 采集
  - 更新 `proposal_metric_from_run_metrics()` 映射：
    - `delivery_quality_risk` → `review_without_diff_count` + `acceptance_coverage`
    - `missing_evaluator_coverage` → `blocked_without_repair_count`
  - 保留 `timeout_count_per_run` 仅用于 `tool_efficiency_risk`
- **File**: `meta-harness/engine/collect-signals.py` + `meta-harness/engine/replay-contracts.py`
- **Verification**: delivery quality proposal 回放使用正确的 metric

### Phase 4: Validation (A10)

#### A10: Unit Tests
- 为每个 detector 函数编写 pytest 测试（至少 3 个 case：positive / negative / edge）
- 端到端 pipeline 测试：mock signals → run full pipeline → assert report structure
- 回归测试：确保现有 22 个 proposal 的 replay 不因代码变更而误判
- **Directory**: `meta-harness/tests/`

## Task Priority

1. Phase 1 (A1-A4) 必须先完成 — 传感器不准确，后续所有优化都建立在错误数据上
2. Phase 2 (A5-A7) 在传感器修复后推进 — 关闭反馈环路
3. Phase 3 (A8-A9) 与 Phase 2 可并行 — 提升鉴别力
4. Phase 4 (A10) 贯穿全程 — 每个 A 完成后立即补测试
