"""Frozen pre-annotation contract for the M25 dual-area diagnostic."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M16 = ROOT / "configs" / "evaluation" / "m16-target-label-oracle-v1.toml"
M21 = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"
M24 = ROOT / "configs" / "evaluation" / "m24-ycbv-cross-scene-d1-materialization-result-v1.toml"
CONTRACT = ROOT / "configs" / "evaluation" / "m25-ycbv-small-bbox-alignment-v1.toml"


class M25ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m16 = tomllib.loads(M16.read_text(encoding="utf-8"))
        cls.m21 = tomllib.loads(M21.read_text(encoding="utf-8"))
        cls.m24 = tomllib.loads(M24.read_text(encoding="utf-8"))
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_is_frozen_before_reread_and_inherits_exact_source(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_REAL_ANNOTATION_REREAD")
        self.assertEqual(self.document["source_revision"], self.m21["source_revision"])
        self.assertEqual(self.document["source_archive_root"], self.m21["source_archive_root"])
        expected = {
            item["name"]: (item["bytes"], item["sha256"], item["source_root"])
            for item in self.m21["archive"]
        }
        actual = {
            item["name"]: (item["bytes"], item["sha256"], item["source_root"])
            for item in self.document["archive"]
        }
        self.assertEqual(actual, expected)
        self.assertEqual(self.document["expected_unique_target_frame_count"], 900)
        self.assertEqual(self.document["expected_annotation_member_count"], 37)

    def test_dual_area_rule_matches_m16_bucket_on_the_same_annotation(self):
        predicate = self.document["positive_predicate"]
        metrics = self.m16["metrics"]
        self.assertEqual(
            predicate["minimum_area_fraction_inclusive"],
            metrics["small_area_lower_fraction_inclusive"],
        )
        self.assertEqual(
            predicate["maximum_area_fraction_exclusive"],
            metrics["small_area_upper_fraction_exclusive"],
        )
        self.assertEqual(predicate["minimum_visibility_fraction_inclusive"], 0.10)
        self.assertTrue(predicate["both_area_predicates_required_on_same_annotation"])
        self.assertEqual(predicate["visible_pixel_area_basis"], "PX_COUNT_VISIB_DIV_307200")
        self.assertEqual(
            predicate["bbox_area_basis"],
            "BBOX_VISIB_WIDTH_TIMES_HEIGHT_DIV_307200",
        )
        self.assertTrue(predicate["positive_bbox_must_fit_640x480_frame"])

    def test_distinct_scene_negative_and_source_order_are_fixed(self):
        negative = self.document["negative_predicate"]
        self.assertTrue(negative["same_modeled_object_id_required"])
        self.assertTrue(negative["modeled_object_id_absent_from_complete_ground_truth_rows"])
        self.assertTrue(negative["scene_must_differ_from_selected_positive"])
        for key in (
            "occluded_object_is_negative",
            "under_ten_percent_visible_object_is_negative",
            "unmodeled_object_is_negative",
            "incomplete_frame_is_negative",
        ):
            self.assertFalse(negative[key])
        selection = self.document["selection"]
        self.assertEqual(selection["object_order"], "ASCENDING_BOP_OBJECT_ID")
        self.assertFalse(selection["adaptive_candidate_or_fallback_allowed"])
        self.assertFalse(selection["threshold_change_after_observation_allowed"])

    def test_two_branches_are_falsifiable_and_authority_is_narrow(self):
        decision = self.document["decision"]
        self.assertEqual(decision["select"], "SELECT_DUAL_AREA_CROSS_SCENE_PAIR")
        self.assertEqual(decision["stop"], "STOP_YCBV_SMALL_BBOX_ORACLE")
        self.assertEqual(
            decision["select_authorizes_only"],
            "ONE_EXACT_REPLACEMENT_D1_MATERIALIZATION_CONTRACT",
        )
        self.assertTrue(decision["select_does_not_authorize_rgb_read_until_next_contract"])
        self.assertTrue(decision["select_does_not_authorize_prediction_training_or_transfer_claim"])
        self.assertTrue(decision["stop_does_not_authorize_threshold_or_source_change"])

    def test_m24_metric_gap_is_the_only_trigger_not_a_changed_m24_result(self):
        self.assertEqual(
            self.m24["metric_alignment"]["status"],
            "VISIBLE_PIXEL_SMALL_BUT_M16_BBOX_LARGE",
        )
        self.assertFalse(self.m24["metric_alignment"]["small_bbox_detector_oracle_established"])
        self.assertFalse(self.m24["metric_alignment"]["transfer_gain_experiment_authorized"])

    def test_access_claim_and_operate_boundaries_remain_closed(self):
        access = self.document["input_access"]
        self.assertTrue(access["read_members_directly_from_verified_zip"])
        for key, value in access.items():
            if key.endswith("_allowed"):
                self.assertFalse(value, key)
        self.assertTrue(all(value is True for value in self.document["claim_limits"].values()))
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
