"""Frozen static contract for the M34 single infrastructure retry."""

from __future__ import annotations

import hashlib
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m34-teammate-drill-infrastructure-retry-v1.toml"


class M34ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_m33_stop_and_single_retry_are_frozen(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_SINGLE_INFRASTRUCTURE_RETRY")
        self.assertEqual(self.document["retry_attempt_limit"], 1)
        self.assertFalse(self.document["additional_retry_allowed"])
        result = ROOT / self.document["m33_result"]
        self.assertEqual(hashlib.sha256(result.read_bytes()).hexdigest(), self.document["m33_result_sha256"])

    def test_only_semantic_uv_version_parser_changes(self):
        repair = self.document["sole_infrastructure_change"]
        self.assertEqual(repair["component"], "OUTER_POWERSHELL_PREFLIGHT_ONLY")
        self.assertEqual(repair["required_semantic_version"], "0.11.24")
        self.assertFalse(repair["trailing_build_metadata_affects_acceptance"])
        match = re.match(
            repair["accepted_regex"],
            "uv 0.11.24 (5e04460c0 2026-06-23 x86_64-pc-windows-msvc)",
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "0.11.24")

    def test_checker_lock_and_fixture_are_byte_identical(self):
        for record in self.document["unchanged_input"]:
            self.assertEqual(
                hashlib.sha256((ROOT / record["path"]).read_bytes()).hexdigest(),
                record["sha256"],
            )

    def test_every_product_and_runtime_change_boundary_is_closed(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertFalse(self.document["decision"]["stop_authorizes_retry"])


if __name__ == "__main__":
    unittest.main()
