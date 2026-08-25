"""Executable composition checks for the capability-negative B0 profile.

These are source/wiring witnesses, not an OS sandbox or production security proof.
"""

from __future__ import annotations

import ast
import contextlib
import importlib
import io
import json
import tomllib
import unittest
from pathlib import Path

from whole_home_agent.cli import main


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "src" / "whole_home_agent"
FIXTURE_ROOT = REPO_ROOT / "examples" / "fixtures"


class B0CompositionBoundaryTests(unittest.TestCase):
    def test_runtime_dependency_list_is_empty(self):
        configuration = tomllib.loads(
            (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(configuration["project"]["dependencies"], [])

    def test_source_does_not_import_deferred_operational_capabilities(self):
        forbidden_roots = {
            "cv2",
            "httpx",
            "paho",
            "requests",
            "serial",
            "socket",
            "sqlite3",
            "subprocess",
            "torch",
            "transformers",
            "ultralytics",
        }
        violations: list[str] = []

        for path in sorted(SOURCE_ROOT.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name.split(".", 1)[0] in forbidden_roots:
                        violations.append(f"{path.name}:{node.lineno}:{name}")

        self.assertEqual(violations, [])

    def test_importing_main_module_does_not_start_the_cli(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            imported = importlib.import_module("whole_home_agent.__main__")

        self.assertIsNotNone(imported)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_cli_happy_path_and_action_shaped_denial_are_structured(self):
        happy_stdout = io.StringIO()
        happy_stderr = io.StringIO()
        with contextlib.redirect_stdout(happy_stdout), contextlib.redirect_stderr(
            happy_stderr
        ):
            happy_exit = main(
                [
                    "replay",
                    str(FIXTURE_ROOT / "b0_key_bag_sofa_v1.json"),
                    "--entity",
                    "key",
                    "--as-of",
                    "2",
                    "--run-id",
                    "boundary-test-run",
                ]
            )

        happy = json.loads(happy_stdout.getvalue())
        self.assertEqual(happy_exit, 0)
        self.assertEqual(happy_stderr.getvalue(), "")
        self.assertEqual(happy["answer"]["status"], "FOUND")
        self.assertEqual(happy["answer"]["location_id"], "sofa")
        self.assertEqual(happy["answer"]["replay_run_id"], "boundary-test-run")

        denied_stdout = io.StringIO()
        denied_stderr = io.StringIO()
        with contextlib.redirect_stdout(denied_stdout), contextlib.redirect_stderr(
            denied_stderr
        ):
            denied_exit = main(
                [
                    "replay",
                    str(FIXTURE_ROOT / "b0_action_shaped_v1.json"),
                    "--entity",
                    "key",
                    "--as-of",
                    "0",
                ]
            )

        denied = json.loads(denied_stderr.getvalue())
        self.assertEqual(denied_exit, 2)
        self.assertEqual(denied_stdout.getvalue(), "")
        self.assertEqual(denied["error_code"], "unknown_field")


if __name__ == "__main__":
    unittest.main()
