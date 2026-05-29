import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ANALYZE_PATH = Path(__file__).resolve().parents[1] / "engine" / "analyze-gaps.py"
ANALYZE_SPEC = importlib.util.spec_from_file_location("analyze_gaps", ANALYZE_PATH)
analyze_gaps = importlib.util.module_from_spec(ANALYZE_SPEC)
ANALYZE_SPEC.loader.exec_module(analyze_gaps)

COLLECT_PATH = Path(__file__).resolve().parents[1] / "engine" / "collect-signals.py"
COLLECT_SPEC = importlib.util.spec_from_file_location("collect_signals", COLLECT_PATH)
collect_signals = importlib.util.module_from_spec(COLLECT_SPEC)
COLLECT_SPEC.loader.exec_module(collect_signals)

PACKET_PATH = Path(__file__).resolve().parents[1] / "engine" / "build-evidence-packets.py"
PACKET_SPEC = importlib.util.spec_from_file_location("build_evidence_packets", PACKET_PATH)
build_evidence_packets = importlib.util.module_from_spec(PACKET_SPEC)
PACKET_SPEC.loader.exec_module(build_evidence_packets)

REPORT_PATH = Path(__file__).resolve().parents[1] / "engine" / "render-report.py"
REPORT_SPEC = importlib.util.spec_from_file_location("render_report", REPORT_PATH)
render_report = importlib.util.module_from_spec(REPORT_SPEC)
REPORT_SPEC.loader.exec_module(render_report)


