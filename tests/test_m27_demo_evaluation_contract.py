"""Frozen no-model M27 demo and evaluation-lane decision contract."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m27-demo-evaluation-contract-v1.toml"
M26 = ROOT / "configs" / "evaluation" / "m26-ycbv-dual-area-replacement-d1-result-v1.toml"


class M27ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.m26 = tomllib.loads(M26.read_text(encoding="utf-8"))

    def test_scope_is_repo_only_no_model_and_exact_hackathon_scale(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_OPTION_SCORING")
        self.assertEqual(self.document["team_size"], 5)
        self.assertEqual(self.document["hackathon_days"], 3)
        self.assertEqual(self.document["primary_demo_target_seconds"], 90)
        evidence = self.document["evidence_scope"]
        self.assertTrue(evidence["committed_repository_evidence_only"])
        self.assertFalse(evidence["source_or_media_read_allowed"])
        self.assertFalse(evidence["network_research_allowed"])

    def test_exactly_three_options_and_seven_fatal_and_gates_are_frozen(self):
        self.assertEqual(
            [item["id"] for item in self.document["option"]],
            ["A_EXISTING_SYNTHETIC_E2E", "B_M26_TWO_FRAME_ORACLE_PRIMARY", "C_NEW_MODEL_DATA_FIRST"],
        )
        self.assertEqual(len(self.document["fatal_gate"]), 7)
        decision = self.document["decision"]
        self.assertTrue(decision["selection_requires_every_fatal_gate_pass"])
        self.assertTrue(decision["unknown_is_selection_ineligible"])
        self.assertTrue(decision["select_first_all_pass_option"])

    def test_three_evaluation_lanes_cannot_be_conflated(self):
        lanes = self.document["evaluation_lane"]
        self.assertFalse(lanes["public_product_demo"]["model_accuracy_or_home_transfer_claim_allowed"])
        self.assertFalse(lanes["mechanical_cv_smoke"]["primary_demo_dependency_allowed"])
        self.assertFalse(lanes["mechanical_cv_smoke"]["gain_claim_or_threshold_tuning_allowed"])
        scientific = lanes["future_scientific"]
        self.assertTrue(scientific["development_and_frozen_test_separated"])
        self.assertTrue(scientific["protected_source_groups_required"])
        self.assertFalse(scientific["adjacent_frame_random_split_allowed"])
        self.assertTrue(scientific["untouched_test_used_once_after_selection"])
        self.assertFalse(scientific["single_positive_bootstrap_or_gain_claim_allowed"])
        self.assertEqual(scientific["training_epoch_cap"], 20)
        self.assertEqual(scientific["early_stopping_patience"], 5)

    def test_m26_is_mechanical_smoke_not_gain_authority(self):
        self.assertTrue(self.m26["metric_alignment"]["small_bbox_detector_oracle_established"])
        self.assertFalse(self.m26["metric_alignment"]["detector_gain_established"])
        self.assertFalse(self.m26["metric_alignment"]["transfer_gain_experiment_authorized"])

    def test_hostile_review_claims_and_all_boundaries_are_closed(self):
        self.assertEqual(len(self.document["hostile_review"]["objections"]), 5)
        self.assertTrue(self.document["hostile_review"]["every_objection_requires_explicit_disposition"])
        self.assertTrue(all(value is False for value in self.document["claim_limits"].values()))
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
