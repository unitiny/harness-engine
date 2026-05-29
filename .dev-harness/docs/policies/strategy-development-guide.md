# Strategy Development Guide

This guide adds strategy-specific guardrails to the dev harness.

## Core Boundary

Historical Event Trajectory Model is not a generic "price went up, therefore short" system.

All product implementation for this strategy must be in Rust. Dev-harness scripts may launch checks, but they must not own strategy logic.

The project must separate:

```text
price anomaly trigger
game-structure classification
same-type historical matching
probability and payoff estimation
risk and execution gate
```

Price events are useful for discovery. They are not sufficient for trading decisions.

## MVP Scope

The first strategy scope is:

```text
Binance USDT perpetual altcoins:
sharp pump -> long crowding -> aggressive buy-flow exhaustion -> failed extension -> short-side path test
```

Development should prove or disprove this narrow edge before adding broader event types.

## Required Workflow For Strategy Changes

Before implementing strategy logic, define:

- Rust crate or module ownership.
- Event type being changed.
- Trigger conditions.
- Features available at trigger time.
- Labeling window and first-hit rules.
- Similarity matching method.
- Cost model assumptions.
- Liquidity filters.
- Walk-forward validation split.
- Failure modes the test should catch.

Any task that changes event detection, labels, matching, scoring, or backtest behavior is at least `HIGH` risk unless it is docs-only.

Any task that proposes non-Rust production code must stop for explicit user approval.

## Leakage Checks

Every strategy implementation must check:

- No future high/low/close is used to create the event trigger.
- Rolling statistics use only prior data.
- Cooldown logic prevents the same pump from becoming many samples.
- Entry price is defined after trigger time, normally next 5m open.
- Outcome fields are written only after the observation window.
- Backtest predictions only use historical events earlier than the candidate event.

## Event Classification Rules

Do not place all pump events in the same library.

At minimum, distinguish:

- `long_crowding_exhaustion`
- `listing_or_contract_launch`
- `news_or_project_catalyst`
- `meme_attention_expansion`
- `sector_rotation`
- `thin_liquidity_manipulation`
- `unknown`

The MVP may only trade or score `long_crowding_exhaustion`. Other classes can be filtered, logged, or used as non-trade evidence.

## Backtest Requirements

Backtests must report:

- Event count before and after filters.
- Same-type neighbor count distribution.
- `P(win)`, `P(loss)`, `P(timeout)`.
- Net expected value after fees, slippage, and funding.
- Average and 95% adverse excursion.
- Maximum consecutive losses.
- Sensitivity to main thresholds.
- Concentration by symbol and date.

Passing a dev gate proves engineering integrity, not trading edge.

## OpenAI Usage

OpenAI can help with extraction, classification, summarization, and review, but strategy-critical behavior must remain auditable.

- Use structured outputs when OpenAI is involved.
- Log prompt version, model, token budget, and failure modes.
- Never let an LLM overwrite deterministic market-data labels.
- Never run unapproved prompts on production data.

## Stop Conditions

Stop and ask the user if a task requires:

- Expanding from one MVP event type into broad event taxonomy.
- Adding social/news/on-chain/OI/liquidation data as required dependencies.
- Changing raw historical data.
- Weakening cost, liquidity, or leakage checks.
- Producing live-trading instructions instead of candidate alerts.
- Adding non-Rust product code.
