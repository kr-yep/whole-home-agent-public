"""Frozen static contract for the M34 single infrastructure retry."""

from __future__ import annotations

import hashlib
import re
import subprocess
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m34-teammate-drill-infrastructure-retry-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m34-teammate-drill-infrastructure-retry-result-v1.toml"


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
            if record["path"] == "tools/check_teammate_drill.py":
                self.assertEqual(
                    record["sha256"],
                    "cd285badb9e4ccd6b5ab8e94a657cdfa814294ceffc9d72468875ea977118c5f",
                )
            elif record["path"] == "uv.lock":
                blob = subprocess.run(
                    ["git", "show", "HEAD:uv.lock"],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                ).stdout
                self.assertEqual(hashlib.sha256(blob).hexdigest(), record["sha256"])
            else:
                self.assertEqual(
                    hashlib.sha256((ROOT / record["path"]).read_bytes()).hexdigest(),
                    record["sha256"],
                )

    def test_every_product_and_runtime_change_boundary_is_closed(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertFalse(self.document["decision"]["stop_authorizes_retry"])


class M34ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_single_retry_stops_only_on_lock_identity(self):
        self.assertEqual(self.result["decision"], "STOP_M34_TEAMMATE_HANDOFF_DRILL")
        self.assertEqual(self.result["attempt_count"], self.result["attempt_limit"])
        self.assertFalse(self.result["additional_retry_allowed"])
        self.assertEqual(self.result["failure_classes"], ["LOCK_OR_MANIFEST"])
        self.assertEqual(self.result["localized_failure"], "UV_LOCK_WORKTREE_EOL_NORMALIZATION")

    def test_install_and_offline_demo_mechanics_passed(self):
        self.assertTrue(self.result["infrastructure_repair"]["repair_passed"])
        self.assertTrue(self.result["clone"]["completed"])
        self.assertTrue(self.result["install"]["completed"])
        self.assertTrue(self.result["demo"]["completed"])
        self.assertEqual(self.result["demo"]["network_attempt_count"], 0)
        answer = self.result["demo"]["answer"]
        self.assertEqual(
            (answer["subject_id"], answer["status"], answer["location_id"], answer["epistemic_status"]),
            ("key", "FOUND", "sofa", "estimated"),
        )
        self.assertEqual(answer["relation_path"], ["key|inside|bag", "bag|at_zone|sofa"])
        self.assertEqual(answer["operate"], "DISABLED")

    def test_lock_failure_is_exact_crlf_checkout_normalization(self):
        lock = self.result["lock_diagnostic"]
        self.assertEqual(lock["contract_sha256"], lock["git_blob_sha256"])
        self.assertNotEqual(lock["git_blob_sha256"], lock["clean_checkout_raw_sha256"])
        self.assertEqual(lock["git_blob_crlf_count"], 0)
        self.assertEqual(lock["clean_checkout_crlf_count"], lock["line_count"])
        self.assertTrue(lock["uv_sync_frozen_succeeded"])
        self.assertTrue(lock["manifest_sha256_matched"])

    def test_cleanup_passed_and_claims_remain_bounded(self):
        self.assertTrue(self.result["cleanup"]["clone_removed"])
        self.assertTrue(self.result["cleanup"]["cache_removed"])
        self.assertFalse(self.result["cleanup"]["retained_runtime_artifacts"])
        limits = self.result["claim_limits"]
        self.assertFalse(limits["m34_contract_passed"])
        self.assertTrue(limits["mechanical_clean_clone_install_observed_on_this_host"])
        self.assertFalse(limits["independent_teammate_or_other_platform_verified"])
        self.assertFalse(limits["cross_platform_raw_text_hash_stable"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))

    def test_next_gate_cannot_retry_acceptance(self):
        next_gate = self.result["next_gate"]
        self.assertEqual(next_gate["proposal"], "M35_VERSIONED_TEXT_IDENTITY_PORTABILITY")
        self.assertFalse(next_gate["acceptance_or_demo_retry_allowed"])
        self.assertFalse(next_gate["production_semantics_or_fixture_change_allowed"])


if __name__ == "__main__":
    unittest.main()
