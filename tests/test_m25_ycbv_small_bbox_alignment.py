"""Frozen pre-annotation contract for the M25 dual-area diagnostic."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from whole_home_agent.adapters.bop_d1 import BopFrame, BopFrameAnnotation
from whole_home_agent.adapters.bop_diagnostic import (
    SELECT_DUAL_AREA,
    STOP_SMALL_BBOX_ORACLE,
    diagnose_ycbv_dual_area,
)


ROOT = Path(__file__).resolve().parents[1]
M16 = ROOT / "configs" / "evaluation" / "m16-target-label-oracle-v1.toml"
M21 = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"
M24 = ROOT / "configs" / "evaluation" / "m24-ycbv-cross-scene-d1-materialization-result-v1.toml"
CONTRACT = ROOT / "configs" / "evaluation" / "m25-ycbv-small-bbox-alignment-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m25-ycbv-small-bbox-alignment-result-v1.toml"


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


def _annotation(
    object_id: int,
    *,
    visible_pixels: int = 600,
    all_pixels: int = 1000,
    bbox: tuple[int, int, int, int] = (10, 20, 20, 30),
) -> BopFrameAnnotation:
    return BopFrameAnnotation(
        object_id=object_id,
        bbox_visible_xywh=bbox,
        pixel_count_all=all_pixels,
        pixel_count_visible=visible_pixels,
        visible_fraction=visible_pixels / all_pixels,
    )


def _frame(scene_id: int, image_id: int, *annotations: BopFrameAnnotation) -> BopFrame:
    return BopFrame(scene_id=scene_id, image_id=image_id, annotations=annotations)


class M25SyntheticDiagnosticTests(unittest.TestCase):
    def test_selects_lowest_object_then_first_positive_and_distinct_scene_negative(self):
        frames = (
            _frame(1, 1, _annotation(2)),
            _frame(2, 1, _annotation(1)),
            _frame(3, 1, _annotation(3, visible_pixels=5000, bbox=(0, 0, 100, 100))),
        )
        result = diagnose_ycbv_dual_area(frames)
        self.assertEqual(result.decision, SELECT_DUAL_AREA)
        self.assertEqual(result.selected_pair["object_id"], 1)
        self.assertEqual(result.selected_pair["positive"]["scene_id"], 2)
        self.assertEqual(result.selected_pair["negative"]["scene_id"], 1)
        self.assertGreaterEqual(result.distinct_scene_pair_object_count, 2)

    def test_pixel_small_but_bbox_large_is_not_dual_positive(self):
        frames = (
            _frame(1, 1, _annotation(1, visible_pixels=600, bbox=(10, 10, 100, 100))),
            _frame(2, 1, _annotation(2)),
        )
        result = diagnose_ycbv_dual_area(frames)
        object_one = result.object_rows[0]
        self.assertEqual(object_one["pixel_positive_frame_count"], 1)
        self.assertEqual(object_one["bbox_positive_frame_count"], 0)
        self.assertEqual(object_one["dual_positive_frame_count"], 0)

    def test_bbox_small_but_visible_pixels_tiny_is_not_dual_positive(self):
        frames = (
            _frame(1, 1, _annotation(1, visible_pixels=100, all_pixels=200, bbox=(10, 10, 20, 30))),
            _frame(2, 1, _annotation(2)),
        )
        result = diagnose_ycbv_dual_area(frames)
        object_one = result.object_rows[0]
        self.assertEqual(object_one["pixel_positive_frame_count"], 0)
        self.assertEqual(object_one["bbox_positive_frame_count"], 1)
        self.assertEqual(object_one["dual_positive_frame_count"], 0)

    def test_area_upper_boundary_is_exclusive_like_m16(self):
        exactly_one_percent = 3072
        frames = (
            _frame(
                1,
                1,
                _annotation(
                    1,
                    visible_pixels=exactly_one_percent,
                    all_pixels=exactly_one_percent,
                    bbox=(0, 0, 48, 64),
                ),
            ),
            _frame(2, 1, _annotation(2)),
        )
        result = diagnose_ycbv_dual_area(frames)
        self.assertEqual(result.object_rows[0]["dual_positive_frame_count"], 0)

    def test_no_dual_pair_is_a_normal_stop_without_threshold_change(self):
        result = diagnose_ycbv_dual_area(
            (
                _frame(1, 1, _annotation(1, visible_pixels=600, bbox=(10, 10, 100, 100))),
                _frame(2, 1, _annotation(2, visible_pixels=100, all_pixels=200)),
            )
        )
        self.assertEqual(result.decision, STOP_SMALL_BBOX_ORACLE)
        document = result.as_dict()
        self.assertIsNone(document["selected_pair"])
        self.assertFalse(document["threshold_or_predicate_changed_after_observation"])

    def test_same_scene_absence_cannot_form_the_pair(self):
        result = diagnose_ycbv_dual_area(
            (
                _frame(1, 1, _annotation(1)),
                _frame(1, 2, _annotation(2)),
            )
        )
        self.assertEqual(result.decision, STOP_SMALL_BBOX_ORACLE)

    def test_duplicate_frame_or_object_identity_fails_closed(self):
        frame = _frame(1, 1, _annotation(1))
        with self.assertRaisesRegex(ValueError, "frame identities"):
            diagnose_ycbv_dual_area((frame, frame))
        with self.assertRaisesRegex(ValueError, "unique within a frame"):
            diagnose_ycbv_dual_area((_frame(1, 1, _annotation(1), _annotation(1)),))

    def test_tool_has_no_media_network_extraction_or_model_path(self):
        source = (ROOT / "tools" / "diagnose_ycbv_dual_area.py").read_text(encoding="utf-8")
        for forbidden in ("rgb/", ".extract(", "extractall", "requests", "urllib", "torch"):
            self.assertNotIn(forbidden, source)


class M25ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_selects_the_exact_frozen_branch_without_posthoc_change(self):
        self.assertEqual(self.result["decision"], self.contract["decision"]["select"])
        self.assertEqual(self.result["area_contract"]["minimum_fraction_inclusive"], 0.001)
        self.assertEqual(self.result["area_contract"]["maximum_fraction_exclusive"], 0.01)
        self.assertFalse(self.result["area_contract"]["threshold_or_predicate_changed_after_observation"])

    def test_exact_counts_and_selected_identity_are_recorded(self):
        diagnostic = self.result["diagnostic"]
        self.assertEqual(diagnostic["pixel_positive_frame_count"], 81)
        self.assertEqual(diagnostic["bbox_positive_frame_count"], 2)
        self.assertEqual(diagnostic["dual_positive_frame_count"], 2)
        self.assertEqual(diagnostic["distinct_scene_pair_object_count"], 2)
        self.assertEqual(diagnostic["complete_absent_frame_count"], 14775)
        selection = self.result["selection"]
        self.assertEqual(selection["selected_object_id"], 4)
        self.assertEqual([selection["positive"]["source_scene_id"], selection["positive"]["source_image_id"]], [50, 722])
        self.assertEqual([selection["negative"]["source_scene_id"], selection["negative"]["source_image_id"]], [48, 1])
        self.assertGreaterEqual(selection["positive"]["bbox_area_fraction"], 0.001)
        self.assertLess(selection["positive"]["bbox_area_fraction"], 0.01)

    def test_result_is_one_read_with_two_byte_identical_pure_runs(self):
        self.assertEqual(self.result["annotation_member_count"], 37)
        self.assertEqual(self.result["real_annotation_read_attempts"], 1)
        self.assertEqual(self.result["pure_diagnostic_runs"], 2)
        self.assertTrue(self.result["byte_identical_result"])

    def test_adversarial_limits_block_gain_and_movement_claims(self):
        review = self.result["adversarial_review"]
        self.assertEqual(review["independent_reviewer_count"], 0)
        self.assertTrue(review["one_positive_and_one_negative_cannot_measure_stable_gain"])
        self.assertTrue(review["cross_scene_pair_is_not_a_physical_transition"])
        limits = self.result["claim_limits"]
        self.assertFalse(limits["annotation_reference_is_detector_performance"])
        self.assertFalse(limits["two_frame_oracle_is_generalization_evidence"])
        self.assertFalse(limits["training_or_tuning_on_test_is_allowed"])

    def test_next_gate_is_exact_materialization_only_and_every_boundary_is_closed(self):
        next_gate = self.result["next_gate"]
        self.assertEqual(next_gate["proposal"], "M26_EXACT_DUAL_AREA_PAIR_REPLACEMENT_MATERIALIZATION")
        self.assertEqual(next_gate["maximum_rgb_members"], 2)
        self.assertFalse(next_gate["adaptive_frame_or_threshold_change_allowed"])
        self.assertFalse(next_gate["prediction_training_or_test_tuning_allowed"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
