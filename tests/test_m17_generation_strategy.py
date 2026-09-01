"""Frozen no-media generation-strategy rules for M17."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m17-generation-strategy-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m17-generation-strategy-result-v1.toml"


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


class M17GenerationStrategyResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_candidate_matrix_is_exact_and_three_state(self):
        candidates = self.result["candidates"]
        self.assertEqual(list(candidates), self.contract["candidates"])
        required = set(self.result["required_gate_order"])
        self.assertTrue(required)
        for candidate in candidates.values():
            self.assertEqual(set(candidate["gates"]), required)
            self.assertLessEqual(set(candidate["gates"].values()), {"PASS", "FAIL", "UNKNOWN"})

    def test_eligibility_is_the_and_of_direct_passes(self):
        computed = [
            name
            for name, candidate in self.result["candidates"].items()
            if all(status == "PASS" for status in candidate["gates"].values())
        ]
        self.assertEqual(computed, self.result["eligible_candidates"])
        self.assertEqual(len(computed), self.result["eligible_count"])
        self.assertEqual(computed, ["existing-project-vector-2d"])

    def test_single_eligible_candidate_selects_only_the_frozen_next_authority(self):
        selection = self.result["selection"]
        self.assertEqual(self.result["selected_candidate"], "existing-project-vector-2d")
        self.assertFalse(self.result["tie_break_applied"])
        self.assertEqual(
            selection["next_authority"],
            self.contract["selection"]["selected_candidate_next_authority"],
        )
        self.assertEqual(
            self.result["interpretation"]["selection_means"],
            "AUTHORIZE_ONLY_ONE_TINY_PROJECT_OWNED_VECTOR_2D_D1_SLICE",
        )

    def test_unknown_remains_selection_ineligible_without_becoming_factual_fail(self):
        self.assertTrue(self.result["unknown_is_selection_ineligible"])
        self.assertEqual(
            self.result["interpretation"]["unknown_means"],
            "NOT_ESTABLISHED_BY_REPOSITORY_OR_ACCESSIBLE_OFFICIAL_SOURCES_CHECKED",
        )
        self.assertTrue(
            any(
                status == "UNKNOWN"
                for candidate in self.result["candidates"].values()
                for status in candidate["gates"].values()
            )
        )

    def test_result_preserves_every_disabled_boundary(self):
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
