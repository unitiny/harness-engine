import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


COLLECT_PATH = Path(__file__).resolve().parents[1] / "engine" / "collect-signals.py"
COLLECT_SPEC = importlib.util.spec_from_file_location("collect_signals", COLLECT_PATH)
collect_signals = importlib.util.module_from_spec(COLLECT_SPEC)
COLLECT_SPEC.loader.exec_module(collect_signals)

REPLAY_PATH = Path(__file__).resolve().parents[1] / "engine" / "replay-contracts.py"
REPLAY_SPEC = importlib.util.spec_from_file_location("replay_contracts", REPLAY_PATH)
replay_contracts = importlib.util.module_from_spec(REPLAY_SPEC)
REPLAY_SPEC.loader.exec_module(replay_contracts)

REPORT_PATH = Path(__file__).resolve().parents[1] / "engine" / "render-report.py"
REPORT_SPEC = importlib.util.spec_from_file_location("render_report", REPORT_PATH)
render_report = importlib.util.module_from_spec(REPORT_SPEC)
REPORT_SPEC.loader.exec_module(render_report)


class ContractReplayRunMetricsTests(unittest.TestCase):
    def test_collects_run_metrics_from_all_run_console_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness_root = Path(tmp) / ".dev-harness"
            old_log = harness_root / "automation" / "logs" / "run-001" / "round-001" / "task_writer"
            new_log = harness_root / "automation" / "logs" / "run-002" / "round-001" / "task_writer"
            old_log.mkdir(parents=True)
            new_log.mkdir(parents=True)
            (old_log / "console.log").write_text(
                "[TOOL OUTPUT: ERROR]\nExit code 1\n[TIMEOUT]\n__AUTO_HARNESS_EXIT_CODE:1",
                encoding="utf-8",
            )
            (new_log / "console.log").write_text(
                "new_task_brief.py --SpecFile spec.json\n[dev-gate] PASS\n__AUTO_HARNESS_EXIT_CODE:0",
                encoding="utf-8",
            )

            metrics = collect_signals.collect_run_metrics(harness_root)

        self.assertEqual([m["run_id"] for m in metrics], ["run-001", "run-002"])
        self.assertEqual(metrics[0]["tool_error_count"], 1)
        self.assertEqual(metrics[0]["timeout_count"], 1)
        self.assertEqual(metrics[1]["tool_error_count"], 0)
        self.assertTrue(metrics[1]["used_spec_file"])
        self.assertTrue(metrics[1]["dev_gate_passed"])

    def test_collects_runtime_trace_from_role_console_file_times(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness_root = Path(tmp) / ".dev-harness"
            role_dir = harness_root / "automation" / "logs" / "run-001" / "round-001" / "task_writer"
            role_dir.mkdir(parents=True)
            console = role_dir / "console.log"
            console.write_text("[TOOL OUTPUT]\nok\n__AUTO_HARNESS_EXIT_CODE:0", encoding="utf-8")

            trace = collect_signals.collect_runtime_trace(harness_root)

        self.assertEqual(trace["runs_analyzed"], 1)
        self.assertEqual(trace["latest_run_id"], "run-001")
        self.assertEqual(len(trace["spans"]), 1)
        span = trace["spans"][0]
        self.assertEqual(span["phase"], "task_writer")
        self.assertEqual(span["status"], "pass")
        self.assertGreaterEqual(span["duration_ms"], 1)
        self.assertEqual(trace["phase_summary"]["task_writer"]["span_count"], 1)

    def test_replays_tool_efficiency_contract_against_run_metrics_trend(self):
        proposals = [
            {
                "proposal_id": "prop-tool",
                "target_surface": "tool_efficiency_risk",
                "prediction_contract": {
                    "expected_future_behavior": "Agents avoid repeated failing tool-call patterns",
                    "measurable_signal": "[TOOL OUTPUT: ERROR] count decreases",
                },
            }
        ]
        run_metrics = [
            {"run_id": "run-1", "tool_error_count": 4, "timeout_count": 1},
            {"run_id": "run-2", "tool_error_count": 3, "timeout_count": 0},
            {"run_id": "run-3", "tool_error_count": 0, "timeout_count": 0},
            {"run_id": "run-4", "tool_error_count": 0, "timeout_count": 0},
        ]

        results = replay_contracts.replay_contracts_with_run_metrics(
            proposals,
            run_metrics,
            {"contract_replay": {"baseline_window": 2, "replay_window": 2, "min_samples_for_verdict": 2}},
        )

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["verdict"], "improved")
        self.assertEqual(result["metric_name"], "tool_error_count_per_run")
        self.assertEqual(result["baseline_value"], 3.5)
        self.assertEqual(result["current_value"], 0.0)

    def test_report_renders_run_metric_replay_summary(self):
        replay_latest = {
            "results": [
                {
                    "proposal_id": "prop-tool",
                    "metric_name": "tool_error_count_per_run",
                    "baseline_value": 3.5,
                    "current_value": 0.0,
                    "relative_change": -1.0,
                    "verdict": "improved",
                    "run_metric_window": {
                        "baseline_runs": ["run-1", "run-2"],
                        "current_runs": ["run-3", "run-4"],
                    },
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            meta_root = Path(tmp)
            results_dir = meta_root / "replays" / "results"
            results_dir.mkdir(parents=True)
            (results_dir / "replay-latest.json").write_text(json.dumps(replay_latest), encoding="utf-8")

            section = render_report.render_contract_replay(meta_root)

        self.assertIn("tool_error_count_per_run", section)
        self.assertIn("run-1, run-2 -> run-3, run-4", section)
        self.assertIn("IMPROVED", section)


if __name__ == "__main__":
    unittest.main()
