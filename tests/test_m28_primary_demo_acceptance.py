"""Frozen pre-execution contract for M28 primary demo acceptance."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m28-primary-demo-acceptance-v1.toml"
M27 = ROOT / "configs" / "evaluation" / "m27-demo-evaluation-contract-result-v1.toml"


class M28ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.m27 = tomllib.loads(M27.read_text(encoding="utf-8"))

    def test_contract_is_frozen_before_demo_and_inherits_m27_selection(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_COMMITTED_DEMO_EXECUTION")
        self.assertEqual(self.m27["decision"], "SELECT_EXISTING_SYNTHETIC_E2E_PRIMARY_DEMO")
        self.assertEqual(self.document["source_use_class"], "D0_SYNTHETIC")
        self.assertEqual(self.document["source_frame_count"], 80)
        self.assertEqual(self.document["target_seconds"], 90)

    def test_two_interfaces_run_offline_and_only_run_id_is_excluded(self):
        execution = self.document["execution"]
        self.assertTrue(execution["committed_project_owned_media_allowed"])
        self.assertFalse(execution["third_party_or_private_media_allowed"])
        self.assertTrue(execution["network_denied_during_both_runs"])
        self.assertEqual(self.document["acceptance_runs"], 2)
        self.assertEqual(execution["semantic_comparison_excludes_only"], ["replay_run_id"])
        self.assertFalse(execution["model_or_runtime_configuration_change_allowed"])

    def test_answer_and_exact_two_claims_are_precommitted(self):
        answer = self.document["expected_answer"]
        self.assertEqual((answer["status"], answer["location_id"], answer["epistemic_status"]), ("FOUND", "sofa", "estimated"))
        self.assertEqual(answer["relation_path_length"], 2)
        claims = self.document["expected_claim"]
        self.assertEqual(
            [(item["predicate"], item["subject_id"], item["object_id"], item["confirmation_frame"]) for item in claims],
            [("inside", "key", "bag", 37), ("at_zone", "bag", "sofa", 68)],
        )

    def test_presentation_prevents_fixture_metrics_from_leading(self):
        presentation = self.document["presentation"]
        self.assertFalse(presentation["perfect_fixture_metrics_in_primary_visible_area_allowed"])
        self.assertTrue(presentation["fixture_metrics_must_be_in_collapsed_expander"])
        self.assertFalse(presentation["upload_camera_chat_arbitrary_path_widgets_allowed"])
        self.assertFalse(presentation["credentials_actions_or_generic_tools_allowed"])

    def test_next_authority_and_every_non_demo_boundary_are_closed(self):
        self.assertEqual(self.document["decision"]["pass_authorizes_only"], "M29_TEAMMATE_CLEAN_INSTALL_AND_DEMO_DRILL")
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
