# Goal-Driven Harness Execution Guide

## `/goal` Command — How It Works

`/goal` is a Claude Code built-in command (shipped May 2026) that provides
"run until done" autonomous execution. It uses a **dual-model architecture**
to separate the worker from the evaluator.

### Architecture

```
┌─────────────────────────────────────────────┐
│  Worker Model (Sonnet / Opus)               │
│  Per turn: read files, edit code, run cmds  │
└──────────────┬──────────────────────────────┘
               │ turn ends
               ▼
┌─────────────────────────────────────────────┐
│  Evaluator Model (Haiku, independent)       │
│  Input: goal condition + conversation       │
│  Decision: Yes → goal achieved, stop        │
│            No  → reason fed back to worker  │
└─────────────────────────────────────────────┘
```

### Key Design Principle

The model doing the work is the worst judge of whether it is done. By using
an independent, tool-less lightweight model as evaluator, `/goal` prevents
the common failure mode where an agent prematurely declares completion.

### Technical Constraints

| Constraint | Value |
|-----------|-------|
| Max condition length | 4,000 characters |
| Models per session | 1 goal at a time |
| Evaluator tools | None (judges transcript only) |
| Session resume | Goals survive `--resume` / `--continue` |
| Non-interactive | Works: `claude -p "/goal ..."` |

### Effective Condition Writing

Three ingredients for a good goal condition:

1. **Measurable end state** — test exit code, build result, file count
2. **Verification method** — how Claude proves it (`npm test` exits 0)
3. **Negative constraints** — what must NOT change en route

---

## Three Approaches to Harness Execution

### Approach A: `/goal` Directly Operates Harness

Claude reads files, runs gates, fixes issues, re-runs — all driven by
per-turn `/goal` evaluation.

```
/goal → worker reads context → runs dev_gate → fixes failures → re-runs → ...
```

**Strengths:**
- Maximum adaptability — every turn can change strategy
- Human can interrupt and redirect at any point

**Weaknesses:**
- High token cost — full conversation context every turn
- Context rot risk on long tasks (>10 turns)
- No bounded AI calls — each turn uses the main model

**Best for:** Simple fixes, 1–5 turn tasks, exploratory work where
direction is uncertain.

### Approach B: `auto_harness_loop.py` Standalone

The Python loop script handles the full architect → implementer → reviewer
cycle with bounded per-role AI calls.

```
loop.py → task-writer(AI) → implementer(AI) → gate → reviewer(AI) → next round
```

**Strengths:**
- Token efficient — each AI call gets a bounded, focused prompt
- No context rot — every round is independent
- Structured flow — task briefs, receipts, reviews all generated correctly
- Local commits every round

**Weaknesses:**
- Fixed retry logic (default 2 in-round retries, then repair task)
- Cannot adapt cross-round strategy — if a gate keeps failing the same way,
  loop just creates repair tasks that may also fail the same way
- Requires `agent-config.json` setup for model providers

**Best for:** Well-defined epics with clear scope, batch execution when
parameters are known upfront.

### Approach C: `/goal` Wrapping `auto_harness_loop.py` (Recommended)

`/goal` drives at the round level; `auto_harness_loop.py` executes within
each round. The evaluator checks gate results between rounds, and the worker
can adjust parameters or fix blocking issues before starting the next iteration.

```
/goal "condition"
  → worker runs loop.py --MaxIterations 1
  → loop handles: write task → execute → gate → review
  → evaluator checks: gate passed? reviews clean?
  → if No: worker reads failure reason, adjusts, runs another iteration
  → if Yes: goal achieved
```

**Strengths:**
- Best of both: bounded AI calls inside loop + adaptive cross-round strategy
- No context rot — loop rounds are independent, goal evaluator is lightweight
- Worker can intervene: adjust epic scope, fix environment issues, modify
  agent-config, escalate blockers
- Human interruptible at goal level

**Weaknesses:**
- Slightly more setup (need agent-config.json + goal condition)
- Need to coordinate two levels of "done" (loop internal vs. goal external)

**Best for:** Most real-world harness execution — multi-round epics where
both efficiency and adaptability matter.

---

## Comparison Matrix

| Dimension | A: `/goal` direct | B: `loop.py` standalone | C: `/goal` + loop |
|-----------|-------------------|------------------------|-------------------|
| Adaptability | High | Low | High |
| Token cost | High | Low | Medium |
| Context rot risk | High | None | Low |
| Fault recovery | Claude decides | Fixed retry (2x) | Retry + Claude adjusts |
| Human control | Any time | Kill only | Any time |
| Structured artifacts | Manual | Auto-generated | Auto-generated |
| Setup complexity | None | agent-config.json | agent-config.json |
| Best task scope | 1–5 turns | Known-scope epics | Most epics |

