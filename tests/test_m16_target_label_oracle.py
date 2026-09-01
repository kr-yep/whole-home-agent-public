"""Frozen no-media D1 target-label oracle contract for M16."""

from __future__ import annotations

import tomllib
import unittest
from dataclasses import replace
from pathlib import Path

from whole_home_agent.target_oracle import (
    OracleFrame,
    OracleSequence,
    ReferenceInstance,
    TargetOracleDataset,
    TargetOracleError,
    VisibilityState,
    evaluate_target_oracle,
    load_target_oracle_fixture,
    validate_source_group_splits,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m16-target-label-oracle-v1.toml"
FIXTURE = ROOT / "examples" / "fixtures" / "evaluation" / "d1_target_oracle_v1.json"


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


class M16TargetLabelOracleConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.fixture = load_target_oracle_fixture(FIXTURE)
        cls.expected = {
            item["case_id"]: item for item in cls.contract["metric_cases"]
        }

    def test_all_frozen_metric_cases_have_exact_results(self):
        for case_id, expected in self.expected.items():
            with self.subTest(case_id=case_id):
                report = evaluate_target_oracle(
                    self.fixture.dataset,
                    self.fixture.predictions_for(case_id),
                )
                small_recall = dict(report.quality.size_recall50)[
                    "small_0.1_to_1pct"
                ]
                self.assertEqual(report.quality.ap50, expected["expected_ap50"])
                self.assertEqual(
                    report.quality.map50_95, expected["expected_map50_95"]
                )
                self.assertEqual(
                    report.quality.recall50, expected["expected_recall50"]
                )
                self.assertEqual(small_recall, expected["expected_small_recall50"])
                self.assertEqual(
                    report.quality.false_positives50,
                    expected["expected_false_positives50"],
                )
                self.assertEqual(
                    report.evaluated_frame_count,
                    expected["expected_evaluated_frames"],
                )
                self.assertEqual(
                    report.false_positives50_per_evaluated_frame,
                    expected["expected_false_positives_per_frame"],
                )
                self.assertEqual(report.unknown_frame_count, 1)
                self.assertEqual(report.negative_frame_count, 1)
                self.assertEqual(report.reference_transition_count, 1)

    def test_prediction_order_does_not_change_duplicate_case(self):
        predictions = self.fixture.predictions_for("duplicate")
        forward = evaluate_target_oracle(self.fixture.dataset, predictions).as_dict()
        reverse = evaluate_target_oracle(
            self.fixture.dataset, tuple(reversed(predictions))
        ).as_dict()
        self.assertEqual(forward, reverse)

    def test_prediction_on_unknown_frame_fails_instead_of_becoming_negative(self):
        with self.assertRaises(TargetOracleError) as caught:
            evaluate_target_oracle(
                self.fixture.dataset,
                self.fixture.predictions_for("prediction_on_unknown_frame"),
            )
        self.assertEqual(caught.exception.code, "PREDICTION_ON_UNSCORED_FRAME")

    def test_duplicate_frame_identity_has_the_frozen_error_code(self):
        sequence = self.fixture.dataset.sequences[0]
        duplicate = replace(
            sequence,
            frames=sequence.frames + (sequence.frames[0],),
        )
        with self.assertRaises(TargetOracleError) as caught:
            replace(self.fixture.dataset, sequences=(duplicate,))
        self.assertEqual(caught.exception.code, "DUPLICATE_FRAME_IDENTITY")

    def test_persistent_instance_label_conflict_fails_closed(self):
        sequence = self.fixture.dataset.sequences[0]
        absent = sequence.frames[1].instances[0]
        conflicting_frame = OracleFrame(
            frame_index=1,
            state=sequence.frames[1].state,
            instances=(replace(absent, label="bag"),),
        )
        conflicting_sequence = OracleSequence(
            group=sequence.group,
            frames=(sequence.frames[0], conflicting_frame, sequence.frames[2]),
        )
        with self.assertRaises(TargetOracleError) as caught:
            TargetOracleDataset(
                dataset_id=self.fixture.dataset.dataset_id,
                width=self.fixture.dataset.width,
                height=self.fixture.dataset.height,
                sequences=(conflicting_sequence,),
                transitions=self.fixture.dataset.transitions,
            )
        self.assertEqual(caught.exception.code, "INSTANCE_LABEL_CONFLICT")

    def test_visibility_semantics_require_or_prohibit_boxes(self):
        visible = self.fixture.dataset.sequences[0].frames[0].instances[0]
        with self.assertRaises(TargetOracleError) as missing_box:
            ReferenceInstance(
                instance_id="key-2",
                label="key",
                visibility=VisibilityState.VISIBLE,
                bbox=None,
            )
        self.assertEqual(missing_box.exception.code, "VISIBILITY_BOX_CONFLICT")
        with self.assertRaises(TargetOracleError) as absent_box:
            replace(visible, visibility=VisibilityState.ABSENT)
        self.assertEqual(absent_box.exception.code, "VISIBILITY_BOX_CONFLICT")

        with self.assertRaises(TargetOracleError) as unknown_negative:
            OracleFrame(
                frame_index=0,
                state=self.fixture.dataset.sequences[0].frames[0].state,
                instances=(
                    ReferenceInstance(
                        instance_id="key-2",
                        label="key",
                        visibility=VisibilityState.UNKNOWN,
                        bbox=None,
                    ),
                ),
            )
        self.assertEqual(
            unknown_negative.exception.code, "SCORED_FRAME_HAS_UNKNOWN_INSTANCE"
        )

    def test_source_group_split_is_valid_and_each_protected_leak_is_rejected(self):
        self.assertEqual(self.fixture.use_class, "D0_SYNTHETIC")
        validate_source_group_splits(self.fixture.split_groups)
        development, validation = self.fixture.split_groups
        for field_name, value in development.protected_values():
            with self.subTest(field_name=field_name):
                leaking_validation = replace(validation, **{field_name: value})
                with self.assertRaises(TargetOracleError) as caught:
                    validate_source_group_splits((development, leaking_validation))
                self.assertEqual(
                    caught.exception.code, "PROTECTED_GROUP_SPLIT_LEAKAGE"
                )


if __name__ == "__main__":
    unittest.main()
