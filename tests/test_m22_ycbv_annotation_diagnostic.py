"""Frozen M22 annotation-only failure-localization contract."""

from __future__ import annotations

import subprocess
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M21 = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"
CONTRACT = ROOT / "configs" / "evaluation" / "m22-ycbv-annotation-failure-localization-v1.toml"


class M22ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m21 = tomllib.loads(M21.read_text(encoding="utf-8"))
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_source_is_the_exact_ignored_m21_source_and_scope(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_REAL_ANNOTATION_REREAD")
        self.assertEqual(self.document["dataset_id"], self.m21["dataset_id"])
        self.assertEqual(self.document["source_revision"], self.m21["source_revision"])
        expected = {
            item["name"]: (item["bytes"], item["sha256"], item["source_root"])
            for item in self.m21["archive"]
        }
        actual = {
            item["name"]: (item["bytes"], item["sha256"], item["source_root"])
            for item in self.document["archive"]
        }
        self.assertEqual(actual, expected)
        self.assertEqual(self.document["expected_target_entry_count"], 4123)
        self.assertEqual(self.document["expected_unique_target_frame_count"], 900)
        self.assertEqual(self.document["expected_scene_ids"], list(range(48, 60)))
        result = subprocess.run(
            ["git", "check-ignore", "-q", self.document["source_archive_root"] + "/probe"],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_positive_predicate_is_byte_for_byte_equivalent_in_meaning_to_m21(self):
        positive = self.document["positive_predicate"]
        selection = self.m21["slice_selection"]
        translator = self.m21["translator"]
        self.assertEqual(positive["modeled_object_ids"], list(range(1, 22)))
        self.assertEqual(positive["minimum_visible_fraction"], translator["visibility_unknown_below_fraction"])
        self.assertEqual(
            [positive["minimum_visible_area_fraction"], positive["maximum_visible_area_fraction"]],
            selection["target_area_fraction_range"],
        )
        self.assertEqual(positive["area_fraction_basis"], selection["target_area_fraction_basis"])
        self.assertTrue(positive["positive_bbox_width_and_height_required"])

    def test_negative_and_completeness_rules_cannot_invent_absence(self):
        negative = self.document["negative_predicate"]
        self.assertTrue(negative["modeled_object_id_absent_from_complete_ground_truth_rows"])
        for key, value in negative.items():
            if key != "name" and key != "modeled_object_id_absent_from_complete_ground_truth_rows":
                self.assertFalse(value, key)
        completeness = self.document["frame_completeness"]
        self.assertTrue(all(value is True for key, value in completeness.items() if key.endswith("_required")))
        self.assertFalse(completeness["invalid_or_incomplete_frame_is_scored"])
        self.assertTrue(completeness["invalid_or_incomplete_source_normal_stop"])

    def test_four_decision_branches_are_exhaustive_and_ordered(self):
        decision = self.document["decision"]
        self.assertEqual(
            decision["priority"],
            [
                "CONFORMANCE_CONFLICT_IF_ANY_M21_PAIR_EXISTS",
                "NO_SMALL_TARGET_TERM_IF_ZERO_POSITIVES",
                "NO_SAFE_NEGATIVE_TERM_IF_ZERO_NEGATIVES",
                "PAIRING_SCOPE_TERM_OTHERWISE",
            ],
        )
        self.assertEqual(len({decision[key] for key in (
            "conformance_conflict",
            "no_small_target",
            "no_safe_negative",
            "pairing_scope",
            "source_invalid",
        )}), 5)

    def test_diagnostic_cannot_read_media_repair_run_models_or_operate(self):
        access = self.document["input_access"]
        self.assertTrue(access["read_members_directly_from_verified_zip"])
        for key, value in access.items():
            if key.endswith("_allowed"):
                self.assertFalse(value, key)
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertFalse(self.document["aggregation"]["raw_annotations_in_result_allowed"])


if __name__ == "__main__":
    unittest.main()
