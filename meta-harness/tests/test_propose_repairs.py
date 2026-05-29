import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "engine" / "propose-repairs.py"
SPEC = importlib.util.spec_from_file_location("propose_repairs", MODULE_PATH)
propose_repairs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(propose_repairs)


class ProposeRepairsTests(unittest.TestCase):
    def test_actionable_summary_excludes_rejected_proposals(self):
        proposals = [
            {
                "proposal_id": "prop-supported",
                "source_findings": ["dq-no-gate-001"],
                "target": "checker",
                "target_surface": "delivery_quality_risk",
                "promotion_state": "candidate_semantic_supported",
                "proposed_change": "Require gate evidence.",
                "rationale": "Gate evidence is mechanically detectable.",
                "prediction_contract": {"measurable_signal": "fewer missing gate findings"},
            },
            {
                "proposal_id": "prop-rejected",
                "source_findings": ["tw-boilerplate-12345678"],
                "target": "instruction",
                "target_surface": "token_waste",
                "promotion_state": "rejected_false_positive",
                "proposed_change": "Extract audit boilerplate.",
                "rationale": "Rejected by semantic triage.",
                "prediction_contract": {},
            },
        ]
        written = [
            Path("harness-engine/meta-harness/proposals/candidate/prop-supported.md"),
            Path("harness-engine/meta-harness/proposals/rejected/prop-rejected.md"),
        ]

        actionable = propose_repairs.summarize_actionable_proposals(proposals, written)

        self.assertEqual([p["proposal_id"] for p in actionable], ["prop-supported"])
        self.assertEqual(actionable[0]["target"], "checker")
        self.assertIn("prop-supported.md", actionable[0]["proposal_file"])

    def test_tool_efficiency_finding_targets_tool_policy(self):
        finding = {
            "category": "tool_efficiency_risk",
            "gap_type": "bad_tool_policy",
            "proposed_action": "Use a generator JSON/spec interface instead of long shell arguments.",
        }

        self.assertEqual(propose_repairs.select_target(finding), "tool_policy")


if __name__ == "__main__":
    unittest.main()
