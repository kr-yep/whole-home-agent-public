"""Frozen static contract for the M33 teammate handoff drill."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m33-teammate-clean-install-demo-drill-v1.toml"
CHECKER = ROOT / "tools" / "check_teammate_drill.py"


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


if __name__ == "__main__":
    unittest.main()
