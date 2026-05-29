# Meta-Harness v0.3

Hybrid harness optimizer: deterministic rules as sensors + optional LLM semantic triage.

## Purpose

Meta-Harness observes recent harness artifacts, diagnoses quality gaps, and proposes candidate improvements. It does **not** modify active `.dev-harness` files.

The operating loop:

```
observe (rules) -> triage (LLM optional) -> propose -> replay contracts -> human review
```

## Quick Start

```powershell
# Rule-only mode (default, no LLM)
python harness-engine/meta-harness/engine/run_meta_review.py

# With offline fixture semantic triage (no LLM call, uses heuristics)
python harness-engine/meta-harness/engine/run_meta_review.py -Offline

# With live LLM semantic triage (requires agent-config.json role)
python harness-engine/meta-harness/engine/run_meta_review.py -Semantic

# More history
python harness-engine/meta-harness/engine/run_meta_review.py -Limit 10 -Semantic

# Full scan with semantic triage
python harness-engine/meta-harness/engine/run_meta_review.py -All -Offline

# PowerShell wrapper (delegates to python internally)
harness-engine/meta-harness/engine/run-meta-review.ps1 -Limit 10
```

After running, read:

```
harness-engine/meta-harness/reports/meta-review-latest.md
```

## Pipeline Steps

| Step | Module | Description |
|------|--------|-------------|
| 1 | collect-signals.py | Bounded collection of recent tasks, receipts, reviews, policy refs |
| 2 | analyze-gaps.py | Deterministic heuristic gap analysis |
| 3 | build-evidence-packets.py | Convert findings into bounded evidence packets |
| 4 | semantic-triage.py | Optional LLM triage (or offline fixture mode) |
| 5 | propose-repairs.py | Merge rule + semantic findings into candidate proposals |
| 6 | replay-contracts.py | Replay prediction contracts against current data |
| 7 | render-report.py | Generate two-layer human-facing report |

## Finding Categories

| Category | Description |
|----------|-------------|
| Token Waste | Repeated boilerplate, broad reads, missing generator use |
| AI Guidance Gap | Missing scope, vague criteria, ambiguous stop conditions |
| Delivery Quality Risk | Reviews without diff, missing gate evidence, incomplete scope checks |
| Missing Evaluator Coverage | BLOCKED tasks without repair proposals, risky tasks without eval criteria |

## Proposal States

| State | Meaning |
|-------|---------|
| candidate_semantic_supported | LLM agrees the finding is a true issue |
| candidate_rule_only | Produced by deterministic rules only |
| candidate_needs_human_review | LLM is uncertain or flags risk |
| rejected_false_positive | Rule finding rejected by semantic triage |
| rejected_benign_exception | Finding is real but should not become a patch |

## LLM Integration

Semantic triage uses the existing automation role/provider pattern:

- Role config in `agent-config.json` (recommended role: `semantic_triage`)
- LLM invocation through `invoke_semantic_role.py`
- No hardcoded credentials or provider config in meta-harness
- Falls back to rule-only report if LLM fails

## Report Sections

1. **Rule Findings** — What deterministic checks found
2. **Semantic Judgement** — Which findings are true/false positives
3. **Candidate Repairs** — Ranked proposals
4. **Prediction Contracts** — Expected future behavior per proposal
5. **Contract Replay** — Whether prior proposals improved, regressed, or are inconclusive
6. **Recommended Next Patch** — One next patch with validation command

## Authority Boundary

Meta-Harness **may**:
- Propose candidate changes to harness artifacts
- Generate reports and findings
- Create prediction contracts and replay them

Meta-Harness **may not**:
- Weaken safety, research, or trading boundaries
- Promote scientific verdicts or edit active `.dev-harness` files
- Replace reviewer judgment
