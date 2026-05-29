import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "engine" / "analyze-gaps.py"
SPEC = importlib.util.spec_from_file_location("analyze_gaps", MODULE_PATH)
analyze_gaps = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analyze_gaps)


class AnalyzeGapsTests(unittest.TestCase):
    def test_repeated_audit_gate_blocks_are_not_token_waste(self):
        audit_block = "\n".join(
            [
                "```powershell",
                "powershell.exe -NoProfile -ExecutionPolicy Bypass -File harness-engine/.dev-harness/checks/dev-gate.ps1 -SkipRust -Fast",
                "```",
                "",
                "- Receipt artifact: harness-engine/.dev-harness/receipts/001.md",
                "- Review artifact: harness-engine/.dev-harness/reviews/001.md",
                "- Gate evidence: dev-gate PASS",
            ]
        )
        tasks = [
            {"filename": "001-task.md", "content": audit_block},
            {"filename": "002-task.md", "content": audit_block},
        ]

        findings = analyze_gaps.detect_repeated_boilerplate(tasks)

        self.assertEqual(findings, [])

    def test_detects_slow_runtime_phase_as_latency_finding(self):
        runtime_trace = {
            "latest_run_id": "run-slow",
            "phase_summary": {
                "task_writer": {
                    "span_count": 1,
                    "total_duration_ms": 900000,
                    "max_duration_ms": 900000,
                    "failure_count": 0,
                    "timeout_count": 0,
                },
                "implementer": {
                    "span_count": 1,
                    "total_duration_ms": 60000,
                    "max_duration_ms": 60000,
                    "failure_count": 0,
                    "timeout_count": 0,
                },
            },
            "total_duration_ms": 960000,
        }

        findings = analyze_gaps.detect_runtime_trace_risks(runtime_trace)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["category"], "runtime_observability_risk")
        self.assertEqual(finding["gap_type"], "phase_latency_hotspot")
        self.assertIn("task_writer", finding["title"])
        self.assertIn("critical path", finding["proposed_action"])

    def test_analyze_gaps_reads_runtime_trace_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            signals_dir = Path(tmp)
            for name, value in {
                "tasks.json": [],
                "receipts.json": [],
                "reviews.json": [],
                "automation_logs.json": [],
                "policy_refs.json": {},
            }.items():
                (signals_dir / name).write_text(json.dumps(value), encoding="utf-8")
            (signals_dir / "runtime_trace.json").write_text(json.dumps({
                "latest_run_id": "run-fail",
                "phase_summary": {
                    "reviewer": {
                        "span_count": 2,
                        "total_duration_ms": 1000,
                        "max_duration_ms": 700,
                        "failure_count": 1,
                        "timeout_count": 0,
                    },
                    "implementer": {
                        "span_count": 1,
                        "total_duration_ms": 9000,
                        "max_duration_ms": 9000,
                        "failure_count": 0,
                        "timeout_count": 0,
                    }
                },
                "total_duration_ms": 20000,
            }), encoding="utf-8")

            findings = analyze_gaps.analyze_gaps(signals_dir)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["gap_type"], "phase_reliability_failure")


if __name__ == "__main__":
    unittest.main()
