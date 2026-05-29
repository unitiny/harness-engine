import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "engine" / "build_experience_archive.py"
SPEC = importlib.util.spec_from_file_location("build_experience_archive", MODULE_PATH)
build_experience_archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_experience_archive)


class ExperienceArchiveTests(unittest.TestCase):
    def test_builds_task_experience_record_with_state_and_outcome(self):
        tasks = [
            {
                "filename": "077-2026-05-21-document-public-microstructure-data-feasibility.md",
                "line_count": 100,
                "content": "\n".join(
                    [
                        "## Task Status",
                        "Task Status: DONE",
                        "- Task Stream: event-collection",
                        "## Risk Class",
                        "MEDIUM",
                    ]
                ),
            }
        ]
        receipts = [
            {
                "task_number": "077",
                "line_count": 20,
                "content": "Engineering verdict: PASS\nScientific verdict: RESEARCH_ONLY",
            }
        ]
        reviews = [
            {
                "task_number": "077",
                "line_count": 10,
                "content": "Verdict: PASS_WITH_RISK\nGate evidence: dev-gate PASS",
            }
        ]
        findings = [
            {
                "id": "me-blocked-077",
                "category": "missing_evaluator_coverage",
                "evidence_files": ["077-2026-05-21-document-public-microstructure-data-feasibility.md"],
            }
        ]

        records = build_experience_archive.build_experience_records(tasks, receipts, reviews, findings)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["task_number"], "077")
        self.assertEqual(record["task_status"], "DONE")
        self.assertEqual(record["task_stream"], "event-collection")
        self.assertEqual(record["review_verdict"], "PASS_WITH_RISK")
        self.assertEqual(record["engineering_verdict"], "PASS")
        self.assertEqual(record["scientific_verdict"], "RESEARCH_ONLY")
        self.assertEqual(record["finding_categories"], ["missing_evaluator_coverage"])

    def test_scores_proposals_with_penalty_for_supported_findings(self):
        proposals = [
            {
                "proposal_id": "prop-me-blocked-077",
                "promotion_state": "candidate_semantic_supported",
                "target_surface": "missing_evaluator_coverage",
            },
            {
                "proposal_id": "prop-tw-boilerplate",
                "promotion_state": "rejected_benign_exception",
                "target_surface": "token_waste",
            },
        ]
        findings = [
            {"category": "missing_evaluator_coverage"},
            {"category": "token_waste"},
            {"category": "token_waste"},
        ]

        scores = build_experience_archive.build_evolution_scores(proposals, findings)

        by_id = {s["proposal_id"]: s for s in scores}
        self.assertGreater(by_id["prop-me-blocked-077"]["evolution_score"], 0)
        self.assertLess(by_id["prop-tw-boilerplate"]["evolution_score"], 0)
        self.assertIn("human review", by_id["prop-me-blocked-077"]["next_action"])


if __name__ == "__main__":
    unittest.main()
