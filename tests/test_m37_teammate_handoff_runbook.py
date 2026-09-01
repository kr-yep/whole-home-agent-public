from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m37-teammate-handoff-runbook-v1.toml"
RUNBOOK = ROOT / "docs" / "teammate-handoff-runbook.md"
RESULT = ROOT / "configs" / "evaluation" / "m37-teammate-handoff-runbook-result-v1.toml"


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
        # GitHub Actions intentionally uses a depth-1 checkout. The handoff revision is
        # frozen above; verify that the retained lock identity is still the current
        # committed blob without requiring unrelated historical objects locally.
        lock_blob = subprocess.run(
            ["git", "show", "HEAD:uv.lock"],
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


class M37RunbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.runbook = RUNBOOK.read_text(encoding="utf-8")

    def test_exact_revision_and_both_shell_workflows_are_present(self):
        self.assertIn(self.contract["handoff_revision"], self.runbook)
        self.assertIn("## Windows PowerShell procedure", self.runbook)
        self.assertIn("## macOS/Linux Bash or Zsh procedure", self.runbook)
        self.assertIn("git -C $DrillRoot checkout --detach $ApprovedRevision", self.runbook)
        self.assertIn('git -C "$DRILL_ROOT" checkout --detach "$APPROVED_REVISION"', self.runbook)
        self.assertIn("uv sync --frozen --extra demo", self.runbook)
        self.assertIn("tools\\check_teammate_drill.py", self.runbook)
        self.assertIn("tools/check_teammate_drill.py", self.runbook)

    def test_receipt_interpretation_keeps_all_required_fields_visible(self):
        for fields in self.contract["required_receipt"].values():
            for field in fields:
                self.assertIn(field, self.runbook)
        self.assertIn("Exit `2` means a bounded `STOP`", self.runbook)
        self.assertIn("may be `false` on a clean CRLF", self.runbook)

    def test_troubleshooting_cleanup_demo_and_result_template_are_explicit(self):
        for heading in (
            "## Failure classes and next action",
            "## Git, uv, and Windows ACL troubleshooting",
            "## 90-second presentation and CLI fallback",
            "## Safe cleanup",
            "## Teammate result template",
            "## Claim limits",
        ):
            self.assertIn(heading, self.runbook)
        self.assertIn("Remove-Item -LiteralPath $ResolvedDrillRoot", self.runbook)
        self.assertIn('rm -rf -- "$DRILL_ROOT"', self.runbook)
        self.assertNotIn("rm -rf /", self.runbook)
        self.assertNotIn("safe.directory '*'", self.runbook)

    def test_runbook_does_not_promote_missing_external_evidence(self):
        self.assertIn("one real teammate", self.runbook)
        self.assertIn("does not establish another unreported platform", self.runbook)
        self.assertIn("`OPERATE` must remain `DISABLED`", self.runbook)
        self.assertNotIn("independent teammate verified", self.runbook.lower())


class M37ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_document_gate_passes_with_every_deliverable(self):
        self.assertEqual(self.result["decision"], "PASS_M37_TEAMMATE_HANDOFF_RUNBOOK")
        self.assertTrue(all(self.result["deliverable"].values()))
        self.assertEqual(
            hashlib.sha256(RUNBOOK.read_bytes()).hexdigest(),
            self.result["runbook_sha256"],
        )

    def test_external_success_and_runtime_claims_remain_closed(self):
        self.assertTrue(all(value is False for value in self.result["claim_limits"].values()))
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))
        self.assertFalse(self.result["verification"]["full_regression_is_teammate_acceptance"])

    def test_next_gate_is_paused_instead_of_auto_started(self):
        self.assertEqual(
            self.result["next_gate"]["status"], "PAUSED_AWAITING_USER_DIRECTION"
        )
        self.assertFalse(self.result["next_gate"]["auto_start"])
        self.assertTrue(
            self.result["next_gate"]["real_teammate_receipt_required_for_handoff_claim"]
        )


if __name__ == "__main__":
    unittest.main()
