"""Frozen decision contract for the M39 language-presentation boundary."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m39-language-presentation-boundary-v1.toml"


class M39ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_three_candidates_and_ten_fatal_gates_are_frozen(self):
        self.assertEqual(
            self.document["status"],
            "FROZEN_BEFORE_REPOSITORY_EVIDENCE_SCORING",
        )
        self.assertEqual(self.document["candidate_count"], 3)
        self.assertEqual(self.document["fatal_gate_count"], 10)
        self.assertEqual(
            [item["id"] for item in self.document["candidate"]],
            [
                "A_LOCAL_DEFAULT_SEPARATE_CLOUD_AUTHORITY",
                "B_API_KEY_AUTOSTART_CLOUD",
                "C_PERMANENT_LOCAL_ONLY",
            ],
        )
        self.assertEqual(len(self.document["fatal_gate"]), 10)

    def test_every_repository_evidence_file_is_hash_pinned(self):
        evidence = {item["path"]: item["sha256"] for item in self.document["evidence_file"]}
        self.assertEqual(
            evidence,
            {
                "src/whole_home_agent/llm_context.py": "4baf318f32066c9b1e87b0b7abb45578ff46a434d54df6b735cc87cc9a0fcf5b",
                "docs/adr/0020-preview-minimized-text-before-language-provider.md": "3960bda19ea5c1d0a84e3ce41924f8fa4b8acb3ed0368b64f7e3352974d46bae",
                "ACTION_POLICY.md": "9ad8b9e5c659535be0176451c5615e1b7db15418193af9fc021c8af4b29c97f3",
                "PROJECT_STATE.md": "bdcd59f8913054c8777c71e55522cac969496c1c8a5a07a9a3fbe9cf3548e963",
            },
        )
        for path, expected in evidence.items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), expected)

    def test_exact_m38_field_surface_is_classified(self):
        self.assertEqual(
            {item["path"] for item in self.document["field_classification"]},
            {
                "schema",
                "purpose",
                "answer.subject_id",
                "answer.status",
                "answer.location_id",
                "answer.epistemic_status",
                "relation_facts[].subject_id",
                "relation_facts[].predicate",
                "relation_facts[].object_id",
                "relation_facts[].epistemic_status",
            },
        )
        private = [
            item
            for item in self.document["field_classification"]
            if item["path"] not in {"schema", "purpose"}
        ]
        self.assertTrue(all("PRIVATE" in item["future_household_value"] for item in private))
        self.assertTrue(
            all(
                item["synthetic_d0_egress_now"] == "PROHIBITED_NO_EGRESS_PROFILE_EXISTS"
                for item in self.document["field_classification"]
            )
        )

    def test_cloud_contract_is_text_only_stateless_and_still_not_zero_retention(self):
        cloud = self.document["cloud_minimum_contract"]
        self.assertEqual(cloud["status"], "PROPOSED_BLOCKED_NOT_IMPLEMENTED")
        self.assertFalse(cloud["payload_media_allowed"])
        self.assertFalse(cloud["payload_files_allowed"])
        self.assertFalse(cloud["tools_allowed"])
        self.assertFalse(cloud["conversation_state_allowed"])
        self.assertFalse(cloud["background_mode_allowed"])
        self.assertTrue(cloud["provider_storage_request_must_be_disabled"])
        self.assertFalse(cloud["claim_of_zero_provider_retention_allowed"])
        self.assertFalse(cloud["automatic_retry_allowed"])

    def test_key_or_configuration_cannot_authorize_egress(self):
        gates = {item["id"]: item["requirement"] for item in self.document["fatal_gate"]}
        self.assertIn("KEY_CONFIGURATION_FLAG", gates["G2_AUTHORITY_SEPARATION"])
        self.assertIn("NEVER_COUNTS", gates["G2_AUTHORITY_SEPARATION"])
        self.assertFalse(self.document["decision"]["policy_adoption_or_operate_activation_allowed"])

    def test_every_current_runtime_boundary_is_closed(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
