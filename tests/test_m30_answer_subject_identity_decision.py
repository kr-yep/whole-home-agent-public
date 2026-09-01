"""Frozen repository-only contract for M30 answer-subject identity."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m30-answer-subject-identity-decision-v1.toml"


class M30ContractTests(unittest.TestCase):
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
                "A_CANONICAL_ANSWER_TRACE_SUBJECT",
                "B_PUBLIC_DTO_ONLY_SUBJECT",
                "C_KEEP_CURRENT_TRACE_CONTEXT",
            ],
        )
        self.assertEqual(len(self.document["fatal_gate"]), 8)

    def test_every_evidence_file_is_hash_pinned(self):
        for item in self.document["evidence_file"]:
            payload = (ROOT / item["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), item["sha256"])
        result = ROOT / self.document["m29_result"]
        self.assertEqual(hashlib.sha256(result.read_bytes()).hexdigest(), self.document["m29_result_sha256"])

    def test_subject_is_query_scope_metadata_not_claim_truth(self):
        review = self.document["hostile_review"]
        self.assertTrue(review["subject_identity_is_query_scope_metadata"])
        self.assertFalse(review["subject_identity_is_epistemic_evidence"])
        self.assertFalse(review["adding_subject_changes_physical_truth"])
        self.assertFalse(review["relation_path_is_sufficient_for_unknown_or_conflict"])

    def test_selection_is_at_most_one_and_requires_separate_implementation(self):
        self.assertEqual(
            self.document["selection_rule"],
            "SELECT_AT_MOST_ONE_CANDIDATE_THAT_PASSES_EVERY_FATAL_GATE",
        )
        self.assertTrue(self.document["decision"]["selected_work_must_be_separately_frozen"])
        self.assertFalse(self.document["decision"]["m29_retry_allowed"])

    def test_every_runtime_and_change_boundary_is_closed(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
