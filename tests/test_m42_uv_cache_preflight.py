"""Contract and pure checker tests for the M42 no-build cache preflight."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest

from tools.check_m42_uv_cache_preflight import (
    CONTRACT,
    ROOT,
    run_preflight,
    sanitized_environment,
    target_has_exact_ignore_rule,
    uv_cache_command,
    validate_new_cache_root,
)


class M42ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_freezes_m41_stop_without_claiming_root_cause(self):
        result = ROOT / self.document["m41_result"]
        self.assertEqual(hashlib.sha256(result.read_bytes()).hexdigest(), self.document["m41_result_sha256"])
        self.assertFalse(self.document["prior_observation"]["root_cause_established"])
        self.assertFalse(self.document["prior_observation"]["default_cache_mutation_or_repair_allowed"])

    def test_contract_allows_one_no_build_attempt_and_no_retry(self):
        self.assertEqual(self.document["attempt_limit"], 1)
        self.assertEqual(self.document["uv"]["initialization_attempts"], 1)
        self.assertFalse(self.document["additional_retry_allowed"])
        self.assertFalse(self.document["decision"]["normal_stop_authorizes_retry"])
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


class M42CheckerTests(unittest.TestCase):
    def test_repository_target_has_exact_ignore_rule(self):
        self.assertTrue(target_has_exact_ignore_rule())

    def test_target_must_be_exact_new_non_symlink_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".tmp").mkdir()
            (root / ".gitignore").write_text(".tmp/\n", encoding="utf-8")
            target = root / ".tmp" / "m42-uv-cache"
            self.assertEqual(validate_new_cache_root(target, root), [])
            self.assertIn("CACHE_PATH", validate_new_cache_root(root / ".tmp" / "other", root))
            target.mkdir()
            self.assertIn("CACHE_NOT_NEW", validate_new_cache_root(target, root))

    def test_uv_command_is_closed_and_offline(self):
        command = uv_cache_command(Path("uv"), Path("cache"))
        self.assertEqual(command[-2:], ("cache", "dir"))
        self.assertIn("--offline", command)
        self.assertIn("--no-config", command)
        self.assertIn("--no-python-downloads", command)
        self.assertNotIn("build", command)
        self.assertNotIn("install", command)

    def test_environment_drops_proxy_index_and_token_values(self):
        environment = sanitized_environment(
            {
                "PATH": "safe-path",
                "SYSTEMROOT": "safe-root",
                "HTTPS_PROXY": "must-drop",
                "UV_INDEX_URL": "must-drop",
                "UV_TOKEN": "must-drop",
            },
            Path("cache"),
        )
        self.assertEqual(environment["PATH"], "safe-path")
        self.assertEqual(environment["UV_OFFLINE"], "1")
        self.assertEqual(environment["UV_NO_CONFIG"], "1")
        self.assertEqual(environment["UV_PYTHON_DOWNLOADS"], "never")
        self.assertNotIn("HTTPS_PROXY", environment)
        self.assertNotIn("UV_INDEX_URL", environment)
        self.assertNotIn("UV_TOKEN", environment)

    def test_fake_uv_initialization_and_probe_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".tmp").mkdir()
            (root / ".gitignore").write_text(".tmp/\n", encoding="utf-8")
            target = root / ".tmp" / "m42-uv-cache"

            def fake_runner(command, **kwargs):
                self.assertFalse(kwargs["shell"])
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "uv 0.11.24 (build)\n", "")
                target.mkdir()
                return subprocess.CompletedProcess(command, 0, f"{target}\n", "")

            receipt = run_preflight(
                Path("uv"), target, root=root, source_environment=os.environ, runner=fake_runner
            )

            self.assertEqual(receipt["status"], "PASS")
            self.assertTrue(receipt["cache"]["initialized"])
            self.assertTrue(receipt["cache"]["write_probe_removed"])
            self.assertFalse(receipt["build_install_or_demo_started"])

    def test_missing_uv_created_directory_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".tmp").mkdir()
            (root / ".gitignore").write_text(".tmp/\n", encoding="utf-8")
            target = root / ".tmp" / "m42-uv-cache"

            def fake_runner(command, **_kwargs):
                if command[-1] == "--version":
                    return subprocess.CompletedProcess(command, 0, "uv 0.11.24\n", "")
                return subprocess.CompletedProcess(command, 0, f"{target}\n", "")

            receipt = run_preflight(Path("uv"), target, root=root, runner=fake_runner)

        self.assertEqual(receipt["status"], "STOP")
        self.assertIn("CACHE_NOT_INITIALIZED", receipt["failure_classes"])

    def test_existing_target_stops_before_any_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".tmp" / "m42-uv-cache").mkdir(parents=True)
            (root / ".gitignore").write_text(".tmp/\n", encoding="utf-8")
            calls = []

            def fake_runner(command, **_kwargs):
                calls.append(command)
                raise AssertionError("runner must remain closed")

            receipt = run_preflight(
                Path("uv"), root / ".tmp" / "m42-uv-cache", root=root, runner=fake_runner
            )

        self.assertEqual(receipt["status"], "STOP")
        self.assertEqual(calls, [])
        self.assertIn("CACHE_NOT_NEW", receipt["failure_classes"])


if __name__ == "__main__":
    unittest.main()