---

## Practical Usage

### Basic Goal — Direct Harness Gate

```bash
/goal "dev_gate.py --Fast 通过，acceptance smoke 通过率 100%"
```

### Goal Wrapping Loop — Single Epic

```bash
/goal "完成 auto_harness_loop 对 epic 的验证。
条件：
1. dev_gate.py --Fast exit 0
2. acceptance scenarios 全部 PASS
3. meta-harness -Offline 无 blocking finding
4. 不修改 harness-engine/.dev-harness/docs/policies/ 下的文件
5. 连续 2 轮 gate FAIL 则停下来报告原因"
```

### Goal with Environment Constraints

```bash
/goal "用 auto_harness_loop.py --MaxIterations 3 验证 epic。
验证条件：
- harness_engine/.dev-harness/checks/dev_gate.py exit 0
- harness_engine/acceptance/gates/acceptance_gate.py --env dev exit 0
约束：
- 不修改任何 gate 规则文件
- 不修改 quality-gates.yaml 阈值
- 每轮结果记录到 task-briefs/ 和 reviews/
- 如果某轮 implementer 连续失败，创建 BLOCKED 状态的 task 并报告"
```

### Segmenting Long Tasks

For tasks expected to take >10 loop rounds, split into segments:

```bash
# Segment 1: Setup + first pass
/goal "跑 auto_harness_loop --MaxIterations 5 完成 epic 前半部分。
条件：前 5 轮的 task 全部 DONE 或有明确 BLOCKED task。"

# Review segment 1 results, then:
# Segment 2: Fix blockers + complete
/goal "跑 auto_harness_loop --MaxIterations 5 完成 epic 后半部分。
条件：dev_gate --Fast PASS，无 BLOCKED task。"
```

---

## Anti-Patterns to Avoid

### 1. Vague Goal Conditions

Bad: `/goal "把项目搞好"`
Good: `/goal "dev_gate.py --Fast exit 0 且 acceptance coverage >= 0.8"`

### 2. No Negative Constraints

Without constraints, the worker may pass gates by weakening them:

```bash
# Bad — worker could edit quality-gates.yaml to lower thresholds
/goal "all gates pass"

# Good — lock the gate rules
/goal "all gates pass without modifying quality-gates.yaml or any file under docs/policies/"
```

### 3. Unbounded Turn Count

Add turn/time bounds to prevent runaway execution:

```bash
/goal "完成 3 轮 harness 循环且 gate PASS，或超过 20 turns 则停下来报告阻塞原因"
```

### 4. Goal Evaluating Its Own Work

Don't let the worker model judge completion. `/goal` already handles this
via the separate evaluator, but avoid patterns like:

```bash
# Bad — worker generates its own pass report and goal accepts it
/goal "worker says it's done"

# Good — goal requires objective evidence
/goal "dev_gate.py exits 0 AND acceptance reports show 100% smoke pass rate"
```

---

## Integration with Harness Layers

### Acceptance Testing

`/goal` conditions should reference acceptance artifacts:

- `harness-engine/acceptance/reports/` — latest test results
- `quality-gates.yaml` thresholds — smoke 100%, overall >= 80%
- Scenario files — ensure coverage of changed features

### Meta-Harness

After a goal-driven session, run meta-harness to check for systemic gaps:

```bash
python harness-engine/meta-harness/engine/run_meta_review.py -Offline
```

The meta-harness will detect:
- ACC-R001: UI features without acceptance scenarios
- ACC-R002: Stale selectors in scenarios
- ACC-R003: Data-modifying scenarios without L5 persistence checks
- ACC-R004: Unnecessary FULL snapshot usage
- ACC-R005: Critical path scenarios missing smoke tag

### AGENT.MD Integration

When `/goal` is active, the agent should still follow `AGENT.MD` for:
- Default harness activation rules
- Task closure packet requirements
- Dual-model workflow constraints
- Memory and skill-candidate promotion rules

---

## References

- [Claude Code `/goal` Documentation](https://code.claude.com/docs/en/goal)
- [VentureBeat: Claude Code Goals separates worker from evaluator](https://venturebeat.com/orchestration/claude-codes-goals-separates-the-agent-that-works-from-the-one-that-decides-its-done)
- `harness-engine/.dev-harness/docs/operations/runbook.md` — full runbook
- `harness-engine/.dev-harness/docs/operations/acceptance-protocol.md` — acceptance testing protocol
- `AGENT.MD` — agent entry point
