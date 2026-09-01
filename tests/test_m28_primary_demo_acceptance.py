"""Frozen pre-execution contract for M28 primary demo acceptance."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from tools.check_primary_demo import (
    _assert_judge_card,
    _assert_presentation,
    _assert_result,
    _semantic_document,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m28-primary-demo-acceptance-v1.toml"
M27 = ROOT / "configs" / "evaluation" / "m27-demo-evaluation-contract-result-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m28-primary-demo-acceptance-result-v1.toml"


class M28ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.m27 = tomllib.loads(M27.read_text(encoding="utf-8"))

    def test_contract_is_frozen_before_demo_and_inherits_m27_selection(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_COMMITTED_DEMO_EXECUTION")
        self.assertEqual(self.m27["decision"], "SELECT_EXISTING_SYNTHETIC_E2E_PRIMARY_DEMO")
        self.assertEqual(self.document["source_use_class"], "D0_SYNTHETIC")
        self.assertEqual(self.document["source_frame_count"], 80)
        self.assertEqual(self.document["target_seconds"], 90)

    def test_two_interfaces_run_offline_and_only_run_id_is_excluded(self):
        execution = self.document["execution"]
        self.assertTrue(execution["committed_project_owned_media_allowed"])
        self.assertFalse(execution["third_party_or_private_media_allowed"])
        self.assertTrue(execution["network_denied_during_both_runs"])
        self.assertEqual(self.document["acceptance_runs"], 2)
        self.assertEqual(execution["semantic_comparison_excludes_only"], ["replay_run_id"])
        self.assertFalse(execution["model_or_runtime_configuration_change_allowed"])

    def test_answer_and_exact_two_claims_are_precommitted(self):
        answer = self.document["expected_answer"]
        self.assertEqual((answer["status"], answer["location_id"], answer["epistemic_status"]), ("FOUND", "sofa", "estimated"))
        self.assertEqual(answer["relation_path_length"], 2)
        claims = self.document["expected_claim"]
        self.assertEqual(
            [(item["predicate"], item["subject_id"], item["object_id"], item["confirmation_frame"]) for item in claims],
            [("inside", "key", "bag", 37), ("at_zone", "bag", "sofa", 68)],
        )

    def test_presentation_prevents_fixture_metrics_from_leading(self):
        presentation = self.document["presentation"]
        self.assertFalse(presentation["perfect_fixture_metrics_in_primary_visible_area_allowed"])
        self.assertTrue(presentation["fixture_metrics_must_be_in_collapsed_expander"])
        self.assertFalse(presentation["upload_camera_chat_arbitrary_path_widgets_allowed"])
        self.assertFalse(presentation["credentials_actions_or_generic_tools_allowed"])

    def test_next_authority_and_every_non_demo_boundary_are_closed(self):
        self.assertEqual(self.document["decision"]["pass_authorizes_only"], "M29_TEAMMATE_CLEAN_INSTALL_AND_DEMO_DRILL")
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


class M28AcceptanceHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_semantic_document_ignores_only_run_id_and_cost_timing(self):
        base = {
            "source": {"source_id": "x"},
            "governance": {"operate": "DISABLED"},
            "answer": {"replay_run_id": "a", "status": "FOUND"},
            "claims": [],
            "source_diagnostics": {},
            "warnings": [],
            "perception_evaluation": {"quality": {"ap50": 1.0}, "cost": {"p95": 1}},
            "relation_evaluation": {"quality": {"f1": 1.0}},
        }
        changed = {**base, "answer": {"replay_run_id": "b", "status": "FOUND"}, "perception_evaluation": {"quality": {"ap50": 1.0}, "cost": {"p95": 999}}}
        self.assertEqual(_semantic_document(base), _semantic_document(changed))

    def test_invalid_result_accumulates_typed_failures(self):
        failures: list[str] = []
        _assert_result({}, self.document, failures)
        self.assertIn("SOURCE_IDENTITY", failures)
        self.assertIn("GOVERNANCE_BOUNDARY", failures)
        self.assertIn("SCOPED_ANSWER", failures)
        self.assertIn("EXACT_EVIDENCE_TRACE", failures)

    def test_hardened_static_presentation_and_judge_card_pass(self):
        presentation_failures: list[str] = []
        _assert_presentation(presentation_failures)
        self.assertEqual(presentation_failures, [])
        card_failures: list[str] = []
        _assert_judge_card(card_failures)
        self.assertEqual(card_failures, [])


class M28ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_normal_stop_records_exact_three_frozen_failures(self):
        self.assertEqual(self.result["decision"], self.contract["decision"]["normal_stop"])
        self.assertEqual(
            self.result["failure_codes"],
            ["EXACT_EVIDENCE_TRACE", "METRICS_NOT_COLLAPSED_OR_LABELED", "PERFECT_METRICS_PRIMARY_VISIBLE"],
        )
        self.assertEqual(self.result["network_attempt_count"], 0)
        self.assertTrue(self.result["semantic_outputs_equal"])

    def test_observed_trace_keeps_event_evidence_and_confirmation_distinct(self):
        rows = self.result["observed_claim"]
        self.assertEqual(
            [(item["source_event_frame"], item["observed_evidence_start_frame"], item["confirmation_frame"]) for item in rows],
            [(35, 33, 37), (65, 66, 68)],
        )

    def test_only_two_presentation_gaps_are_hardened(self):
        dispositions = {item["code"]: item for item in self.result["gap_disposition"]}
        self.assertEqual(dispositions["PERFECT_METRICS_PRIMARY_VISIBLE"]["status"], "HARDENED_WITHOUT_SEMANTIC_CHANGE")
        self.assertEqual(dispositions["METRICS_NOT_COLLAPSED_OR_LABELED"]["status"], "HARDENED_WITHOUT_SEMANTIC_CHANGE")
        self.assertEqual(dispositions["EXACT_EVIDENCE_TRACE"]["status"], "UNRESOLVED_FROZEN_CONTRACT_FACT_MISMATCH")
        self.assertFalse(self.result["static_acceptance"]["second_media_acceptance_attempt_run"])

    def test_stop_does_not_invalidate_m27_or_claim_runtime_failure(self):
        limits = self.result["claim_limits"]
        self.assertFalse(limits["stop_invalidates_m27_primary_demo_selection"])
        self.assertFalse(limits["stop_establishes_demo_runtime_failure"])
        self.assertTrue(limits["stop_establishes_precommitted_trace_contract_mismatch"])
        self.assertFalse(limits["presentation_hardening_changes_claim_or_relation_semantics"])

    def test_next_gate_allows_one_semantic_contract_retry_only(self):
        next_gate = self.result["next_gate"]
        self.assertEqual(next_gate["proposal"], "M29_TRACE_WINDOW_CONTRACT_CORRECTION_AND_SINGLE_ACCEPTANCE_RETRY")
        self.assertEqual(next_gate["acceptance_retry_count"], 1)
        self.assertFalse(next_gate["presentation_or_semantic_change_allowed"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
