"""Frozen pre-retry contract for M29 primary demo acceptance."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m29-primary-demo-acceptance-retry-v1.toml"


class M29ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_is_frozen_before_one_committed_retry(self):
        self.assertEqual(
            self.document["status"],
            "FROZEN_BEFORE_SINGLE_COMMITTED_ACCEPTANCE_RETRY",
        )
        self.assertEqual(self.document["acceptance_attempt_limit"], 1)
        self.assertEqual(self.document["acceptance_internal_run_count"], 2)
        execution = self.document["execution"]
        self.assertTrue(execution["checker_must_be_committed_before_retry"])
        self.assertFalse(execution["post_attempt_expected_value_change_allowed"])
        self.assertFalse(execution["second_retry_allowed"])
        self.assertFalse(execution["arbitrary_contract_path_allowed"])

    def test_correction_changes_expected_meaning_only(self):
        correction = self.document["correction"]
        self.assertTrue(correction["changes_only_frozen_expected_meaning"])
        self.assertFalse(correction["changes_runtime_semantics"])
        self.assertFalse(correction["changes_presentation"])
        self.assertFalse(correction["changes_source_or_threshold"])

    def test_event_evidence_and_confirmation_frames_are_distinct(self):
        rows = self.document["expected_claim"]
        self.assertEqual(
            [
                (
                    item["source_event_label_frame"],
                    item["evidence_start_frame"],
                    item["evidence_end_frame"],
                    item["confirmation_frame"],
                )
                for item in rows
            ],
            [(35, 33, 37, 37), (65, 66, 68, 68)],
        )

    def test_semantic_basis_files_match_frozen_hashes(self):
        for path_key, hash_key in (
            ("m28_result", "m28_result_sha256"),
            ("source_manifest", "source_manifest_sha256"),
            ("relation_engine", "relation_engine_sha256"),
            ("relation_rules", "relation_rules_sha256"),
        ):
            payload = (ROOT / self.document[path_key]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), self.document[hash_key])

    def test_source_answer_and_closed_boundaries_are_unchanged(self):
        self.assertEqual(self.document["source_use_class"], "D0_SYNTHETIC")
        self.assertEqual(self.document["source_frame_count"], 80)
        answer = self.document["expected_answer"]
        self.assertEqual(
            (answer["status"], answer["location_id"], answer["epistemic_status"]),
            ("FOUND", "sofa", "estimated"),
        )
        self.assertEqual(answer["world_scope"], "source:b1-key-bag-sofa@2")
        self.assertEqual(answer["as_of_source_sequence"], 68)
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))

    def test_pass_advances_only_to_teammate_drill(self):
        decision = self.document["decision"]
        self.assertEqual(
            decision["pass_authorizes_only"],
            "M30_TEAMMATE_CLEAN_INSTALL_AND_DEMO_DRILL",
        )
        self.assertTrue(decision["stop_authorizes_no_second_retry"])


if __name__ == "__main__":
    unittest.main()
