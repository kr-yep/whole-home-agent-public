"""M11 development-only failure-localization contract tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

from whole_home_agent.adapters.torchvision_coco import TorchvisionDiagnosticProposal
from whole_home_agent.model import SourcePosition, TimestampBasis
from whole_home_agent.perception import BoundingBox, GroundTruthObject


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "run_vost_m11_failure_localization.py"
SPEC = importlib.util.spec_from_file_location("run_vost_m11_failure_localization", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
TOOL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TOOL
SPEC.loader.exec_module(TOOL)


class M11FailureLocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = TOOL.load_contract()
        cls.position = SourcePosition(
            source_sequence=0,
            source_offset=0,
            timestamp_basis=TimestampBasis.SOURCE_FRAME_INDEX,
            frame_index=0,
        )
        cls.target = GroundTruthObject(
            entity_id="vost-target-1",
            label="bottle",
            bbox=BoundingBox(0.0, 0.0, 10.0, 10.0),
        )

    def proposal(self, score: float, bbox: BoundingBox) -> TorchvisionDiagnosticProposal:
        return TorchvisionDiagnosticProposal(
            label="bottle",
            confidence=score,
            bbox=bbox,
            position=self.position,
        )

    def test_contract_is_frozen_to_development_and_pinned_inputs(self):
        contract = self.contract
        self.assertEqual(contract.source_sequence_id, "3518_unscrew_bottle")
        self.assertEqual(contract.source_split, "development")
        self.assertEqual(contract.reserved_sequence_id, "3510_unscrew_bottle")
        self.assertEqual(contract.diagnostic_score_floor, 0.05)
        self.assertEqual(contract.product_confidence_threshold, 0.25)
        self.assertEqual(contract.expected_m10_matched_frames, 10)

    def test_visible_target_categories_are_mutually_exclusive(self):
        cases = (
            ((), "no_bottle_proposal"),
            (
                (self.proposal(0.10, BoundingBox(0.0, 0.0, 10.0, 10.0)),),
                "confidence_filtered_proposal",
            ),
            (
                (self.proposal(0.80, BoundingBox(20.0, 20.0, 30.0, 30.0)),),
                "localization_miss",
            ),
            (
                (self.proposal(0.80, BoundingBox(0.0, 0.0, 10.0, 10.0)),),
                "matched",
            ),
        )
        for proposals, expected in cases:
            with self.subTest(expected=expected):
                category, _ = TOOL.classify_visible_target(
                    self.target,
                    proposals,
                    contract=self.contract,
                )
                self.assertEqual(category, expected)

    def test_detector_failure_has_priority_when_match_gate_fails(self):
        decision = TOOL.select_next_candidate(
            {
                "target_absent_or_void": 0,
                "no_bottle_proposal": 30,
                "confidence_filtered_proposal": 5,
                "localization_miss": 5,
                "matched": 10,
            },
            visible_target_frames=50,
            oracle_id_switches=99,
            oracle_fragmentations=99,
            contract=self.contract,
        )
        self.assertEqual(decision["bottleneck"], "no_bottle_proposal")
        self.assertEqual(
            decision["candidate"],
            "SCREEN_BOTTLE_SPECIALIST_DETECTOR_ON_DEVELOPMENT",
        )
        self.assertTrue(decision["detector_priority_applied"])
        self.assertFalse(decision["oracle_tracker_passed"])

    def test_oracle_tracker_is_selected_only_after_detector_match_gate(self):
        decision = TOOL.select_next_candidate(
            {
                "target_absent_or_void": 0,
                "no_bottle_proposal": 5,
                "confidence_filtered_proposal": 2,
                "localization_miss": 3,
                "matched": 40,
            },
            visible_target_frames=50,
            oracle_id_switches=2,
            oracle_fragmentations=0,
            contract=self.contract,
        )
        self.assertEqual(decision["bottleneck"], "oracle_tracker")
        self.assertEqual(
            decision["candidate"], "SCREEN_TRACKER_REPLACEMENT_WITH_ORACLE_BOXES"
        )
        self.assertFalse(decision["detector_priority_applied"])


if __name__ == "__main__":
    unittest.main()
