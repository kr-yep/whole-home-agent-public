"""Evidence-bound checks for the stopped M42 cache preflight."""

from __future__ import annotations

import tomllib
import unittest

from tools.check_m42_uv_cache_preflight import CONTRACT, ROOT


RESULT = ROOT / "configs" / "evaluation" / "m42-uv-cache-path-preflight-result-v1.toml"


class M42ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_is_the_frozen_stop_without_retry(self):
        self.assertEqual(self.result["decision"], self.contract["decision"]["normal_stop"])
        self.assertEqual(self.result["attempts_started"], 1)
        self.assertEqual(self.result["attempt_limit"], 1)
        self.assertFalse(self.result["additional_retry_used"])
        self.assertFalse(self.result["additional_retry_authorized"])

    def test_uv_accepted_path_but_did_not_initialize_it(self):
        self.assertEqual(self.result["uv"]["cache_command_exit_code"], 0)
        self.assertTrue(self.result["uv"]["stdout_matched_exact_target"])
        self.assertEqual(self.result["result"]["failure_class"], "CACHE_NOT_INITIALIZED")
        self.assertFalse(self.result["result"]["target_directory_created_by_uv"])
        self.assertFalse(self.result["result"]["write_probe_started"])

    def test_claims_do_not_promote_path_echo_to_writability_or_network_proof(self):
        claims = self.result["claim_limits"]
        self.assertTrue(claims["establishes_explicit_cache_path_is_accepted_and_reported"])
        self.assertFalse(claims["establishes_cache_directory_initialization"])
        self.assertFalse(claims["establishes_cache_writability"])
        self.assertFalse(claims["establishes_zero_os_network_attempts"])
        self.assertFalse(claims["authorizes_packaging_attempt"])

    def test_cleanup_and_authority_are_closed(self):
        cleanup = self.result["cleanup"]
        self.assertTrue(cleanup["target_absent_after_attempt"])
        self.assertTrue(cleanup["empty_temp_parent_removed"])
        self.assertFalse(cleanup["cache_or_probe_retained"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
