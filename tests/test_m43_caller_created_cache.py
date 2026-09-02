"""Contract and checker tests for M43 caller-created cache semantics."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

from tools.check_m43_caller_created_cache import CONTRACT, ROOT, run_preflight, validate_absent_target


class M43ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_freezes_m42_stop_and_separates_responsibilities(self):
        result = ROOT / self.document["m42_result"]
        self.assertEqual(hashlib.sha256(result.read_bytes()).hexdigest(), self.document["m42_result_sha256"])
        responsibility = self.document["responsibility"]
        self.assertTrue(responsibility["caller_creates_new_empty_cache"])
        self.assertTrue(responsibility["caller_proves_local_writability_before_uv"])
        self.assertTrue(responsibility["uv_only_confirms_selected_path"])
        self.assertFalse(responsibility["uv_expected_to_create_directory"])

    def test_contract_is_one_no_build_attempt_with_closed_boundaries(self):
        self.assertEqual(self.document["attempt_limit"], 1)
        self.assertFalse(self.document["additional_retry_allowed"])
        self.assertFalse(self.document["decision"]["normal_stop_authorizes_retry"])
        self.assertFalse(self.document["target"]["recursive_cleanup_inside_checker_allowed"])
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


def _prepare_root(directory: str) -> tuple[Path, Path]:
    root = Path(directory)
    (root / ".tmp").mkdir()
    (root / ".gitignore").write_text(".tmp/\n", encoding="utf-8")
    return root, root / ".tmp" / "m43-uv-cache"


class M43CheckerTests(unittest.TestCase):
    def test_checker_can_launch_directly_outside_repository_without_pythonpath(self):
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        process = subprocess.run(
            [sys.executable, "-B", str(ROOT / "tools" / "check_m43_caller_created_cache.py"), "--help"],
            cwd=ROOT.parent,
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            env=environment,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("--cache-root", process.stdout)

    def test_target_must_be_exact_and_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root, target = _prepare_root(directory)
            self.assertEqual(validate_absent_target(target, root), [])
            self.assertIn("CACHE_PATH", validate_absent_target(root / ".tmp" / "other", root))
            target.mkdir()
            self.assertIn("CACHE_NOT_NEW", validate_absent_target(target, root))

    def test_fake_uv_path_confirmation_passes_and_checker_cleans(self):
        with tempfile.TemporaryDirectory() as directory:
            root, target = _prepare_root(directory)

            def fake_runner(command, **kwargs):
                self.assertFalse(kwargs["shell"])
                self.assertNotIn("HTTPS_PROXY", kwargs["env"])
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "uv 0.11.24 (build)\n", "")
                self.assertTrue(target.is_dir())
                return subprocess.CompletedProcess(command, 0, f"{target}\n", "")

            receipt = run_preflight(
                Path("uv"),
                target,
                root=root,
                source_environment={"PATH": "safe", "HTTPS_PROXY": "drop"},
                runner=fake_runner,
            )

            self.assertEqual(receipt["status"], "PASS")
            self.assertTrue(receipt["responsibility"]["caller_created_directory"])
            self.assertTrue(receipt["responsibility"]["caller_write_probe_passed"])
            self.assertTrue(receipt["responsibility"]["uv_only_confirmed_path"])
            self.assertTrue(receipt["cache"]["target_removed_non_recursively"])
            self.assertFalse(target.exists())

    def test_uv_residue_fails_non_recursive_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root, target = _prepare_root(directory)

            def fake_runner(command, **_kwargs):
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "uv 0.11.24\n", "")
                (target / "unexpected-entry").write_text("x", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, f"{target}\n", "")

            receipt = run_preflight(Path("uv"), target, root=root, runner=fake_runner)

        self.assertEqual(receipt["status"], "STOP")
        self.assertIn("CACHE_NOT_EMPTY_OR_CLEANUP", receipt["failure_classes"])
        self.assertTrue(receipt["cleanup_required"])

    def test_existing_target_stops_before_process_or_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root, target = _prepare_root(directory)
            target.mkdir()
            calls = []

            def fake_runner(command, **_kwargs):
                calls.append(command)
                raise AssertionError("runner must remain closed")

            receipt = run_preflight(Path("uv"), target, root=root, runner=fake_runner)

        self.assertEqual(receipt["status"], "STOP")
        self.assertEqual(calls, [])
        self.assertIn("CACHE_NOT_NEW", receipt["failure_classes"])

    def test_no_build_install_or_demo_surface_exists(self):
        source = (ROOT / "tools" / "check_m43_caller_created_cache.py").read_text(encoding="utf-8")
        self.assertNotIn("uv build", source)
        self.assertNotIn("uv pip", source)
        self.assertNotIn("demo-recorded", source)


if __name__ == "__main__":
    unittest.main()
