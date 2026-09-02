"""Frozen static contract for the M33 teammate handoff drill."""

from __future__ import annotations

import hashlib
import subprocess
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m33-teammate-clean-install-demo-drill-v1.toml"
CHECKER = ROOT / "tools" / "check_teammate_drill.py"
RESULT = ROOT / "configs" / "evaluation" / "m33-teammate-clean-install-demo-drill-result-v1.toml"


class M33ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_one_disposable_attempt_and_exact_public_source_are_frozen(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_PUBLIC_CLONE")
        self.assertEqual(self.document["attempt_limit"], 1)
        self.assertEqual(
            self.document["source_repository"],
            "https://github.com/kr-yep/whole-home-agent-public.git",
        )
        self.assertTrue(self.document["environment"]["disposable_clone_must_be_outside_source_checkout"])
        self.assertTrue(self.document["environment"]["cleanup_required"])

    def test_text_inputs_are_hash_pinned_and_media_is_not_opened(self):
        for record in self.document["frozen_text_input"]:
            path = ROOT / record["path"]
            self.assertNotIn(path.suffix.lower(), {".mp4", ".png", ".jpg", ".webm"})
            if record["path"] == "README.md":
                self.assertEqual(
                    record["sha256"],
                    "24d3efa8b0ed960b7c27409392778cfb0e7a77669ed711db6ef4871499fffece",
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
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])

    def test_network_is_install_only_and_demo_is_closed(self):
        network = self.document["network"]
        self.assertTrue(network["public_git_clone_allowed"])
        self.assertTrue(network["public_python_package_install_allowed"])
        self.assertFalse(network["demo_network_allowed"])
        self.assertFalse(network["private_registry_or_credential_allowed"])
        self.assertFalse(network["cloud_inference_or_external_source_allowed"])

    def test_expected_answer_and_boundaries_are_exact(self):
        answer = self.document["expected_answer"]
        self.assertEqual(
            (answer["subject_id"], answer["status"], answer["location_id"], answer["epistemic_status"]),
            ("key", "FOUND", "sofa", "estimated"),
        )
        self.assertEqual(answer["relation_path"], ["key|inside|bag", "bag|at_zone|sofa"])
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))

    def test_checker_has_network_guard_receipt_and_no_m29_import(self):
        source = CHECKER.read_text(encoding="utf-8")
        self.assertIn("def _deny_network", source)
        self.assertIn("def validate_payload", source)
        self.assertIn('"semantic_sha256"', source)
        self.assertNotIn("check_primary_demo", source)


class M33ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_one_attempt_stops_before_install_on_exact_infrastructure_failure(self):
        self.assertEqual(self.result["decision"], "STOP_M33_TEAMMATE_HANDOFF_DRILL")
        self.assertEqual(self.result["attempt_count"], self.result["attempt_limit"])
        self.assertEqual(self.result["failure_classes"], ["INSTALL"])
        self.assertEqual(self.result["failure_code"], "UV_VERSION_OUTPUT_FORMAT")
        self.assertFalse(self.result["install"]["uv_sync_started"])
        self.assertFalse(self.result["demo"]["started"])

    def test_clone_was_exact_clean_and_cleaned_up(self):
        clone = self.result["clone"]
        self.assertTrue(clone["completed"])
        self.assertTrue(clone["head_matches_expected"])
        self.assertTrue(clone["worktree_clean"])
        self.assertTrue(self.result["cleanup"]["clone_removed"])
        self.assertTrue(self.result["cleanup"]["disposable_cache_removed"])
        self.assertFalse(self.result["cleanup"]["retained_runtime_artifacts"])

    def test_stop_claim_is_limited_to_preflight_orchestration(self):
        limits = self.result["claim_limits"]
        self.assertTrue(limits["stop_establishes_only_orchestration_preflight_failure"])
        self.assertFalse(limits["stop_establishes_repository_install_failure"])
        self.assertFalse(limits["stop_establishes_dependency_incompatibility"])
        self.assertFalse(limits["stop_establishes_demo_failure"])
        self.assertFalse(limits["clean_install_usability_verified"])

    def test_only_one_separately_frozen_infrastructure_retry_is_proposed(self):
        next_gate = self.result["next_gate"]
        self.assertEqual(next_gate["proposal"], "M34_SINGLE_INFRASTRUCTURE_RETRY")
        self.assertTrue(next_gate["same_contract_revision_required"])
        self.assertTrue(next_gate["same_source_thresholds_expected_output_and_boundaries_required"])
        self.assertFalse(next_gate["additional_retry_after_m34_allowed"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
