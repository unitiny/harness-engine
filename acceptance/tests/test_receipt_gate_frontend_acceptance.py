import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
DEV_HARNESS = ROOT / ".dev-harness"
sys.path.insert(0, str(DEV_HARNESS / "checks"))

import receipt_gate


def _write_frontend_task_and_receipt(tmp_path: Path, gate_evidence: str) -> Path:
    harness_root = tmp_path / "harness-engine" / ".dev-harness"
    task_root = harness_root / "task-briefs"
    receipt_root = harness_root / "execution-receipts"
    task_root.mkdir(parents=True)
    receipt_root.mkdir(parents=True)

    (task_root / "011-2026-05-26-dashboard.md").write_text(
        """
# Dashboard

## Task Status

Task Status: DONE

## Layer

frontend

## Scope Contract

Allowed files or paths:

- openclacky/lib/clacky/web/index.html
""",
        encoding="utf-8",
    )
    receipt_path = receipt_root / "011-2026-05-26-execution-receipt.md"
    receipt_path.write_text(
        f"""
# Execution Receipt

## Task

- Task brief: `harness-engine/.dev-harness/task-briefs/011-2026-05-26-dashboard.md`
- Task status before claim: UNCLAIMED
- Task status after completion: DONE
- Implementer: test
- Date: 2026-05-26

## Files Changed

- `openclacky/lib/clacky/web/index.html`

## Summary

- What changed: Dashboard UI.
- Why it matches the brief: Claimed complete.

## Acceptance Criteria Status

- [x] Criterion: Dashboard exists.

## Commands Run

```text
grep -c dashboard openclacky/lib/clacky/web/index.html
```

## Scope Check

- Changed only allowed files: yes
- Performed forbidden operations: no
- Dependency or lockfile changes: no
- Generated artifact rewrites: no
- Opportunistic cleanup/refactor: no

## Scope Independent Check

```text
[scope-diff-gate] PASS
```

## Acceptance Verification

- Criterion 1: grep returned 1.

## Deliverable File Existence Check

- `openclacky/lib/clacky/web/index.html`: exists: yes, size: 100 bytes, content check: pass

## API Permission Check

N/A: no API changes in this task.
- Permission model checked: N/A
- Field filtering verified: N/A
- Tenant isolation confirmed: N/A

## Secret And Safety Check

- Secrets added or exposed: no
- Raw model output persisted: no
- Production data or credentials used in prompts: no
- Trust boundary violations: no
- Unauthorized tenant access: no
- AI permission gateway bypass: no

## Gate Evidence

```text
{gate_evidence}
```

## Verification Self-Assessment

- Diff inspected: yes
- Scope checked programmatically (scope_diff_gate.py): yes
- Receipt claims contradicted by diff: no

## Memory Promotion Decisions

- project-memory.md: no promotion needed: test
- decision-log.md: no promotion needed: test
- risk-register.md: no promotion needed: test
- skill-candidates.md: no promotion needed: test

## Next-Task Prediction

- Next task should observe a rendered browser page.
""",
        encoding="utf-8",
    )
    return receipt_path


def test_frontend_done_receipt_rejects_static_grep_only_gate(monkeypatch, tmp_path):
    receipt_path = _write_frontend_task_and_receipt(tmp_path, "[scope-diff-gate] PASS")
    harness_root = tmp_path / "harness-engine" / ".dev-harness"
    monkeypatch.setattr(receipt_gate, "find_harness_root", lambda: harness_root)

    with pytest.raises(SystemExit):
        receipt_gate.assert_receipt(receipt_path, harness_root / "task-briefs")


def test_frontend_done_receipt_accepts_playwright_five_layer_gate(monkeypatch, tmp_path):
    receipt_path = _write_frontend_task_and_receipt(
        tmp_path,
        """
acceptance_gate: PASS
Playwright browser acceptance executed
Five-layer acceptance: L1 L2 L3 L4 L5 PASS
""",
    )
    harness_root = tmp_path / "harness-engine" / ".dev-harness"
    monkeypatch.setattr(receipt_gate, "find_harness_root", lambda: harness_root)

    receipt_gate.assert_receipt(receipt_path, harness_root / "task-briefs")