class ToolEfficiencyDetectionTests(unittest.TestCase):
    def test_detects_repeated_bash_quoting_failures_in_console_log(self):
        console = """
  [10] Bash
  [INPUT]
    {"command":"python \\"harness-engine/.dev-harness/scripts/new_task_brief.py\\" --Title \\"Prepare\\" --Goal \\"long ..."}
  [TOOL OUTPUT: ERROR]
    Exit code 2
    /usr/bin/bash: -c: line 1: unexpected EOF while looking for matching `''
  [11] Bash
  [INPUT]
    {"command":"python - <<'PY'\\nimport subprocess\\nPY"}
  [TOOL OUTPUT: ERROR]
    Exit code 2
    /usr/bin/bash: -c: line 67: unexpected EOF while looking for matching `''
  [12] Bash
  [INPUT]
    {"command":"python \\"harness-engine/.dev-harness/scripts/new_task_brief.py\\" --Title \\"Prepare\\""}
  [TOOL OUTPUT]
    [new-task-brief] wrote file
"""
        logs = [
            {
                "path": "automation/logs/run-x/round-001/task_writer/console.log",
                "role": "task_writer",
                "run_id": "run-x",
                "content": console,
            }
        ]

        findings = analyze_gaps.detect_tool_efficiency_risks(logs)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["category"], "tool_efficiency_risk")
        self.assertEqual(finding["gap_type"], "bad_tool_policy")
        self.assertIn("Bash quoting", finding["title"])
        self.assertIn("[10] Bash", finding["evidence"])
        self.assertIn("new_task_brief.py", finding["proposed_action"])

    def test_detects_generic_tool_output_error_in_console_log(self):
        console = """
  [5] Read
  [INPUT]
    {"file_path":"missing.md"}
  [TOOL OUTPUT: ERROR]
    File does not exist.
  [6] Grep
  [INPUT]
    {"pattern":"task","path":"harness-engine/.dev-harness"}
  [TOOL OUTPUT]
    ok
"""
        logs = [
            {
                "path": "automation/logs/run-y/round-002/implementer/console.log",
                "role": "implementer",
                "run_id": "run-y",
                "round_id": "round-002",
                "content": console,
            }
        ]

        findings = analyze_gaps.detect_tool_efficiency_risks(logs)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["category"], "tool_efficiency_risk")
        self.assertEqual(finding["gap_type"], "bad_tool_policy")
        self.assertIn("[TOOL OUTPUT: ERROR]", finding["title"])
        self.assertIn("File does not exist", finding["evidence"])
        self.assertIn("why devharness guidance allowed", finding["proposed_action"])

    def test_collects_bounded_console_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness_root = Path(tmp) / ".dev-harness"
            log_dir = harness_root / "automation" / "logs" / "run-1" / "round-001" / "task_writer"
            log_dir.mkdir(parents=True)
            (log_dir / "console.log").write_text("[1] Bash\n[TOOL OUTPUT]\nok", encoding="utf-8")

            logs = collect_signals.collect_automation_logs(harness_root, limit=3, max_chars=200)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["role"], "task_writer")
        self.assertIn("[1] Bash", logs[0]["content"])

    def test_collects_error_windows_even_when_full_log_is_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness_root = Path(tmp) / ".dev-harness"
            log_dir = harness_root / "automation" / "logs" / "run-1" / "round-001" / "task_writer"
            log_dir.mkdir(parents=True)
            early_error = "\n".join(
                [
                    "[10] Bash",
                    "[TOOL OUTPUT: ERROR]",
                    "Exit code 2",
                    "/usr/bin/bash: -c: line 1: unexpected EOF while looking for matching `''",
                ]
            )
            late_tail = "x" * 500
            (log_dir / "console.log").write_text(early_error + "\n" + late_tail, encoding="utf-8")

            logs = collect_signals.collect_automation_logs(harness_root, limit=3, max_chars=80)

        self.assertTrue(logs[0]["truncated_to_tail"])
        self.assertIn("error_windows", logs[0])
        self.assertIn("unexpected EOF", logs[0]["content"])

    def test_tool_efficiency_finding_gets_semantic_question_and_report_section(self):
        finding = {
            "id": "ter-bash-quoting-run-1-task_writer",
            "category": "tool_efficiency_risk",
            "gap_type": "bad_tool_policy",
            "severity": "high",
            "title": "task_writer repeated Bash quoting failures before generator success",
            "evidence": "[10] Bash\nunexpected EOF\n[11] Bash\nunexpected EOF",
            "evidence_files": ["automation/logs/run-1/round-001/task_writer/console.log"],
            "proposed_action": "Use a generator JSON/spec interface instead of long shell arguments.",
        }

        packet = build_evidence_packets.build_packet(finding, [], [], [])

        self.assertIn("tool-use trace", packet["question_for_llm"])
        self.assertIn("generator interface", packet["question_for_llm"])

        section = render_report.render_findings_section([finding], "tool_efficiency_risk")

        self.assertIn("Tool Efficiency Risks", section)
        self.assertIn("repeated Bash quoting", section)

    def test_evidence_packets_deduplicate_same_failure_shape_before_semantic_triage(self):
        findings = [
            {
                "id": f"ter-tool-output-error-run-1-round-00{i}-task_writer",
                "category": "tool_efficiency_risk",
                "gap_type": "bad_tool_policy",
                "severity": "medium",
                "title": "task_writer had repeated ls missing-directory errors",
                "evidence": "ls: cannot access 'tests/': No such file or directory",
                "evidence_files": [
                    f"E:/repo/harness-engine/.dev-harness/automation/logs/run-1/round-00{i}/task_writer/console.log"
                ],
                "proposed_action": "Use repo-root checks before probing optional paths.",
            }
            for i in range(1, 5)
        ]
        findings.append(
            {
                "id": "ter-tool-output-error-run-1-round-001-implementer",
                "category": "tool_efficiency_risk",
                "gap_type": "bad_tool_policy",
                "severity": "medium",
                "title": "implementer had file edit sequencing errors",
                "evidence": "File has not been read yet. Read it first before writing to it.",
                "evidence_files": [
                    "E:/repo/harness-engine/.dev-harness/automation/logs/run-1/round-001/implementer/console.log"
                ],
                "proposed_action": "Read target files before editing.",
            }
        )

        packets, budget = build_evidence_packets.build_all_packets_with_budget(
            findings,
            [],
            [],
            [],
            max_packets=5,
        )

        self.assertEqual(len(packets), 2)
        self.assertEqual(budget["input_findings"], 5)
        self.assertEqual(budget["deduped_findings"], 2)
        self.assertEqual(budget["semantic_calls_saved"], 3)
        self.assertEqual(budget["duplicate_groups"][0]["duplicates"], 3)
        self.assertEqual(packets[0]["dedupe_group"]["duplicate_count"], 3)

    def test_wrong_cwd_generator_error_gets_concrete_repair_action(self):
        console = """
  [115] Bash
  [INPUT]
    {"command":"python harness-engine/.dev-harness/scripts/new_task_brief.py --SpecFile spec.json"}
  [TOOL OUTPUT: ERROR]
    Exit code 2
    python.exe: can't open file 'C:\\Users\\dev\\projects\\my-project\\subdir\\harness-engine\\.dev-harness\\scripts\\new_task_brief.py': [Errno 2] No such file or directory
  [116] Bash
  [TOOL OUTPUT: ERROR]
    Exit code 1
    [new-task-brief] missing required fields: Title
"""
        logs = [
            {
                "path": "automation/logs/run-x/round-005/task_writer/console.log",
                "role": "task_writer",
                "run_id": "run-x",
                "round_id": "round-005",
                "content": console,
            }
        ]

        findings = analyze_gaps.detect_tool_efficiency_risks(logs)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["gap_type"], "wrong_working_directory")
        self.assertIn("wrong working directory", finding["title"])
        self.assertIn("repo-root absolute path", finding["proposed_action"])

    def test_scope_runtime_noise_error_gets_scope_diff_repair_action(self):
        console = """
  [200] Bash
  [INPUT]
    {"command":"python harness-engine/.dev-harness/checks/scope_diff_gate.py --TaskBrief task.md"}
  [TOOL OUTPUT: ERROR]
    Exit code 1
    [scope-diff-gate] changed files outside task allowed scope:
    - cockpit-api/tmp/cache/bootsnap/load-path-cache
    - harness-engine/.dev-harness/automation/auto_state.json
    - harness-engine/.dev-harness/automation/logs/run-1/latest.txt
    - openclacky
"""
        logs = [
            {
                "path": "automation/logs/run-x/round-005/implementer/console.log",
                "role": "implementer",
                "run_id": "run-x",
                "round_id": "round-005",
                "content": console,
            }
        ]

        findings = analyze_gaps.detect_tool_efficiency_risks(logs)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["gap_type"], "scope_runtime_noise")
        self.assertIn("runtime noise", finding["title"])
        self.assertIn("LOCAL_WORKSPACE_PREFIXES", finding["proposed_action"])

    def test_blind_file_read_gets_existence_precheck_action(self):
        console = """
  [91] Read
  [INPUT]
    {"file_path":"C:\\Users\\dev\\projects\\my-project\\harness-engine\\.dev-harness\\automation\\execution-receipts\\008-task.md"}
  [TOOL OUTPUT: ERROR]
    File does not exist. Note: your current working directory is C:\\Users\\dev\\projects\\my-project.
"""
        logs = [
            {
                "path": "automation/logs/run-z/round-005/task_writer/console.log",
                "role": "task_writer",
                "run_id": "run-z",
                "round_id": "round-005",
                "content": console,
            }
        ]

        findings = analyze_gaps.detect_tool_efficiency_risks(logs)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["gap_type"], "blind_file_read")
        self.assertIn("blind file read", finding["title"])
        self.assertIn("verify file exists", finding["proposed_action"])

    def test_relative_cd_missing_dir_gets_repo_root_action(self):
        console = """
  [14] Glob
  [INPUT]
    {"pattern":"cockpit-api/spec/requests/**/*.rb"}
  [TOOL OUTPUT: ERROR]
    Exit code 1
    /usr/bin/bash: line 1: cd: cockpit-api: No such file or directory
"""
        logs = [
            {
                "path": "automation/logs/run-z/round-001/task_writer/console.log",
                "role": "task_writer",
                "run_id": "run-z",
                "round_id": "round-001",
                "content": console,
            }
        ]

        findings = analyze_gaps.detect_tool_efficiency_risks(logs)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["gap_type"], "wrong_working_directory")
        self.assertIn("relative cd failed", finding["title"])
        self.assertIn("repo root", finding["proposed_action"])

    def test_acceptance_gate_failure_is_product_task_guidance(self):
        console = """
  [TOOL OUTPUT: ERROR]
    Acceptance Gate: FAIL
    Scenarios: 0 passed, 3 failed, 3 total
    [acceptance-gate] Failed scenario diagnostics:
      - scenario: 用户登录验证
        first_failed_step: 填写用户名
        reason: Action execution error: connection refused
"""
        logs = [
            {
                "path": "automation/logs/run-z/round-001/implementer/console.log",
                "role": "implementer",
                "run_id": "run-z",
                "round_id": "round-001",
                "content": console,
            }
        ]

        findings = analyze_gaps.detect_tool_efficiency_risks(logs)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["gap_type"], "product_acceptance_failure")
        self.assertIn("product acceptance failure", finding["title"])
        self.assertIn("current product task", finding["proposed_action"])
        self.assertNotIn("repair harness", finding["proposed_action"].lower())

    def test_current_run_status_uses_latest_run_metrics_without_role_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            signals_dir = Path(tmp)
            (signals_dir / "automation_logs.json").write_text(
                json.dumps([
                    {
                        "path": "automation/logs/run-old/round-005/task_writer/console.log",
                        "role": "task_writer",
                        "run_id": "run-old",
                        "error_windows": ["[TOOL OUTPUT: ERROR] old"],
                        "content": "[TOOL OUTPUT: ERROR] old",
                    }
                ]),
                encoding="utf-8",
            )
            (signals_dir / "run_metrics.json").write_text(
                json.dumps([
                    {
                        "run_id": "run-old",
                        "latest_mtime": 1,
                        "tool_error_count": 2,
                        "dev_gate_passed": True,
                    },
                    {
                        "run_id": "run-new",
                        "latest_mtime": 2,
                        "tool_error_count": 0,
                        "dev_gate_passed": True,
                    },
                ]),
                encoding="utf-8",
            )

            section = render_report.render_current_run_tool_status(
                signals_dir,
                [
                    {
                        "category": "tool_efficiency_risk",
                        "evidence_files": ["automation/logs/run-old/round-005/task_writer/console.log"],
                    }
                ],
            )

        self.assertIn("Latest run: `run-new`", section)
        self.assertIn("Latest run role logs collected: 0", section)
        self.assertIn("Latest run tool-error windows: 0", section)
        self.assertIn("CURRENT PASS", section)
        self.assertIn("Historical sampled tool findings: 1", section)


if __name__ == "__main__":
    unittest.main()
