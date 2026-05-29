import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "engine" / "render-report.py"
SPEC = importlib.util.spec_from_file_location("render_report", MODULE_PATH)
render_report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_report)


class RenderReportTests(unittest.TestCase):
    def test_rejected_semantic_findings_are_not_recommended_or_contracts(self):
        findings = [
            {
                "id": "tw-boilerplate-12345678",
                "category": "token_waste",
                "severity": "medium",
                "title": "Repeated boilerplate in 8 task briefs",
                "proposed_action": "Extract to a template or generator script",
            }
        ]
        semantic_summary = {
            "verdicts": [
                {
                    "finding_id": "tw-boilerplate-12345678",
                    "semantic_verdict": "false_positive",
                    "reason": "Required audit evidence is not token waste.",
                }
            ]
        }
        proposals_summary = {
            "total_proposals": 1,
            "proposal_files": [],
            "proposals_by_state": {"rejected_false_positive": 1},
            "actionable_proposals": [],
        }

        recommended = render_report.render_recommended_patch(
            findings, proposals_summary, semantic_summary
        )

        self.assertIn("No actionable findings", recommended)
        self.assertNotIn("Repeated boilerplate", recommended)

        with tempfile.TemporaryDirectory() as tmp:
            findings_path = Path(tmp) / "findings.json"
            findings_path.write_text("[]", encoding="utf-8")
            contracts = render_report.render_prediction_contracts(
                findings_path, proposals_summary
            )

        self.assertIn("No actionable findings", contracts)
        self.assertNotIn("Repeated boilerplate", contracts)

    def test_current_run_tool_status_separates_latest_run_from_historical_debt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            signals_dir = tmp_path / "signals" / "latest"
            meta_root = tmp_path / "meta"
            signals_dir.mkdir(parents=True)
            meta_root.mkdir()
            (signals_dir / "manifest.json").write_text(json.dumps({
                "tasks_collected": 0,
                "receipts_collected": 0,
                "reviews_collected": 0,
            }), encoding="utf-8")
            (signals_dir / "automation_logs.json").write_text(json.dumps([
                {
                    "run_id": "run-new",
                    "round_id": "round-001",
                    "role": "task_writer",
                    "path": "logs/run-new/round-001/task_writer/console.log",
                    "error_windows": [],
                    "content": "new_task_brief.py --SpecFile spec.json\n[TOOL OUTPUT]\nok",
                },
                {
                    "run_id": "run-old",
                    "round_id": "round-001",
                    "role": "task_writer",
                    "path": "logs/run-old/round-001/task_writer/console.log",
                    "error_windows": ["[TOOL OUTPUT: ERROR]\nold failure"],
                    "content": "[TOOL OUTPUT: ERROR]\nold failure",
                },
            ]), encoding="utf-8")
            findings = [
                {
                    "id": "ter-old",
                    "category": "tool_efficiency_risk",
                    "severity": "high",
                    "title": "old tool error",
                    "evidence_files": ["logs/run-old/round-001/task_writer/console.log"],
                    "proposed_action": "fix old",
                    "gap_type": "bad_tool_policy",
                }
            ]

            report = render_report.render_report(findings, None, None, signals_dir, meta_root)

        self.assertIn("## 1. Current Run Tool Status", report)
        self.assertIn("## 2. Runtime Profile", report)
        self.assertIn("Latest run: `run-new`", report)
        self.assertIn("Status: **CURRENT PASS**", report)
        self.assertIn("Historical sampled tool findings: 1", report)
        self.assertIn("Uses `new_task_brief.py --SpecFile`", report)

    def test_runtime_profile_renders_phase_hotspots_and_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            signals_dir = Path(tmp)
            (signals_dir / "runtime_trace.json").write_text(json.dumps({
                "latest_run_id": "run-123",
                "runs_analyzed": 2,
                "total_duration_ms": 200000,
                "critical_path": [
                    {"phase": "task_writer", "duration_ms": 120000, "status": "pass"},
                    {"phase": "reviewer", "duration_ms": 80000, "status": "fail"},
                ],
                "phase_summary": {
                    "task_writer": {
                        "span_count": 1,
                        "total_duration_ms": 120000,
                        "max_duration_ms": 120000,
                        "failure_count": 0,
                        "timeout_count": 0,
                    },
                    "reviewer": {
                        "span_count": 1,
                        "total_duration_ms": 80000,
                        "max_duration_ms": 80000,
                        "failure_count": 1,
                        "timeout_count": 0,
                    },
                },
            }), encoding="utf-8")

            section = render_report.render_runtime_profile(signals_dir)

        self.assertIn("Latest traced run: `run-123`", section)
        self.assertIn("Total traced duration: 200.0s", section)
        self.assertIn("task_writer", section)
        self.assertIn("reviewer", section)
        self.assertIn("failures=1", section)

    def test_token_budget_renders_semantic_call_savings(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta_root = Path(tmp)
            pkt_dir = meta_root / "evidence-packets" / "latest"
            pkt_dir.mkdir(parents=True)
            (pkt_dir / "manifest.json").write_text(json.dumps({
                "total_findings": 5,
                "total_packets": 2,
                "token_budget": {
                    "semantic_calls_saved": 3,
                    "input_findings": 5,
                    "deduped_findings": 2,
                    "semantic_calls_planned": 2,
                    "duplicate_groups": [
                        {
                            "representative_finding_id": "ter-tool-output-error-run-1-round-001-task_writer",
                            "duplicates": 3,
                        }
                    ],
                },
            }), encoding="utf-8")

            section = render_report.render_token_budget(meta_root)

        self.assertIn("Semantic calls planned: 2", section)
        self.assertIn("Duplicate semantic calls saved: 3", section)
        self.assertIn("ter-tool-output-error-run-1-round-001-task_writer", section)

    def test_regressed_contract_replay_overrides_lower_priority_recommendation(self):
        findings = [
            {
                "id": "tw-boilerplate-12345678",
                "category": "token_waste",
                "severity": "medium",
                "title": "Repeated boilerplate",
                "proposed_action": "Extract boilerplate.",
            },
            {
                "id": "ter-tool-output-error-run-x",
                "category": "tool_efficiency_risk",
                "severity": "medium",
                "title": "tool errors regressed",
                "proposed_action": "Fix tool policy.",
            },
        ]
        proposals_summary = {
            "actionable_proposals": [
                {
                    "proposal_id": "prop-tw-boilerplate-12345678",
                    "target_surface": "token_waste",
                    "promotion_state": "candidate_rule_only",
                    "proposed_change": "Extract boilerplate.",
                    "rationale": "Repeated block.",
                },
                {
                    "proposal_id": "prop-ter-tool-output-error-run-x",
                    "target_surface": "tool_efficiency_risk",
                    "promotion_state": "candidate_rule_only",
                    "proposed_change": "Fix tool policy.",
                    "rationale": "Tool errors increased.",
                },
            ]
        }
        replay_results = [
            {
                "proposal_id": "prop-ter-tool-output-error-run-x",
                "metric_name": "tool_error_count_per_run",
                "baseline_value": 1.2,
                "current_value": 3.6,
                "relative_change": 2.0,
                "verdict": "regressed",
            }
        ]

        recommended = render_report.render_recommended_patch(
            findings,
            proposals_summary,
            None,
            replay_results,
        )

        self.assertIn("Priority: REGRESSED CONTRACT", recommended)
        self.assertIn("prop-ter-tool-output-error-run-x", recommended)
        self.assertIn("tool_error_count_per_run 1.2 -> 3.6", recommended)
        self.assertNotIn("prop-tw-boilerplate", recommended)


if __name__ == "__main__":
    unittest.main()
