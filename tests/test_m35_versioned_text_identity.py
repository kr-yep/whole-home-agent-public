"""Frozen repository-only contract for M35 versioned-text identity."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m35-versioned-text-identity-portability-decision-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m35-versioned-text-identity-portability-decision-result-v1.toml"


class M35ContractTests(unittest.TestCase):
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
                "A_GIT_BLOB_SHA256_PLUS_CLEAN_WORKTREE",
                "B_CANONICAL_LF_WORKTREE_SHA256",
                "C_RAW_WORKTREE_SHA256",
            ],
        )

    def test_m34_result_checker_and_attributes_are_hash_pinned(self):
        self.assertEqual(
            hashlib.sha256((ROOT / self.document["m34_result"]).read_bytes()).hexdigest(),
            self.document["m34_result_sha256"],
        )
        for record in self.document["evidence_file"]:
            self.assertEqual(
                hashlib.sha256((ROOT / record["path"]).read_bytes()).hexdigest(),
                record["sha256"],
            )

    def test_byte_evidence_keeps_blob_and_checkout_distinct(self):
        basis = self.document["observed_byte_basis"]
        self.assertNotEqual(basis["git_blob_sha256"], basis["windows_worktree_sha256"])
        self.assertEqual(basis["git_blob_crlf_count"], 0)
        self.assertEqual(basis["windows_worktree_crlf_count"], basis["line_count"])
        self.assertFalse(basis["gitattributes_has_uv_lock_rule"])
        self.assertTrue(basis["uv_sync_frozen_succeeded"])

    def test_decision_and_runtime_boundaries_are_closed(self):
        self.assertFalse(self.document["decision"]["m34_status_rewrite_or_retry_allowed"])
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


class M35ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_git_blob_identity_is_the_only_eligible_candidate(self):
        matrix = {item["id"]: item for item in self.result["candidate_result"]}
        self.assertEqual(self.result["eligible_candidate_count"], 1)
        self.assertEqual(self.result["selected_candidate"], "A_GIT_BLOB_SHA256_PLUS_CLEAN_WORKTREE")
        self.assertEqual(matrix["A_GIT_BLOB_SHA256_PLUS_CLEAN_WORKTREE"]["gate_results"], ["PASS"] * 8)
        self.assertFalse(matrix["B_CANONICAL_LF_WORKTREE_SHA256"]["eligible"])
        self.assertFalse(matrix["C_RAW_WORKTREE_SHA256"]["eligible"])

    def test_selected_scope_keeps_identity_and_representation_distinct(self):
        scope = self.result["selected_scope"]
        self.assertTrue(scope["hash_exact_head_uv_lock_git_blob"])
        self.assertTrue(scope["require_expected_head_revision"])
        self.assertTrue(scope["require_clean_worktree"])
        self.assertFalse(scope["non_git_fallback_allowed"])
        self.assertTrue(scope["retain_worktree_raw_sha256_as_diagnostic_only"])
        self.assertTrue(scope["receipt_distinguishes_git_blob_and_worktree_hash"])

    def test_archive_limit_and_m34_history_are_explicit(self):
        self.assertFalse(self.result["archive_limit"]["source_archive_or_wheel_without_git_supported"])
        self.assertFalse(self.result["selected_scope"]["m34_retry_or_status_rewrite"])
        self.assertEqual(self.result["m34_status_after_m35"], "CONTRACT_NORMAL_STOP")
        self.assertFalse(self.result["claim_limits"]["selection_establishes_m34_pass"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
