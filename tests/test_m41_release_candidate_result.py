"""Evidence-bound result checks for the stopped M41 packaging attempt."""

from __future__ import annotations

import tomllib
import unittest

from tools.check_m41_release_candidate import CONTRACT, ROOT


RESULT = ROOT / "configs" / "evaluation" / "m41-release-candidate-packaging-result-v1.toml"


class M41ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_attempt_stops_before_artifact_without_retry(self):
        self.assertEqual(self.result["decision"], self.contract["decision"]["normal_stop"])
        self.assertEqual(self.result["attempts_started"], 1)
        self.assertEqual(self.result["attempt_limit"], 1)
        self.assertFalse(self.result["additional_retry_used"])
        self.assertFalse(self.result["additional_retry_authorized"])
        self.assertEqual(self.result["build"]["sdist_count"], 0)
        self.assertEqual(self.result["build"]["wheel_count"], 0)

    def test_failure_is_bounded_to_cache_initialization(self):
        failure = self.result["failure"]
        self.assertEqual(failure["stage"], "UV_CACHE_INITIALIZATION")
        self.assertFalse(failure["root_cause_established"])
        self.assertFalse(failure["product_code_reached"])
        self.assertFalse(failure["install_started"])
        self.assertFalse(failure["demo_started"])

    def test_network_claim_does_not_exceed_instrumentation(self):
        network = self.result["network"]
        self.assertTrue(network["uv_offline_flag_set"])
        self.assertFalse(network["os_level_network_instrumented"])
        self.assertEqual(network["network_attempt_count"], -1)

    def test_cleanup_and_authority_remain_closed(self):
        cleanup = self.result["cleanup"]
        self.assertTrue(cleanup["worktree_removed"])
        self.assertTrue(cleanup["dist_removed"])
        self.assertTrue(cleanup["venv_removed_or_never_created"])
        self.assertTrue(cleanup["run_root_removed"])
        self.assertFalse(cleanup["artifact_retained"])
        self.assertFalse(self.result["claim_limits"]["authorizes_retry"])
        self.assertFalse(self.result["claim_limits"]["authorizes_push"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
