"""Frozen no-media target-domain substrate rules for M15."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m15-target-domain-substrate-v1.toml"


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


if __name__ == "__main__":
    unittest.main()
