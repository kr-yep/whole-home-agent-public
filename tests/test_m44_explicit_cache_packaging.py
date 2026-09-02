"""Contract and tooling tests for the M44 explicit-cache packaging gate."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest

from tools.prepare_m44_cache import (
    CONTRACT,
    ROOT,
    copy_subset,
    tree_identity,
    validate_identity,
)
from tools.run_m44_packaging import (
    build_command,
    install_command,
    sanitized_environment,
    venv_command,
)


class M44ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_freezes_m43_m41_checker_and_product_inputs(self):
        frozen = self.document["frozen_input"]
        for path_key, hash_key in (
            ("m43_result", "m43_result_sha256"),
            ("m41_contract", "m41_contract_sha256"),
            ("m41_checker", "m41_checker_sha256"),
        ):
            self.assertEqual(
                hashlib.sha256((ROOT / frozen[path_key]).read_bytes()).hexdigest(),
                frozen[hash_key],
            )
        self.assertEqual(
            hashlib.sha256((ROOT / "pyproject.toml").read_bytes()).hexdigest(),
            frozen["pyproject_sha256"],
        )

    def test_contract_is_one_offline_attempt_with_closed_boundaries(self):
        self.assertEqual(self.document["attempt_limit"], 1)
        self.assertFalse(self.document["additional_retry_allowed"])
        self.assertFalse(self.document["decision"]["normal_stop_authorizes_retry"])
        self.assertFalse(self.document["environment"]["os_level_network_instrumented"])
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))

    def test_cache_provenance_limit_and_exact_exclusion_are_explicit(self):
        cache = self.document["cache_source"]
        self.assertEqual(
            cache["excluded_prefixes"], ["sdists-v9/editable/", "interpreter-v4/"]
        )
        self.assertEqual(cache["excluded_file_count"], 13)
        self.assertEqual(cache["excluded_local_absolute_path_metadata_files"], 7)
        self.assertFalse(cache["upstream_provenance_independently_authenticated"])


class M44CacheTests(unittest.TestCase):
    def test_tree_identity_and_byte_copy_exclude_editable_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            target = root / "target"
            (source / "archive-v0" / "package").mkdir(parents=True)
            (source / "archive-v0" / "package" / "file.py").write_text("x\n", encoding="utf-8")
            (source / "sdists-v9" / "editable" / "blocked").mkdir(parents=True)
            (source / "sdists-v9" / "editable" / "blocked" / "local.whl").write_bytes(b"no")
            excluded = ("sdists-v9/editable/",)
            expected = tree_identity(source, excluded)
            copy_subset(source, target, excluded)
            actual = tree_identity(target, ())

        self.assertEqual(actual, expected)
        self.assertEqual(expected["file_count"], 1)
        self.assertEqual(expected["forbidden_paths"], [])

    def test_forbidden_sensitive_cache_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "archive-v0").mkdir()
            (root / "archive-v0" / "private.key").write_bytes(b"secret")
            identity = tree_identity(root, ())
            expected = {
                "included_file_count": identity["file_count"],
                "included_bytes": identity["total_bytes"],
                "included_tree_sha256": identity["tree_sha256"],
                "reparse_point_count": identity["reparse_point_count"],
                "metadata_credential_pattern_count": identity["metadata_credential_pattern_count"],
            }
            failures = validate_identity(identity, expected)
        self.assertIn("CACHE_SOURCE_FORBIDDEN_PATH", failures)


class M44RunnerTests(unittest.TestCase):
    def test_commands_are_explicit_cache_offline_and_non_editable(self):
        build = build_command(Path("uv"), Path("python"), Path("cache"), Path("dist"))
        venv = venv_command(Path("uv"), Path("python"), Path("cache"), Path("venv"))
        install = install_command(
            Path("uv"), Path("venv-python"), Path("cache"), Path("package.whl")
        )
        for command in (build, venv, install):
            self.assertIn("--offline", command)
            self.assertIn("--no-config", command)
            self.assertIn("--no-python-downloads", command)
            self.assertIn("--cache-dir", command)
        self.assertIn("--no-build-isolation", build)
        self.assertNotIn("--editable", install)
        self.assertTrue(install[-1].endswith("package.whl[demo]"))

    def test_sanitized_environment_drops_registry_proxy_and_tokens(self):
        environment = sanitized_environment(
            {
                "PATH": "safe",
                "SYSTEMROOT": "root",
                "HTTPS_PROXY": "drop",
                "UV_INDEX_URL": "drop",
                "UV_TOKEN": "drop",
            },
            Path("cache"),
        )
        self.assertEqual(environment["UV_OFFLINE"], "1")
        self.assertEqual(environment["UV_NO_CONFIG"], "1")
        self.assertEqual(environment["UV_PYTHON_DOWNLOADS"], "never")
        self.assertNotIn("HTTPS_PROXY", environment)
        self.assertNotIn("UV_INDEX_URL", environment)
        self.assertNotIn("UV_TOKEN", environment)

    def test_tools_launch_directly_without_pythonpath(self):
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        for relative in ("tools/prepare_m44_cache.py", "tools/run_m44_packaging.py"):
            process = subprocess.run(
                [sys.executable, "-B", str(ROOT / relative), "--help"],
                cwd=ROOT.parent,
                check=False,
                capture_output=True,
                text=True,
                shell=False,
                env=environment,
            )
            self.assertEqual(process.returncode, 0, process.stderr)


if __name__ == "__main__":
    unittest.main()
