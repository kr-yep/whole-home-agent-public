"""Frozen repository-only contract for M30 answer-subject identity."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m30-answer-subject-identity-decision-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m30-answer-subject-identity-decision-result-v1.toml"


class M30ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_three_candidates_and_eight_fatal_gates_are_frozen(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_REPOSITORY_EVIDENCE_SCORING")
        self.assertEqual(self.document["candidate_count"], 3)
        self.assertEqual(self.document["fatal_gate_count"], 8)
        self.assertEqual(
            [item["id"] for item in self.document["candidate"]],
            [
                "A_CANONICAL_ANSWER_TRACE_SUBJECT",
                "B_PUBLIC_DTO_ONLY_SUBJECT",
                "C_KEEP_CURRENT_TRACE_CONTEXT",
            ],
        )
        self.assertEqual(len(self.document["fatal_gate"]), 8)

    def test_every_evidence_file_is_hash_pinned(self):
        self.assertEqual(
            {item["path"]: item["sha256"] for item in self.document["evidence_file"]},
            {
                "src/whole_home_agent/model.py": "6cfb51c6cfc14ba86121d583c024c66a34719b7c6e0538580d5c0589f48fe824",
                "src/whole_home_agent/relations.py": "4f6d1ef0be4b2b7c8f63d1a4d2afd6c2b4318857df74645aef602a7fccc67954",
                "src/whole_home_agent/cli.py": "ccb10cf803a20148c8e97e2d8b41bb10b0b697357513b3829324cc51a1571030",
                "src/whole_home_agent/public_demo.py": "646fea88077aeaf83a2d4a39fe67a99fa043713f8983d80f0c30c790c975737c",
                "docs/minimal-viable-architecture.md": "7437ce780cdb9e6efa35e56d5a4f58506972f599347c2c5046f8008b1fc49255",
            },
        )
        result = ROOT / self.document["m29_result"]
        self.assertEqual(hashlib.sha256(result.read_bytes()).hexdigest(), self.document["m29_result_sha256"])

    def test_subject_is_query_scope_metadata_not_claim_truth(self):
        review = self.document["hostile_review"]
        self.assertTrue(review["subject_identity_is_query_scope_metadata"])
        self.assertFalse(review["subject_identity_is_epistemic_evidence"])
        self.assertFalse(review["adding_subject_changes_physical_truth"])
        self.assertFalse(review["relation_path_is_sufficient_for_unknown_or_conflict"])

    def test_selection_is_at_most_one_and_requires_separate_implementation(self):
        self.assertEqual(
            self.document["selection_rule"],
            "SELECT_AT_MOST_ONE_CANDIDATE_THAT_PASSES_EVERY_FATAL_GATE",
        )
        self.assertTrue(self.document["decision"]["selected_work_must_be_separately_frozen"])
        self.assertFalse(self.document["decision"]["m29_retry_allowed"])

    def test_every_runtime_and_change_boundary_is_closed(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


class M30ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_exactly_one_candidate_passes_every_gate(self):
        matrix = {item["id"]: item for item in self.result["candidate_result"]}
        self.assertEqual(self.result["eligible_candidate_count"], 1)
        self.assertTrue(matrix["A_CANONICAL_ANSWER_TRACE_SUBJECT"]["eligible"])
        self.assertEqual(matrix["A_CANONICAL_ANSWER_TRACE_SUBJECT"]["gate_results"], ["PASS"] * 8)
        self.assertFalse(matrix["B_PUBLIC_DTO_ONLY_SUBJECT"]["eligible"])
        self.assertFalse(matrix["C_KEEP_CURRENT_TRACE_CONTEXT"]["eligible"])
        self.assertEqual(self.result["selected_candidate"], "A_CANONICAL_ANSWER_TRACE_SUBJECT")

    def test_repository_facts_support_canonical_boundary(self):
        facts = {item["id"]: item["status"] for item in self.result["observed_fact"]}
        self.assertEqual(set(facts.values()), {"PASS"})
        model = (ROOT / "src/whole_home_agent/model.py").read_text(encoding="utf-8")
        relations = (ROOT / "src/whole_home_agent/relations.py").read_text(encoding="utf-8")
        self.assertIn("class QueryRequest:", model)
        self.assertIn("class AnswerTrace:", model)
        self.assertEqual(relations.count("AnswerTrace("), 1)

    def test_selected_scope_is_exact_and_does_not_retry_m29(self):
        scope = self.result["selected_scope"]
        self.assertEqual(scope["next_gate"], "M31_BOUNDED_ANSWER_TRACE_SUBJECT_IMPLEMENTATION")
        self.assertTrue(scope["add_required_subject_id_to_answer_trace"])
        self.assertTrue(scope["copy_only_from_query_request_in_trace_constructor"])
        self.assertTrue(scope["serialize_in_b0_cli_answer"])
        self.assertTrue(scope["serialize_in_b1_public_demo_answer"])
        self.assertFalse(scope["change_query_resolution_or_epistemic_semantics"])
        self.assertFalse(scope["m29_acceptance_retry"])

    def test_compatibility_risk_is_visible_not_rewritten_as_zero(self):
        compatibility = self.result["compatibility"]
        self.assertEqual(compatibility["serialized_change"], "ADDITIVE_FIELD")
        self.assertEqual(compatibility["manual_or_positional_answer_trace_constructor_risk"], "POSSIBLE")
        self.assertTrue(compatibility["strict_external_consumer_additive_field_tolerance_unknown"])

    def test_no_media_code_or_runtime_boundary_was_crossed(self):
        self.assertTrue(self.result["repository_evidence_only"])
        self.assertFalse(self.result["media_or_model_read"])
        self.assertFalse(self.result["code_schema_or_presentation_changed"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
