"""Frozen contract and focused tests for M36 Git-blob identity hardening."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m36-checker-git-blob-identity-hardening-v1.toml"
CHECKER = ROOT / "tools" / "check_teammate_drill.py"


def _load_checker_module():
    spec = importlib.util.spec_from_file_location("m36_checker_under_test", CHECKER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load teammate checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
    return result.stdout.strip()


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


class M36ImplementationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = _load_checker_module()

    def make_repository(self, root: Path) -> Path:
        repository = root / "repo"
        repository.mkdir()
        _git(repository, "init")
        _git(repository, "config", "user.email", "m36@invalid")
        _git(repository, "config", "user.name", "M36 Fixture")
        _git(repository, "config", "core.autocrlf", "true")
        (repository / "uv.lock").write_bytes(b"version = 1\nvalue = 'same'\n")
        _git(repository, "add", "uv.lock")
        _git(repository, "commit", "-m", "fixture")
        return repository

    def test_lf_and_crlf_worktrees_share_one_git_blob_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = self.make_repository(Path(temporary_directory))
            path = repository / "uv.lock"
            blob_lf, worktree_lf, matches_lf = self.checker._versioned_text_hashes(
                path, repository_root=repository
            )
            path.unlink()
            _git(repository, "checkout", "--", "uv.lock")
            blob_crlf, worktree_crlf, matches_crlf = self.checker._versioned_text_hashes(
                path, repository_root=repository
            )
            self.assertEqual(blob_lf, blob_crlf)
            self.assertNotEqual(worktree_lf, worktree_crlf)
            self.assertTrue(matches_lf)
            self.assertFalse(matches_crlf)
            self.assertEqual(_git(repository, "status", "--porcelain"), "")

    def test_content_change_is_dirty_without_changing_committed_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = self.make_repository(Path(temporary_directory))
            path = repository / "uv.lock"
            blob_before, _, _ = self.checker._versioned_text_hashes(
                path, repository_root=repository
            )
            path.write_bytes(path.read_bytes() + b"tampered = true\n")
            blob_after, worktree_after, matches = self.checker._versioned_text_hashes(
                path, repository_root=repository
            )
            self.assertEqual(blob_before, blob_after)
            self.assertNotEqual(blob_after, worktree_after)
            self.assertFalse(matches)
            self.assertTrue(_git(repository, "status", "--porcelain"))

    def test_wrong_blob_hash_is_rejected_by_fatal_identity_check(self):
        contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        fake_contract = {
            "frozen_text_input": [{}, {"sha256": "a" * 64}],
            "expected_source": {"manifest_sha256": "b" * 64},
        }
        self.assertEqual(
            self.checker._validate_artifact_identity(
                lock_git_blob_sha256="c" * 64,
                manifest_sha256="b" * 64,
                contract=fake_contract,
            ),
            ["LOCK_OR_MANIFEST"],
        )
        self.assertEqual(contract["selected_candidate"], "A_GIT_BLOB_SHA256_PLUS_CLEAN_WORKTREE")

    def test_non_git_environment_fails_without_fallback(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            path = root / "uv.lock"
            path.write_text("version = 1\n", encoding="utf-8")
            with self.assertRaises(subprocess.CalledProcessError):
                self.checker._versioned_text_hashes(path, repository_root=root)

    def test_receipt_source_uses_three_explicit_fields(self):
        source = CHECKER.read_text(encoding="utf-8")
        self.assertIn('"uv_lock_git_blob_sha256"', source)
        self.assertIn('"uv_lock_worktree_sha256"', source)
        self.assertIn('"uv_lock_worktree_representation_matches_git_blob"', source)
        self.assertNotIn('"uv_lock_sha256"', source)


if __name__ == "__main__":
    unittest.main()
