"""Evidence-bound checks for the M44 packaging stop."""

from __future__ import annotations

import tomllib
import unittest

from tools.prepare_m44_cache import CONTRACT, ROOT


RESULT = ROOT / "configs" / "evaluation" / "m44-explicit-cache-packaging-result-v1.toml"


class M44ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_is_the_one_attempt_normal_stop(self):
        self.assertEqual(self.result["decision"], self.contract["decision"]["normal_stop"])
        self.assertEqual(self.result["package_attempts_started"], 1)
        self.assertEqual(self.result["attempt_limit"], 1)
        self.assertFalse(self.result["additional_retry_used"])
        self.assertFalse(self.result["additional_retry_authorized"])

    def test_decode_and_receipt_failure_is_not_a_build_pass(self):
        stop = self.result["stop"]
        self.assertEqual(stop["background_decode_exception"], "UnicodeDecodeError")
        self.assertEqual(stop["implicit_text_encoding"], "cp950")
        self.assertEqual(stop["runner_exception"], "AttributeError")
        self.assertFalse(stop["runner_receipt_emitted"])
        self.assertFalse(stop["build_process_return_code_retained"])

    def test_partial_sdist_forensics_are_exact_and_fail_closed(self):
        sdist = self.result["sdist_forensics"]
        self.assertTrue(sdist["created"])
        self.assertEqual(
            sdist["sha256"],
            "44e16a69d1fcd72aa3492306db9ba4d9a4b1d4d3d423c62627b27faf3433dd91",
        )
        self.assertEqual(sdist["presentation_sha256"], self.contract["frozen_input"]["presentation_module_sha256"])
        self.assertFalse(sdist["m41_sdist_content_contract_passed"])
        self.assertEqual(sdist["missing_required_members"], ["uv.lock"])
        self.assertFalse(self.result["wheel_forensics"]["created"])

    def test_install_and_demo_were_not_reached(self):
        stages = self.result["stage_reachability"]
        self.assertTrue(stages["build_process_started"])
        self.assertFalse(stages["fresh_venv_started"])
        self.assertFalse(stages["wheel_install_started"])
        self.assertFalse(stages["installed_demo_started"])
        self.assertFalse(stages["python_socket_guard_started"])

    def test_cleanup_is_complete(self):
        cleanup = self.result["cleanup"]
        self.assertTrue(cleanup["source_worktree_removed"])
        self.assertTrue(cleanup["cache_target_removed"])
        self.assertTrue(cleanup["dist_removed"])
        self.assertTrue(cleanup["venv_absent"])
        self.assertTrue(cleanup["run_root_removed"])
        self.assertFalse(cleanup["generated_artifact_or_cache_retained"])

    def test_claims_and_authority_remain_bounded(self):
        self.assertTrue(all(value is False for value in self.result["claim_limits"].values()))
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
