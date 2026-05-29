# Phase 0 Data Foundation Acceptance

Phase 0 is not accepted by `cargo test` alone. A data-foundation change must pass the Rust quality gate and a schema-contract review.

## Required Commands

```powershell
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
harness-engine/.dev-harness/checks/dev-gate.ps1
```

## Harness Documentation Hygiene

- New harness documents are categorized according to
  `harness-engine/.dev-harness/docs/document-governance.md`.
- Task briefs stay in `task-briefs/`; reviews and audit reports stay in
  `reviews/`; stable harness governance stays in `docs/`.
- No task-specific markdown file may be created directly under the
  `.dev-harness` root.
- `dev-gate.ps1` must reject unapproved root markdown files.

## Schema Contract

- Raw kline records include taker-buy fields, data-quality flags, source metadata, and market/available/ingested timestamps.
- Funding records distinguish settled and predicted values and point-in-time queries must require both `funding_time <= event_time` and `available_at <= event_time`.
- Symbol lifecycle records must retain enough historical contract metadata for Phase A universe construction, not only current active symbols.
- Duplicate raw market-data writes preserve the original record.
- At least one negative regression test covers a non-happy-path query or leakage condition.

## Review Questions

- Can Phase A build a historical USD-M universe without relying on current exchange metadata only?
- Can a detector snapshot prove which values were available at event time?
- Can raw data quality issues be filtered without rewriting the raw record?
- Does the verification include fmt, clippy, tests, and harness policy checks?
