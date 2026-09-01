"""Frozen contract and bounded implementation checks for M31."""

from __future__ import annotations

import hashlib
import inspect
import tomllib
import unittest
from pathlib import Path

from whole_home_agent import QueryRequest, QueryStatus, load_fixture, locate, run_fixture
from whole_home_agent.cli import _answer_dict as b0_answer_dict
from whole_home_agent.model import AnswerTrace
from whole_home_agent.public_demo import _answer_dict as b1_answer_dict


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m31-answer-trace-subject-implementation-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m31-answer-trace-subject-implementation-result-v1.toml"


class M31ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_m30_selection_and_six_statuses_are_frozen(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_BOUNDED_IMPLEMENTATION")
        self.assertEqual(self.document["selected_candidate"], "A_CANONICAL_ANSWER_TRACE_SUBJECT")
        self.assertEqual(
            self.document["required_statuses"],
            ["FOUND", "UNKNOWN", "CONFLICT", "SCOPE_REQUIRED", "OUT_OF_SCOPE", "FRONTIER_MISMATCH"],
        )

    def test_prechange_files_and_m30_result_are_hash_pinned(self):
        self.assertEqual(
            {item["path"]: item["sha256"] for item in self.document["prechange_file"]},
            {
                "src/whole_home_agent/model.py": "6cfb51c6cfc14ba86121d583c024c66a34719b7c6e0538580d5c0589f48fe824",
                "src/whole_home_agent/relations.py": "4f6d1ef0be4b2b7c8f63d1a4d2afd6c2b4318857df74645aef602a7fccc67954",
                "src/whole_home_agent/cli.py": "ccb10cf803a20148c8e97e2d8b41bb10b0b697357513b3829324cc51a1571030",
                "src/whole_home_agent/public_demo.py": "646fea88077aeaf83a2d4a39fe67a99fa043713f8983d80f0c30c790c975737c",
            },
        )
        result = (ROOT / self.document["m30_result"]).read_bytes()
        self.assertEqual(hashlib.sha256(result).hexdigest(), self.document["m30_result_sha256"])

    def test_implementation_is_one_field_one_constructor_two_serializers(self):
        implementation = self.document["implementation"]
        self.assertTrue(implementation["answer_trace_add_required_subject_id"])
        self.assertEqual(implementation["answer_trace_construction_site_count"], 1)
        self.assertTrue(implementation["b0_cli_serializer_add_subject_id"])
        self.assertTrue(implementation["b1_public_demo_serializer_add_subject_id"])
        self.assertFalse(implementation["other_production_file_changes_allowed"])

    def test_no_legacy_empty_subject_and_compatibility_risk_is_visible(self):
        compatibility = self.document["compatibility"]
        self.assertEqual(compatibility["serialized_output_change"], "ADDITIVE_SUBJECT_ID_FIELD")
        self.assertTrue(compatibility["manual_or_positional_answer_trace_constructor_may_require_update"])
        self.assertFalse(compatibility["legacy_default_or_empty_subject_allowed"])

    def test_every_runtime_and_semantic_boundary_is_closed(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertFalse(self.document["decision"]["m29_retry_allowed"])


class M31ImplementationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_root = ROOT / "examples" / "fixtures"
        cls.session = run_fixture(load_fixture(fixture_root / "b0_key_bag_sofa_v1.json"), replay_run_id="m31-statuses")
        cls.conflict_session = run_fixture(load_fixture(fixture_root / "b0_multi_location_conflict_v1.json"), replay_run_id="m31-conflict")

    def locate(self, subject_id: str, **overrides):
        fields = {
            "subject_id": subject_id,
            "world_scope": self.session.world_scope,
            "replay_run_id": self.session.replay_run_id,
            "as_of_source_sequence": 2,
        }
        fields.update(overrides)
        return locate(self.session, QueryRequest(**fields))

    def test_subject_is_required_on_immutable_answer_trace(self):
        parameter = inspect.signature(AnswerTrace).parameters["subject_id"]
        self.assertIs(parameter.default, inspect.Parameter.empty)
        self.assertEqual(AnswerTrace.__dataclass_params__.frozen, True)

    def test_all_six_statuses_retain_exact_request_subject(self):
        cases = [
            (self.locate("key"), QueryStatus.FOUND, "key"),
            (self.locate("missing-object"), QueryStatus.UNKNOWN, "missing-object"),
            (self.locate("key", world_scope=""), QueryStatus.SCOPE_REQUIRED, "key"),
            (self.locate("key", world_scope="fixture:other@1"), QueryStatus.OUT_OF_SCOPE, "key"),
            (self.locate("key", as_of_source_sequence=3), QueryStatus.FRONTIER_MISMATCH, "key"),
            (
                locate(
                    self.conflict_session,
                    QueryRequest(
                        subject_id="key",
                        world_scope=self.conflict_session.world_scope,
                        replay_run_id=self.conflict_session.replay_run_id,
                        as_of_source_sequence=2,
                    ),
                ),
                QueryStatus.CONFLICT,
                "key",
            ),
        ]
        self.assertEqual({status for _, status, _ in cases}, set(QueryStatus))
        for answer, status, subject_id in cases:
            with self.subTest(status=status):
                self.assertEqual(answer.status, status)
                self.assertEqual(answer.subject_id, subject_id)
                if status is not QueryStatus.FOUND:
                    self.assertEqual(answer.relation_path, ())

    def test_b0_and_b1_serializers_add_only_subject_to_existing_keys(self):
        answer = self.locate("key")
        b0 = b0_answer_dict(answer)
        b1 = b1_answer_dict(answer)
        expected_b0_before = {
            "as_of_source_sequence", "candidate_location_ids", "epistemic_status",
            "location_id", "projection_frontier", "reason", "relation_path",
            "replay_run_id", "source_content_hash", "source_claim_ids", "status",
            "validator_version", "projector_version", "world_scope",
        }
        expected_b1_before = expected_b0_before - {
            "source_content_hash", "validator_version", "projector_version"
        }
        self.assertEqual(set(b0), expected_b0_before | {"subject_id"})
        self.assertEqual(set(b1), expected_b1_before | {"subject_id"})
        self.assertEqual(b0["subject_id"], "key")
        self.assertEqual(b1["subject_id"], "key")
        for key in expected_b1_before - {"relation_path"}:
            self.assertEqual(b0[key], b1[key])
        self.assertTrue(all("epistemic_status" in item for item in b1["relation_path"]))

    def test_session_semantics_and_golden_hash_are_unchanged(self):
        document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(self.session.canonical_hash, document["prechange_b0_golden_semantic_sha256"])
        self.assertEqual(
            tuple(claim.claim_id for claim in self.session.accepted_claims),
            ("claim-key-inside-bag", "claim-bag-at-sofa"),
        )
        self.assertEqual(self.session.projection.frontier, 2)


class M31ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_implementation_pass_is_distinct_from_contract_stop(self):
        self.assertTrue(self.result["implementation_checks_passed"])
        self.assertFalse(self.result["contract_no_media_assertion_passed"])
        self.assertEqual(self.result["decision"], self.contract["decision"]["normal_stop"])
        self.assertEqual(self.result["failure_codes"], ["VERIFICATION_MEDIA_BOUNDARY_CONTRADICTION"])

    def test_all_statuses_and_session_invariants_pass(self):
        self.assertTrue(all(self.result["status_coverage"].values()))
        invariants = self.result["invariants"]
        self.assertEqual(invariants["prechange_b0_golden_semantic_sha256"], invariants["postchange_b0_golden_semantic_sha256"])
        self.assertTrue(invariants["accepted_claim_ids_unchanged"])
        self.assertTrue(invariants["projection_frontier_unchanged"])
        self.assertFalse(invariants["query_resolution_or_epistemic_semantics_changed"])

    def test_boundary_violation_is_exact_and_not_private_or_model_use(self):
        boundary = self.result["verification_boundary"]
        self.assertTrue(boundary["committed_d0_synthetic_media_read"])
        self.assertTrue(boundary["full_suite_contains_committed_d0_synthetic_prerecorded_regressions"])
        self.assertFalse(boundary["third_party_or_private_media_read"])
        self.assertFalse(boundary["model_loaded"])
        self.assertFalse(boundary["m29_checker_executed"])
        self.assertFalse(boundary["post_observation_contract_reinterpretation_allowed"])

    def test_stop_does_not_rewrite_implementation_as_failure(self):
        limits = self.result["claim_limits"]
        self.assertFalse(limits["stop_establishes_implementation_failure"])
        self.assertTrue(limits["stop_establishes_no_media_contract_violation"])
        self.assertFalse(limits["implementation_establishes_product_or_cv_gain"])
        self.assertFalse(limits["m29_result_retried_or_rewritten"])

    def test_next_gate_is_no_media_repository_decision_only(self):
        next_gate = self.result["next_gate"]
        self.assertEqual(next_gate["proposal"], "M32_VERIFICATION_MEDIA_BOUNDARY_CLARIFICATION")
        self.assertFalse(next_gate["code_schema_or_presentation_change_allowed"])
        self.assertFalse(next_gate["media_model_demo_or_checker_execution_allowed"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
