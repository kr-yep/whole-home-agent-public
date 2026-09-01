"""Frozen no-model M27 demo and evaluation-lane decision contract."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m27-demo-evaluation-contract-v1.toml"
M26 = ROOT / "configs" / "evaluation" / "m26-ycbv-dual-area-replacement-d1-result-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m27-demo-evaluation-contract-result-v1.toml"


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


class M27ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_only_existing_e2e_passes_all_fatal_gates(self):
        self.assertEqual(self.result["decision"], self.contract["decision"]["selection"])
        self.assertEqual(self.result["selected_option"], "A_EXISTING_SYNTHETIC_E2E")
        self.assertTrue(self.result["all_fatal_gates_passed"])
        options = {item["id"]: item for item in self.result["option_result"]}
        self.assertTrue(options["A_EXISTING_SYNTHETIC_E2E"]["eligible"])
        self.assertFalse(options["B_M26_TWO_FRAME_ORACLE_PRIMARY"]["eligible"])
        self.assertFalse(options["C_NEW_MODEL_DATA_FIRST"]["eligible"])

    def test_matrix_has_every_option_gate_once_and_unknown_stays_ineligible(self):
        option_ids = {item["id"] for item in self.contract["option"]}
        gate_ids = {item["id"] for item in self.contract["fatal_gate"]}
        rows = self.result["gate_result"]
        self.assertEqual(len(rows), len(option_ids) * len(gate_ids))
        self.assertEqual({(item["option_id"], item["gate_id"]) for item in rows}, {(option, gate) for option in option_ids for gate in gate_ids})
        c_rows = [item for item in rows if item["option_id"] == "C_NEW_MODEL_DATA_FIRST"]
        self.assertTrue(all(item["status"] == "UNKNOWN" for item in c_rows))

    def test_lanes_keep_demo_smoke_and_future_science_separate(self):
        lanes = self.result["lane_decision"]
        self.assertEqual(lanes["public_product_demo"]["status"], "PRIMARY")
        self.assertEqual(lanes["mechanical_cv_smoke"]["status"], "OPTIONAL_SUPPORTING_EVIDENCE")
        self.assertEqual(lanes["future_scientific"]["status"], "DEFERRED_REQUIRES_SEPARATE_CONTRACT")
        self.assertEqual(lanes["future_scientific"]["training_epoch_cap"], 20)
        self.assertEqual(lanes["future_scientific"]["early_stopping_patience"], 5)

    def test_all_hostile_objections_have_non_material_dispositions(self):
        objections = self.contract["hostile_review"]["objections"]
        dispositions = self.result["hostile_disposition"]
        self.assertEqual([item["objection"] for item in dispositions], objections)
        self.assertTrue(all(not item["material_objection_remaining"] for item in dispositions))

    def test_result_read_no_media_or_model_and_next_gate_is_bounded(self):
        self.assertFalse(self.result["source_or_media_read"])
        self.assertFalse(self.result["model_or_prediction_used"])
        next_gate = self.result["next_gate"]
        self.assertEqual(next_gate["proposal"], "M28_PRIMARY_DEMO_ACCEPTANCE_GAP_AUDIT_AND_SCRIPT_HARDENING")
        self.assertTrue(next_gate["committed_d0_synthetic_media_allowed"])
        self.assertFalse(next_gate["third_party_or_private_media_allowed"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
