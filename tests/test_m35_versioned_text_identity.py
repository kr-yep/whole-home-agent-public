"""Frozen repository-only contract for M35 versioned-text identity."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m35-versioned-text-identity-portability-decision-v1.toml"


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


if __name__ == "__main__":
    unittest.main()
