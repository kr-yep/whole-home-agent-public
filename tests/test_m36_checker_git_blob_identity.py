"""Frozen contract and focused tests for M36 Git-blob identity hardening."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m36-checker-git-blob-identity-hardening-v1.toml"
CHECKER = ROOT / "tools" / "check_teammate_drill.py"


class M36ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_m35_selection_and_prechange_checker_are_frozen(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_BOUNDED_IMPLEMENTATION")
        self.assertEqual(self.document["selected_candidate"], "A_GIT_BLOB_SHA256_PLUS_CLEAN_WORKTREE")
        self.assertEqual(
            hashlib.sha256((ROOT / self.document["m35_result"]).read_bytes()).hexdigest(),
            self.document["m35_result_sha256"],
        )
        self.assertEqual(self.document["prechange_checker_sha256"], "cd285badb9e4ccd6b5ab8e94a657cdfa814294ceffc9d72468875ea977118c5f")

    def test_scope_is_one_tool_file_and_zero_product_files(self):
        implementation = self.document["implementation"]
        self.assertEqual(implementation["production_file_change_count"], 0)
        self.assertEqual(implementation["tool_file_change_count"], 1)
        self.assertEqual(implementation["tool_file"], "tools/check_teammate_drill.py")
        self.assertFalse(implementation["non_git_fallback_allowed"])
        self.assertFalse(implementation["raw_worktree_hash_fatal"])

    def test_receipt_schema_change_is_checker_only_and_explicit(self):
        compatibility = self.document["compatibility"]
        self.assertIn("THREE_EXPLICIT", compatibility["checker_receipt_schema_change"])
        self.assertFalse(compatibility["stable_external_checker_receipt_schema_promised"])
        self.assertFalse(compatibility["product_or_public_demo_schema_changed"])

    def test_every_runtime_and_product_boundary_is_closed(self):
        self.assertFalse(self.document["decision"]["m34_retry_or_status_rewrite_allowed"])
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
