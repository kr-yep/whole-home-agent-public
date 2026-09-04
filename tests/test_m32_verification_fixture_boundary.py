"""Static document contract for the M32 verification-fixture decision."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m32-verification-fixture-boundary-decision-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m32-verification-fixture-boundary-decision-result-v1.toml"


class M32ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_three_candidates_and_eight_fatal_gates_are_frozen(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_REPOSITORY_EVIDENCE_SCORING")
        self.assertEqual(self.document["candidate_count"], 3)
        self.assertEqual(self.document["fatal_gate_count"], 8)
        self.assertEqual(
            [item["id"] for item in self.document["candidate"]],
            [
                "A_EXPLICIT_VERIFICATION_PROFILES",
                "B_ZERO_MEDIA_FOR_EVERY_VERIFICATION",
                "C_ALL_D0_MEDIA_ALLOWED_FOR_VERIFICATION",
            ],
        )
        self.assertEqual(len(self.document["fatal_gate"]), 8)

    def test_text_evidence_records_historical_hash_pins_without_opening_media(self):
        expected = {item["path"]: item["sha256"] for item in self.document["evidence_file"]}
        for relative_path, digest in expected.items():
            self.assertNotIn(Path(relative_path).suffix.lower(), {".mp4", ".png", ".jpg", ".webm"})
            self.assertTrue((ROOT / relative_path).is_file())
            self.assertEqual(len(digest), 64)
            self.assertTrue(all(character in "0123456789abcdef" for character in digest))
        m31_digest = self.document["m31_result_sha256"]
        self.assertTrue((ROOT / self.document["m31_result"]).is_file())
        self.assertEqual(len(m31_digest), 64)
        self.assertTrue(all(character in "0123456789abcdef" for character in m31_digest))

    def test_profiles_keep_static_and_ad_hoc_work_closed(self):
        profiles = self.document["required_profile"]
        self.assertFalse(profiles["static_contract"]["media_bytes_allowed"])
        self.assertFalse(profiles["static_contract"]["application_or_demo_execution_allowed"])
        self.assertFalse(profiles["ad_hoc_acceptance_or_experiment"]["authorized_by_this_decision"])
        self.assertTrue(profiles["ad_hoc_acceptance_or_experiment"]["separately_frozen_gate_required"])

    def test_scoring_phase_keeps_every_runtime_boundary_closed(self):
        self.assertTrue(all(value is False for value in self.document["scoring_phase_boundaries"].values()))
        self.assertFalse(self.document["decision"]["m31_status_rewrite_allowed"])


class M32ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_exactly_one_candidate_passes_every_fatal_gate(self):
        matrix = {item["id"]: item for item in self.result["candidate_result"]}
        self.assertEqual(self.result["eligible_candidate_count"], 1)
        self.assertEqual(self.result["selected_candidate"], "A_EXPLICIT_VERIFICATION_PROFILES")
        self.assertEqual(matrix["A_EXPLICIT_VERIFICATION_PROFILES"]["gate_results"], ["PASS"] * 8)
        self.assertFalse(matrix["B_ZERO_MEDIA_FOR_EVERY_VERIFICATION"]["eligible"])
        self.assertFalse(matrix["C_ALL_D0_MEDIA_ALLOWED_FOR_VERIFICATION"]["eligible"])

    def test_selected_policy_is_exact_and_purpose_limited(self):
        policy = self.result["selected_policy"]
        self.assertEqual(policy["static_contract_media"], "FORBIDDEN")
        self.assertEqual(policy["complete_regression_media"], "EXACT_ALLOWLIST_ONLY")
        self.assertEqual(policy["complete_regression_evidence_meaning"], "REGRESSION_ONLY")
        self.assertFalse(policy["ad_hoc_acceptance_or_experiment_authorized"])
        self.assertTrue(policy["new_path_or_use_class_requires_separate_gate"])

    def test_m31_history_and_runtime_authority_remain_closed(self):
        self.assertEqual(self.result["m31_status_after_m32"], "CONTRACT_NORMAL_STOP")
        self.assertFalse(self.result["claim_limits"]["m31_retroactive_pass"])
        self.assertFalse(self.result["claim_limits"]["product_or_cv_gain_established"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
