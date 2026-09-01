"""Frozen no-media selection rules for M14."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m14-detector-priority-v1.toml"


class M14PriorityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exactly_two_candidates_and_stop_baseline_are_frozen(self):
        self.assertEqual(
            self.document["candidates"],
            ["dfine-medium-coco", "rt-detrv2-small-coco"],
        )
        self.assertEqual(self.document["stop_baseline"], "STOP_MODEL_SWAPPING")
        self.assertTrue(self.document["selection"]["exactly_one_candidate_required"])

    def test_material_same_protocol_gate_is_frozen(self):
        self.assertEqual(self.document["reference"]["ap75"], 52.6)
        self.assertEqual(self.document["reference"]["ap_small"], 29.1)
        rules = self.document["eligibility"]
        self.assertEqual(rules["minimum_gain_on_either_ap75_or_ap_small"], 3.0)
        self.assertEqual(rules["maximum_decline_on_other_metric"], 1.0)
        self.assertEqual(
            rules["maximum_simultaneous_params_flops_latency_ratio"], 2.5
        )
        self.assertTrue(rules["same_protocol_primary_source_required"])

    def test_artifact_metric_and_operation_shortcuts_are_denied(self):
        evidence = self.document["evidence_rules"]
        self.assertFalse(evidence["objects365_allowed"])
        self.assertFalse(evidence["community_conversion_counts_as_author_artifact"])
        self.assertFalse(evidence["community_conversion_inherits_author_metrics"])
        self.assertFalse(evidence["cross_paper_metric_fill_allowed"])
        self.assertTrue(evidence["missing_ap75_or_ap_small_is_failure"])
        self.assertTrue(
            all(value is False for value in self.document["boundaries"].values())
        )


if __name__ == "__main__":
    unittest.main()
