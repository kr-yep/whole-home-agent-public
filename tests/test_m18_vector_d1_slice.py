"""Frozen pre-generation contract for the M18 vector D1 slice."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m18-vector-d1-slice-v1.toml"


class M18VectorD1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_tiny_shape_and_split_assignment_are_frozen(self):
        shape = self.document["shape"]
        self.assertEqual((shape["width"], shape["height"]), (640, 360))
        self.assertEqual(shape["source_group_count"], 3)
        self.assertEqual(shape["frames_per_group"], 6)
        self.assertEqual(shape["image_annotation_pair_count"], 18)
        split = self.document["split_integrity"]
        self.assertEqual(split["splits"], ["development", "validation", "test"])
        self.assertTrue(split["assign_before_render"])
        self.assertFalse(split["protected_factor_cross_split_allowed"])
        groups = self.document["scene_groups"]
        self.assertEqual(list(groups), split["splits"])
        for field in split["protected_factors"]:
            values = [groups[name][field] for name in split["splits"]]
            self.assertEqual(len(values), len(set(values)))

    def test_six_frame_semantic_plan_is_exact(self):
        plan = self.document["frame_plan"]
        self.assertEqual(
            plan["roles"],
            [
                "visible_source",
                "truncated_near_container",
                "occluded_inside_container",
                "visible_destination",
                "scored_negative",
                "unknown",
            ],
        )
        self.assertEqual(len(plan["evaluation_states"]), 6)
        self.assertEqual(len(plan["visibility_states"]), 6)
        self.assertEqual(len(plan["relation_states"]), 6)
        self.assertEqual(self.document["vector_geometry"]["key_width"], 28)
        self.assertEqual(self.document["vector_geometry"]["key_height"], 12)

    def test_complete_d1_case_coverage_is_frozen(self):
        coverage = self.document["coverage"]
        self.assertEqual(coverage["small_object_area_fraction_range"], [0.001, 0.01])
        self.assertEqual(
            coverage["required_visibility_states"],
            ["VISIBLE", "TRUNCATED", "OCCLUDED", "ABSENT"],
        )
        self.assertEqual(
            coverage["required_transition_kinds"],
            ["CONTAINMENT_CHANGE", "LOCATION_CHANGE"],
        )
        self.assertTrue(coverage["explicit_scored_negative_per_split"])
        self.assertTrue(coverage["explicit_unknown_frame_per_split"])

    def test_manifest_reproducibility_and_golden_identity_are_bounded(self):
        reproducibility = self.document["reproducibility"]
        self.assertEqual(reproducibility["clean_generation_count"], 2)
        self.assertEqual(
            reproducibility["maximum_total_non_manifest_output_bytes"],
            5 * 1024 * 1024,
        )
        self.assertFalse(reproducibility["new_dependency_allowed"])
        self.assertTrue(self.document["existing_golden"]["must_remain_unchanged"])
        for key, value in self.document["existing_golden"].items():
            if key.endswith("sha256"):
                self.assertEqual(len(value), 64)

    def test_gate_cannot_authorize_models_claims_or_operation(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertEqual(
            self.document["gate"]["pass_decision"],
            "PASS_TO_REALISM_TRANSFER_GATE_DESIGN",
        )


if __name__ == "__main__":
    unittest.main()
