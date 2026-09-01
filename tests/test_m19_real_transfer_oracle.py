"""Frozen no-download real transfer-oracle rules for M19."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m19-real-transfer-oracle-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m19-real-transfer-oracle-result-v1.toml"


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


class M19RealTransferOracleResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_candidate_matrix_is_exact_and_three_state(self):
        candidates = self.result["candidates"]
        self.assertEqual(list(candidates), self.contract["candidates"])
        required = set(self.contract["required_gate_order"])
        for candidate in candidates.values():
            self.assertEqual(set(candidate["gates"]), required)
            self.assertLessEqual(
                set(candidate["gates"].values()), {"PASS", "FAIL", "UNKNOWN"}
            )

    def test_eligibility_is_the_and_of_every_fatal_gate(self):
        computed = [
            name
            for name, candidate in self.result["candidates"].items()
            if all(status == "PASS" for status in candidate["gates"].values())
        ]
        self.assertEqual(computed, self.result["eligible_candidates"])
        self.assertEqual(computed, ["homebreweddb", "ycb-video"])
        self.assertEqual(len(computed), self.result["eligible_count"])

    def test_frozen_tiebreak_selects_only_the_smaller_ycb_route(self):
        self.assertTrue(self.result["tie_break_applied"])
        self.assertEqual(self.result["tie_break_decisive_stage"], 3)
        self.assertEqual(self.result["selected_candidate"], "ycb-video")
        self.assertEqual(
            self.result["selection"]["next_authority"],
            self.contract["selection"]["selected_candidate_next_authority"],
        )
        self.assertEqual(
            self.result["translation"]["relation_policy"],
            "NO_REFERENCE_TRANSITION_OR_RELATION_IS_EMITTED",
        )

    def test_unknown_is_not_rewritten_as_failure(self):
        gmu = self.result["candidates"]["gmu-kitchens"]["gates"]
        self.assertEqual(gmu["stable_official_acquisition_route"], "FAIL")
        self.assertEqual(
            gmu["official_terms_cover_noncommercial_evaluation_and_training"],
            "UNKNOWN",
        )
        self.assertTrue(self.result["unknown_is_selection_ineligible"])

    def test_result_downloaded_nothing_and_preserves_every_boundary(self):
        verification = self.result["verification"]
        self.assertEqual(verification["archive_media_or_annotation_download_count"], 0)
        self.assertEqual(verification["model_detector_or_tracker_load_count"], 0)
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
