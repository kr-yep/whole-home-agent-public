"""Frozen no-media D1 target-label oracle contract for M16."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m16-target-label-oracle-v1.toml"


class M16TargetLabelOracleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_units_and_complete_frame_denominator_are_frozen(self):
        units = self.document["units"]
        self.assertEqual(units["detection"], "FRAME_BY_PERSISTENT_OBJECT_INSTANCE")
        self.assertEqual(
            units["false_positive_denominator"], "ALL_AND_ONLY_SCORED_FRAMES"
        )
        frame = self.document["frame_contract"]
        self.assertTrue(frame["complete_unique_frame_records_required"])
        self.assertEqual(frame["prediction_on_unknown_frame"], "REJECT")

    def test_visibility_and_identity_rules_do_not_invent_negatives(self):
        instance = self.document["instance_contract"]
        self.assertEqual(instance["scored_visibility_states"], ["VISIBLE", "TRUNCATED"])
        self.assertNotIn("UNKNOWN", instance["scored_visibility_states"])
        self.assertEqual(instance["same_identity_different_payload"], "REJECT_CONFLICT")
        self.assertEqual(
            self.document["frame_contract"]["negative_frame"],
            "SCORED_FRAME_WITH_ZERO_SCORABLE_TARGETS",
        )

    def test_metrics_and_hostile_cases_are_exact(self):
        metrics = self.document["metrics"]
        self.assertEqual(len(metrics["iou_thresholds"]), 10)
        self.assertEqual(metrics["small_area_lower_fraction_inclusive"], 0.001)
        self.assertEqual(metrics["small_area_upper_fraction_exclusive"], 0.01)
        self.assertEqual(
            [item["case_id"] for item in self.document["metric_cases"]],
            [
                "perfect",
                "empty",
                "duplicate",
                "wrong_class",
                "bad_localization",
                "negative_frame_false_positive",
            ],
        )
        self.assertEqual(
            {item["case_id"] for item in self.document["rejection_cases"]},
            {
                "prediction_on_unknown_frame",
                "duplicate_frame_identity",
                "same_instance_different_label",
                "split_group_leakage",
            },
        )

    def test_every_source_group_dimension_is_split_protected(self):
        protected = set(self.document["split_contract"]["protected_group_fields"])
        self.assertEqual(
            protected,
            {
                "participant_id",
                "house_room_id",
                "session_id",
                "source_sequence_id",
                "camera_time_group_id",
                "synchronized_view_group_id",
            },
        )
        self.assertFalse(
            self.document["split_contract"]["adjacent_frame_random_split_allowed"]
        )

    def test_all_media_model_claim_and_operation_boundaries_are_false(self):
        self.assertTrue(
            all(value is False for value in self.document["boundaries"].values())
        )
        self.assertFalse(self.document["transition_contract"]["product_movement_candidate"])
        self.assertFalse(self.document["transition_contract"]["claim_authority"])


if __name__ == "__main__":
    unittest.main()
