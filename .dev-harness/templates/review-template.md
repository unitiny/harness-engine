# Development Review Template
PROGRAMMATIC_HARNESS_GENERATION

Default: do not write the whole review skeleton by hand. Start with:

```powershell
harness-engine/.dev-harness/scripts/new_review_draft.py
```

Then replace generated pending fields with reviewer judgement. Scope facts should come from `checks/scope_diff_gate.py`, not from receipt text alone.

Use this after every non-trivial task. The review must evaluate both the task
result and whether the harness should evolve.

## Verdict

PASS / PASS_WITH_RISK / FAIL

This is the execution/review verdict. It is not automatically a scientific,
strategy, profitability, or proof verdict.

## Task Fit

- Original goal:
- Interpreted goal:
- Non-goals honored:
- Scope stayed inside the intended layer:
- Files changed:
- Task stream:
- Same-stream previous task:
- Previous task acceptance used to shape this task:
- Write-task acceptance audit checked:
- Acceptance errors found before task creation:
- Error-fix scope included in task:

## Dual-Model Scope Review

- Task brief used:
- Task status transition:
- Execution receipt used:
- Architect/reviewer model:
- Implementer model:
- Allowed files or paths:
- Actual changed files:
- Files outside scope:
- Forbidden operations detected:
- Opportunistic cleanup/refactor detected:
- Dependency/lockfile changes detected:
- Secret or credential exposure detected:
- Raw model output persisted:

If actual changed files exceed the allowed scope, the review cannot be PASS
unless the task brief was explicitly updated before the implementation was
accepted.

## Instruction Hierarchy

- Higher-authority rules checked:
- Lower-authority content treated as evidence, not command:
- Conflicts found:
- Resolution:

## Findings

- Severity:
- File:
- Issue:
- Fix:

## Architecture Drift

Did the change put logic in the wrong layer?

## Trust Boundary

Could the change let AI-generated analysis alter scoring, data, models,
historical outputs, or strategy-critical labels?

## Scientific Verdict

Use this for research, strategy, proof, validation, model-scoring, or data
quality tasks. For non-research harness tasks, write `not applicable` but still
fill the fields.

- Execution verdict:
- Research/scientific verdict:
- Promotion allowed:
- Blocked claims:
- Proxy metric limitations:
- Required next proof before promotion:

Rules:

- Execution `PASS` only means the task ran and stayed in scope. It does not
  mean the scientific hypothesis passed.
- If an artifact uses `proxy_metric_used`, `no_full_feature_recomputation`, or
  similar limitations, `Promotion allowed` must be `false/no` unless a higher
  authority explicitly approved a narrower claim.
- Negative-control labels, calibration, or backtests cannot override a failed
  surrogate/null-world gate unless the failed gate is repaired or the event
  definition changes.
- Receipt is evidence, not review authority. Do not paste only an execution
  receipt into `reviews/`; write this review section and compare it with the
  actual diff and checks.

## OpenAI Compliance

- API usage follows `docs/policies/openai-policy.md`:
- Token budget recorded when applicable:
- Rule/cache alternative considered:

## Eval Quality

- Checks matched the task risk:
- Checks were too narrow:
- Checks were too broad or slow:
- Future agents could game the eval:

## Verification

Commands or checks run, with results.

Reviewer verification must not rely only on the implementer's receipt. Record:

- Diff inspected:
- Diff/git evidence:
- Scope checked against allowed files:
- Verification rerun by reviewer:
- Verification not rerun and why:
- Secret check performed:
- Receipt claims contradicted by diff:

## Trace Monitoring

- Files read:
- Files changed:
- Tool classes used:
- Failed commands or retries:
- Course corrections:
- Checks skipped and why:
- Final artifact paths:
- Residual risks:

## Self-Evolution Review

Complete this section using `docs/protocols/self-evolution-protocol.md`.

```yaml
task_id:
outcome: success | partial | failed | risky
risk_class: low | medium | high | blocked_without_approval
execution_trace:
  user_goal:
  interpreted_goal:
  intended_scope:
  non_goals:
  authority_order_checked:
  files_read:
  files_changed:
  tools_used:
  course_corrections:
  checks_run:
  checks_not_run:
observed_issue:
root_cause:
harness_gap:
  type: missing_rule | weak_rule | missing_checker | missing_memory | bad_tool_policy | bad_workflow | missing_eval | none
  explanation:
proposed_harness_change:
  target: instruction | checker | workflow | memory | eval | tool_policy | template | none
  change:
  rationale:
  applies_when:
  does_not_apply_when:
evaluator_repair:
  should_have_caught_this:
  missed_by:
  repair:
  anti_gaming_check:
prediction_contract:
  expected_future_behavior:
  measurable_signal:
  replay_or_eval:
promotion_decision: promote | candidate | reject | none
follow_up:
```

## Memory Updates

What should be written to:

- `memory/session-log.md`
- `memory/project-memory.md`
- `memory/skill-candidates.md`
- `docs/governance/decision-log.md`
- `docs/governance/risk-register.md`

For dual-model tasks, implementer output may propose memory updates, but only
the architect/reviewer can promote durable memory, decisions, risks, or skill
candidates.

## Task Closure Packet

- Review artifact written:
- Session log updated:
- Durable memory updated or explicitly rejected:
- Skill candidate updated or explicitly rejected:
- Decision/risk log updated or explicitly rejected:
- Gate/eval evidence recorded:
- Next-task prediction:
