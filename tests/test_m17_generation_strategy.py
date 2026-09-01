"""Frozen no-media generation-strategy rules for M17."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m17-generation-strategy-v1.toml"


class M17GenerationStrategyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exactly_three_concrete_candidates_and_stop_are_frozen(self):
        self.assertEqual(
            self.document["candidates"],
            [
                "existing-project-vector-2d",
                "blender-python-headless-3d",
                "kubric-licensed-asset-compositing",
            ],
        )
        self.assertEqual(
            self.document["stop_baseline"],
            "STOP_NO_FEASIBLE_GENERATION_STRATEGY",
        )

    def test_d1_and_split_requirements_cannot_be_traded_for_realism(self):
        required = self.document["required_output"]
        self.assertTrue(
            all(
                value is True
                for key, value in required.items()
                if key != "small_object_area_fraction_range"
            )
        )
        self.assertEqual(required["small_object_area_fraction_range"], [0.001, 0.01])
        split = self.document["split_integrity"]
        self.assertFalse(split["protected_factor_cross_split_allowed"])
        self.assertTrue(split["split_assignment_before_render_or_result"])
        self.assertFalse(self.document["evidence_rules"]["unmeasured_realism_claim_allowed"])

    def test_cost_and_single_strategy_limits_are_bounded(self):
        cost = self.document["cost"]
        self.assertEqual(cost["first_d1_conformant_slice_max_working_hours"], 8)
        self.assertEqual(cost["complete_frozen_substrate_max_calendar_days"], 3)
        self.assertEqual(cost["maximum_complete_substrate_gib"], 20.0)
        selection = self.document["selection"]
        self.assertTrue(selection["select_at_most_one"])
        self.assertEqual(
            selection["unresolved_multiple_decision"],
            "STOP_OR_PIVOT_NO_MULTI_GENERATOR_BUILD",
        )

    def test_all_install_media_model_claim_and_operation_boundaries_are_false(self):
        self.assertTrue(
            all(value is False for value in self.document["boundaries"].values())
        )


if __name__ == "__main__":
    unittest.main()
