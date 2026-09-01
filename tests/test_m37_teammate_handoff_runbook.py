from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m37-teammate-handoff-runbook-v1.toml"


class M37ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_handoff_is_pinned_to_exact_public_revision_and_tools(self):
        self.assertEqual(
            self.contract["handoff_revision"],
            "f16a0a4f99ac97dce16430b70568a3f47613cc0d",
        )
        self.assertEqual(self.contract["python_version"], "3.12")
        self.assertEqual(self.contract["uv_version"], "0.11.24")
        self.assertEqual(len(self.contract["checker_sha256"]), 64)
        self.assertEqual(len(self.contract["uv_lock_git_blob_sha256"]), 64)
        checker = ROOT / self.contract["checker_path"]
        self.assertEqual(
            hashlib.sha256(checker.read_bytes()).hexdigest(),
            self.contract["checker_sha256"],
        )
        lock_blob = subprocess.run(
            ["git", "show", f'{self.contract["handoff_revision"]}:uv.lock'],
            cwd=ROOT,
            check=True,
            capture_output=True,
            shell=False,
        ).stdout
        self.assertEqual(
            hashlib.sha256(lock_blob).hexdigest(),
            self.contract["uv_lock_git_blob_sha256"],
        )

    def test_both_shell_families_and_every_runbook_section_are_required(self):
        self.assertTrue(all(self.contract["required_platforms"].values()))
        self.assertTrue(all(self.contract["required_sections"].values()))
        self.assertTrue(all(self.contract["required_workflow"].values()))

    def test_receipt_keeps_version_authority_and_representation_distinct(self):
        self.assertEqual(
            self.contract["required_receipt"]["identity_fields"],
            [
                "uv_lock_git_blob_sha256",
                "uv_lock_worktree_sha256",
                "uv_lock_worktree_representation_matches_git_blob",
            ],
        )
        self.assertTrue(
            self.contract["required_interpretation"][
                "representation_match_false_can_be_diagnostic"
            ]
        )

    def test_document_gate_cannot_claim_or_execute_a_teammate_drill(self):
        boundaries = self.contract["boundaries"]
        self.assertTrue(all(value is False for value in boundaries.values()))
        self.assertFalse(
            self.contract["verification_profile"][
                "clone_install_demo_or_checker_acceptance_allowed"
            ]
        )
        self.assertTrue(self.contract["next_gate"]["requires_real_teammate_receipt"])
        self.assertTrue(self.contract["next_gate"]["agent_generated_receipt_is_ineligible"])


if __name__ == "__main__":
    unittest.main()
