"""Frozen no-download real transfer-oracle rules for M19."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m19-real-transfer-oracle-v1.toml"


class M19RealTransferOracleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exactly_three_real_candidates_and_stop_are_frozen(self):
        self.assertEqual(
            self.document["candidates"],
            ["gmu-kitchens", "homebreweddb", "ycb-video"],
        )
        self.assertEqual(
            self.document["stop_baseline"],
            "STOP_NO_REAL_TRANSFER_ORACLE",
        )

    def test_localization_completeness_and_small_target_gates_are_fatal(self):
        required = self.document["required_gate_order"]
        for gate in (
            "per_frame_instance_boxes_or_masks",
            "annotation_completeness_or_safe_scoring_rule",
            "small_target_0_1_to_1_percent_verification_path",
            "negative_and_unknown_semantics_translatable",
            "exact_m16_d1_translation_feasible",
        ):
            self.assertIn(gate, required)
        self.assertFalse(self.document["evidence_rules"]["unlabelled_objects_may_be_treated_as_negative"])

    def test_cost_split_and_single_selection_are_bounded(self):
        self.assertEqual(self.document["cost"]["maximum_minimal_evaluation_subset_gib"], 5.0)
        self.assertEqual(self.document["cost"]["first_slice_max_working_hours"], 8)
        self.assertFalse(self.document["split_integrity"]["protected_factor_cross_split_allowed"])
        selection = self.document["selection"]
        self.assertTrue(selection["all_required_gates_must_pass"])
        self.assertTrue(selection["select_at_most_one"])

    def test_research_cannot_download_run_or_operate(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertFalse(self.document["evidence_rules"]["metric_or_model_result_allowed"])


if __name__ == "__main__":
    unittest.main()
