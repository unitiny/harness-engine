# Reviewer Prompt (DEPRECATED)

This role has been merged into the implementer.
See `harness-engine/.dev-harness/prompts/implementer.md` for the combined
execution and verification responsibilities.
See `harness-engine/.dev-harness/templates/execution-receipt-template.md` for
the expanded receipt format that replaces separate review artifacts.

The implementer now handles:
- Independent scope verification (scope_diff_gate.py)
- Acceptance testing verification
- API permission checks
- Security checks
- Memory promotion decisions
- Next-task prediction

Review artifacts in `reviews/` are no longer generated for new tasks.
The expanded execution receipt serves as the single verification record.
