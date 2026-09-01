"""Frozen no-data/no-model contract for the M23 cross-scene validity gate."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M16 = ROOT / "configs" / "evaluation" / "m16-target-label-oracle-v1.toml"
M22 = ROOT / "configs" / "evaluation" / "m22-ycbv-annotation-failure-localization-result-v1.toml"
CONTRACT = ROOT / "configs" / "evaluation" / "m23-cross-scene-transfer-oracle-validity-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m23-cross-scene-transfer-oracle-validity-result-v1.toml"


class M23ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m16 = tomllib.loads(M16.read_text(encoding="utf-8"))
        cls.m22 = tomllib.loads(M22.read_text(encoding="utf-8"))
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_frozen_facts_are_exactly_the_m22_evidence_boundary(self):
        facts = self.document["frozen_input_facts"]
        for key in (
            "source_revision",
            "positive_frame_count",
            "negative_frame_count",
            "paired_object_scene_count",
        ):
            self.assertEqual(facts[key], self.m22[key], key)
        self.assertEqual(facts["positive_object_ids"], [4, 17, 18])
        self.assertEqual(facts["target_frame_count"], 900)
        self.assertFalse(self.m22["next_gate"]["cross_scene_rule_adopted"])

    def test_proposal_changes_scene_pairing_but_not_label_semantics(self):
        proposal = self.document["proposed_contract"]
        self.assertTrue(proposal["same_modeled_class_required"])
        self.assertTrue(proposal["positive_and_negative_may_use_distinct_scenes"])
        self.assertEqual(
            [proposal["minimum_visible_area_fraction"], proposal["maximum_visible_area_fraction"]],
            [0.001, 0.01],
        )
        self.assertTrue(proposal["complete_frame_denominator_required"])
        self.assertFalse(proposal["unmodeled_objects_are_negative"])
        self.assertFalse(proposal["unknown_occluded_or_under_ten_percent_visible_are_negative"])
        self.assertEqual(proposal["maximum_slice_frames"], 18)
        self.assertFalse(proposal["relation_movement_or_whole_home_claim_allowed"])

    def test_exactly_five_fatal_gates_form_an_and_gate(self):
        gates = self.document["fatal_gate"]
        self.assertEqual(
            [gate["id"] for gate in gates],
            [
                "G1_CROSS_IMAGE_CLASS_AGGREGATION",
                "G2_NEGATIVE_DENOMINATOR",
                "G3_PROTECTED_GROUP_NO_LEAKAGE",
                "G4_PAIRED_COMPARABILITY",
                "G5_SMALL_SLICE_UNCERTAINTY",
            ],
        )
        self.assertTrue(self.document["decision"]["selection_requires_all_fatal_gates_pass"])
        self.assertTrue(self.document["evidence_requirements"]["unknown_is_selection_ineligible"])

    def test_hostile_objections_and_narrow_authority_are_frozen(self):
        hostile = self.document["hostile_review"]
        self.assertEqual(len(hostile["objections"]), 5)
        self.assertTrue(hostile["every_objection_requires_explicit_disposition"])
        self.assertTrue(hostile["unresolved_material_objection_is_fatal"])
        decision = self.document["decision"]
        self.assertEqual(
            decision["selection_authorizes_only"],
            "ONE_MAXIMUM_18_FRAME_D1_MATERIALIZATION_PROPOSAL",
        )
        self.assertTrue(decision["selection_is_not_materialization"])
        self.assertTrue(decision["selection_is_not_model_or_transfer_evidence"])

    def test_research_cannot_read_data_run_models_or_operate(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        requirements = self.document["evidence_requirements"]
        self.assertTrue(requirements["primary_sources_only_for_technical_claims"])
        self.assertTrue(requirements["inference_must_be_labeled"])

    def test_result_is_the_exact_all_pass_selection(self):
        self.assertEqual(
            self.result["decision"],
            self.document["decision"]["selection"],
        )
        self.assertEqual(self.result["fatal_gate_count"], 5)
        self.assertEqual(self.result["fatal_gate_pass_count"], 5)
        self.assertTrue(self.result["all_fatal_gates_passed"])
        self.assertEqual(
            [gate["id"] for gate in self.result["fatal_gate"]],
            [gate["id"] for gate in self.document["fatal_gate"]],
        )
        self.assertTrue(
            all(gate["status"] == "PASS" for gate in self.result["fatal_gate"])
        )

    def test_result_preserves_the_narrow_authority_and_hostile_limits(self):
        self.assertEqual(
            self.result["selection_authorizes_only"],
            self.document["decision"]["selection_authorizes_only"],
        )
        self.assertEqual(self.result["maximum_slice_frames"], 18)
        self.assertEqual(self.result["project_split"], "test")
        self.assertEqual(len(self.result["hostile_disposition"]), 5)
        self.assertTrue(self.result["inference"]["is_inference"])
        self.assertFalse(self.result["boundaries"]["d1_materialized"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))

    def test_next_gate_is_materialization_only_not_model_work(self):
        next_gate = self.result["next_gate"]
        self.assertEqual(next_gate["maximum_frames"], 18)
        self.assertFalse(next_gate["training_prediction_or_test_tuning_allowed"])
        self.assertEqual(
            next_gate["proposal"],
            "M24_MINIMAL_CROSS_SCENE_YCBV_D1_MATERIALIZATION",
        )


if __name__ == "__main__":
    unittest.main()
