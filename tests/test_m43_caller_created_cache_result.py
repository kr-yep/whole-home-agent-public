"""Evidence-bound checks for the M43 caller-created cache result."""

from __future__ import annotations

import tomllib
import unittest

from tools.check_m43_caller_created_cache import CONTRACT, ROOT


RESULT = ROOT / "configs" / "evaluation" / "m43-caller-created-uv-cache-result-v1.toml"


class M43ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_is_the_bounded_pass_with_one_cache_attempt(self):
        self.assertEqual(self.result["decision"], self.contract["decision"]["pass"])
        self.assertEqual(self.result["cache_attempts_started"], 1)
        self.assertEqual(self.result["attempt_limit"], 1)
        self.assertFalse(self.result["additional_retry_used"])

    def test_pre_attempt_launch_failure_is_preserved_and_not_miscounted(self):
        failure = self.result["pre_attempt_launch_failure"]
        self.assertTrue(failure["occurred"])
        self.assertFalse(failure["target_created"])
        self.assertFalse(failure["probe_started"])
        self.assertFalse(failure["uv_process_started"])
        self.assertFalse(failure["counted_as_cache_attempt"])

    def test_responsibility_and_probe_are_exact(self):
        responsibility = self.result["responsibility"]
        self.assertTrue(responsibility["caller_created_new_empty_directory"])
        self.assertTrue(responsibility["caller_write_probe_passed"])
        self.assertTrue(responsibility["probe_removed_before_uv"])
        self.assertTrue(responsibility["uv_only_confirmed_selected_path"])
        self.assertFalse(responsibility["uv_expected_to_create_directory"])
        self.assertEqual(
            self.result["probe"]["sha256"],
            "fa1c6fde2dad49408d7d605ee73397ab22ca09d5c12898fc0ce52750cdbc87ae",
        )
        self.assertTrue(self.result["probe"]["probe_removed"])
        self.assertEqual(self.result["uv"]["cache_command_exit_code"], 0)
        self.assertTrue(self.result["uv"]["stdout_matched_exact_target"])

    def test_cleanup_is_complete_without_recursive_checker_deletion(self):
        cleanup = self.result["cleanup"]
        self.assertTrue(cleanup["target_removed_non_recursively"])
        self.assertTrue(cleanup["target_absent_after_checker"])
        self.assertTrue(cleanup["empty_temp_parent_removed"])
        self.assertFalse(cleanup["cache_probe_or_artifact_retained"])

    def test_claims_and_authority_remain_bounded(self):
        claims = self.result["claim_limits"]
        self.assertTrue(claims["establishes_caller_created_cache_semantics_on_this_host"])
        self.assertFalse(claims["establishes_package_build_install_or_demo"])
        self.assertFalse(claims["establishes_zero_os_network_attempts"])
        self.assertTrue(claims["authorizes_only_separately_frozen_m44_packaging_gate"])
        self.assertFalse(claims["authorizes_push"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
