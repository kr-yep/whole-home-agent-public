"""Tests for the fail-closed, standard-library public release audit."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.audit_public_release import AuditError, audit_repository, main


class PublicReleaseAuditTests(unittest.TestCase):
    def audit_root(self, root: Path, *, max_file_bytes: int = 1024):
        return audit_repository(root, scan_mode="root", max_file_bytes=max_file_bytes)

    def write(self, root: Path, relative: str, data: bytes | str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            path.write_bytes(data)
        return path

    def test_safe_source_and_placeholder_template_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "README.md", "Synthetic public fixture.\n")
            self.write(root, ".env.example", "API_KEY=placeholder\n")

            receipt = self.audit_root(root)

        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["violation_count"], 0)
        self.assertFalse(receipt["operate_enabled"])

    def test_sensitive_names_artifacts_archives_and_large_files_fail(self):
        cases = {
            "credentials.json": "sensitive_path",
            "server.key": "forbidden_artifact",
            "runtime.sqlite3": "forbidden_artifact",
            "model.safetensors": "forbidden_artifact",
            "debug.log": "forbidden_artifact",
            "bundle.zip": "forbidden_artifact",
        }
        for relative, expected_rule in cases.items():
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write(root, relative, b"safe")
                receipt = self.audit_root(root)
                rules = {item["rule_id"] for item in receipt["violations"]}
                self.assertIn(expected_rule, rules)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "large.txt", b"x" * 9)
            receipt = self.audit_root(root, max_file_bytes=8)
        self.assertIn("file_too_large", {item["rule_id"] for item in receipt["violations"]})

    def test_secret_email_and_local_home_path_content_fail_without_value_leakage(self):
        secret = "ghp_" + "A" * 36
        email = "person" + "@" + "example.com"
        local_path = "C:" + "\\Users\\Alice\\project"
        personal_id = "A" + "1" + "23456789"
        mobile = "09" + "12-345-678"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(
                root,
                "notes.txt",
                "\n".join(
                    (
                        secret,
                        email,
                        local_path,
                        personal_id,
                        mobile,
                        "client_" + "secret=" + "not-a-placeholder",
                    )
                ),
            )
            receipt = self.audit_root(root)

        rules = {item["rule_id"] for item in receipt["violations"]}
        self.assertTrue({"credential_content", "email_or_pii", "local_absolute_path"}.issubset(rules))
        serialized = json.dumps(receipt)
        self.assertNotIn(secret, serialized)
        self.assertNotIn(email, serialized)
        self.assertNotIn(local_path, serialized)
        self.assertNotIn(personal_id, serialized)
        self.assertNotIn(mobile, serialized)

    def test_lockfile_digests_do_not_trigger_structured_pii_false_positive(self):
        lock_line = (
            'url = "https://files.pythonhosted.org/packages/c8/e3/'
            'd119f86a01f9331e8186175f24873b1d74a7ee9e2e4b4d68f9947dae5afd/'
            'package.whl", hash = "sha256:'
            '09ce8f56e81f19b9c378ae7bb109f83f6659fd8bc3cd14241a48e4af46e9ed49"\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "uv.lock", lock_line)
            receipt = self.audit_root(root)

        self.assertEqual(receipt["status"], "PASS")

    def test_media_outside_allowlist_or_without_manifest_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "demo.mp4", b"not-real-video")
            self.write(root, "examples/media/generated/orphan.mp4", b"synthetic")
            receipt = self.audit_root(root)

        by_path = {(item["path"], item["rule_id"]) for item in receipt["violations"]}
        self.assertIn(("demo.mp4", "media_not_allowlisted"), by_path)
        self.assertIn(("examples/media/generated/orphan.mp4", "media_manifest_invalid"), by_path)

    def test_generated_media_with_valid_sidecar_manifest_passes(self):
        media = b"project-generated synthetic media bytes"
        digest = hashlib.sha256(media).hexdigest()
        manifest = {
            "path": "demo.mp4",
            "sha256": digest,
            "license": "CC0-1.0",
            "use_class": "D0_SYNTHETIC",
            "provenance": {"kind": "project_generated_synthetic", "generator": "test"},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "examples/media/generated/demo.mp4", media)
            self.write(root, "examples/media/generated/demo.mp4.manifest.json", json.dumps(manifest))
            receipt = self.audit_root(root)

        self.assertEqual(receipt["status"], "PASS")

    def test_index_manifest_defaults_are_supported_and_invalid_hash_fails(self):
        media = b"synthetic-index-media"
        manifest = {
            "license": "CC0-1.0",
            "use_class": "D0_SYNTHETIC",
            "provenance": "project-generated-synthetic",
            "media": [{"path": "indexed.webm", "sha256": hashlib.sha256(media).hexdigest()}],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "examples/media/generated/indexed.webm", media)
            manifest_path = self.write(
                root,
                "examples/media/generated/media_manifest.json",
                json.dumps(manifest),
            )
            passing = self.audit_root(root)
            manifest["media"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            failing = self.audit_root(root)

        self.assertEqual(passing["status"], "PASS")
        self.assertIn("media_manifest_invalid", {item["rule_id"] for item in failing["violations"]})

    def test_git_mode_scans_index_and_changed_tracked_worktree_but_not_untracked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            tracked = self.write(root, "tracked.txt", "safe\n")
            subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
            self.write(root, "untracked.log", "ignored by git scan")

            clean_receipt = audit_repository(root, scan_mode="git")
            tracked.write_text("password=" + "working-tree-value" + "\n", encoding="utf-8")
            changed_receipt = audit_repository(root, scan_mode="git")

        self.assertEqual(clean_receipt["status"], "PASS")
        self.assertEqual(clean_receipt["scanned_file_count"], 1)
        self.assertEqual(changed_receipt["status"], "FAIL")
        self.assertIn(
            ("tracked.txt", "working_tree", "credential_content"),
            {(item["path"], item["snapshot"], item["rule_id"]) for item in changed_receipt["violations"]},
        )

    def test_staged_sensitive_file_is_a_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            self.write(root, "tokens.json", "{}")
            subprocess.run(["git", "-C", str(root), "add", "tokens.json"], check=True)
            receipt = audit_repository(root, scan_mode="git")

        self.assertEqual(receipt["status"], "FAIL")
        self.assertIn("sensitive_path", {item["rule_id"] for item in receipt["violations"]})

    def test_git_worktree_manifest_is_checked_against_unchanged_media(self):
        media = b"tracked synthetic media"
        manifest = {
            "path": "demo.mp4",
            "sha256": hashlib.sha256(media).hexdigest(),
            "license": "CC0-1.0",
            "use_class": "D0_SYNTHETIC",
            "provenance": {"kind": "project_generated_synthetic"},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            self.write(root, "examples/media/generated/demo.mp4", media)
            manifest_path = self.write(
                root,
                "examples/media/generated/demo.mp4.manifest.json",
                json.dumps(manifest),
            )
            subprocess.run(["git", "-C", str(root), "add", "examples"], check=True)
            passing = audit_repository(root, scan_mode="git")
            manifest["sha256"] = "f" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            failing = audit_repository(root, scan_mode="git")

        self.assertEqual(passing["status"], "PASS")
        self.assertIn(
            ("examples/media/generated/demo.mp4", "working_tree", "media_manifest_invalid"),
            {(item["path"], item["snapshot"], item["rule_id"]) for item in failing["violations"]},
        )

    def test_cli_prints_json_receipt_and_uses_nonzero_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write(root, "release.log", "diagnostic")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["--root", str(root), "--scan", "root"])
            receipt = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertGreater(receipt["violation_count"], 0)

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            error_exit = main(["--root", str(Path("missing-root")), "--scan", "root"])
        self.assertEqual(error_exit, 2)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "ERROR")

    def test_invalid_configuration_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(AuditError):
                audit_repository(Path(directory), scan_mode="root", max_file_bytes=0)


if __name__ == "__main__":
    unittest.main()
