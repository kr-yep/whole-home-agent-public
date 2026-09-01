"""Frozen no-media target-domain substrate rules for M15."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m15-target-domain-substrate-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m15-target-domain-substrate-result-v1.toml"


class M15SubstrateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exactly_three_candidates_and_stop_are_frozen(self):
        self.assertEqual(
            self.document["candidates"],
            ["home-action-genome", "cad-120", "watch-n-patch"],
        )
        self.assertEqual(self.document["stop_baseline"], "STOP_OR_PIVOT")
        self.assertTrue(self.document["selection"]["exactly_one_candidate_required"])

    def test_required_data_evidence_is_not_weakened_to_action_labels(self):
        rules = self.document["eligibility"]
        self.assertTrue(rules["fixed_or_explicit_exocentric_indoor_view_required"])
        self.assertTrue(rules["temporally_ordered_source_video_required"])
        self.assertTrue(rules["per_frame_instance_localization_required"])
        self.assertTrue(rules["interaction_or_affordance_signal_required"])
        evidence = self.document["evidence_rules"]
        self.assertFalse(evidence["action_labels_without_instance_localization_are_sufficient"])
        self.assertFalse(evidence["skeletons_without_object_localization_are_sufficient"])
        self.assertFalse(evidence["egocentric_only_is_sufficient"])

    def test_relation_truth_is_a_visible_gap_not_a_detector_data_shortcut(self):
        self.assertFalse(
            self.document["estimand"]["exact_containment_or_zone_truth_required_for_detector_training"]
        )
        gaps = self.document["important_non_blocking_gaps"]
        self.assertEqual(gaps["container_relation_truth"], "REPORT_SEPARATELY")
        self.assertEqual(gaps["zone_relation_truth"], "REPORT_SEPARATELY")

    def test_all_operational_and_media_boundaries_remain_disabled(self):
        self.assertTrue(
            all(value is False for value in self.document["boundaries"].values())
        )


class M15SubstrateResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_candidate_matrix_is_exact_and_three_state(self):
        candidates = self.result["candidates"]
        self.assertEqual(list(candidates), self.contract["candidates"])
        required = set(self.result["required_gate_order"])
        self.assertTrue(required)
        for candidate in candidates.values():
            self.assertEqual(set(candidate["gates"]), required)
            self.assertLessEqual(set(candidate["gates"].values()), {"PASS", "FAIL", "UNKNOWN"})

    def test_eligibility_is_the_and_of_direct_passes(self):
        computed = [
            name
            for name, candidate in self.result["candidates"].items()
            if all(status == "PASS" for status in candidate["gates"].values())
        ]
        self.assertEqual(computed, self.result["eligible_candidates"])
        self.assertEqual(len(computed), self.result["eligible_count"])
        self.assertEqual(computed, [])

    def test_unknown_is_not_rewritten_as_pass_or_factual_fail(self):
        self.assertTrue(self.result["unknown_is_selection_ineligible"])
        self.assertEqual(
            self.result["interpretation"]["unknown_means"],
            "NOT_ESTABLISHED_IN_ACCESSIBLE_OFFICIAL_SOURCES_CHECKED",
        )
        self.assertTrue(
            any(
                status == "UNKNOWN"
                for candidate in self.result["candidates"].values()
                for status in candidate["gates"].values()
            )
        )

    def test_zero_candidate_branch_matches_frozen_decision(self):
        self.assertEqual(self.result["selected_candidate"], "NONE")
        self.assertFalse(self.result["tie_break_applied"])
        self.assertEqual(
            self.result["decision"],
            self.contract["selection"]["zero_eligible_decision"],
        )

    def test_result_preserves_every_disabled_boundary(self):
        self.assertTrue(
            all(value is False for value in self.result["boundaries"].values())
        )


if __name__ == "__main__":
    unittest.main()
