"""Black-box conformance contract for the frozen B0 semantic replay.

These tests intentionally import only the package-root API.  The fixtures are
synthetic D0 reports: accepting one proves validator behavior inside the named
fixture/run scope, never that a physical household event occurred.
"""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

from whole_home_agent import (
    ClaimConflictError,
    CycleError,
    ErrorCode,
    FixtureError,
    QueryRequest,
    QueryStatus,
    load_fixture,
    locate,
    run_fixture,
)


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "examples" / "fixtures"


class B0ReplayConformanceTests(unittest.TestCase):
    """MVA-001/003/004/005/006/008 deterministic B0 witnesses."""

    def run_named_fixture(self, name: str, *, replay_run_id: str | None = None):
        fixture = load_fixture(FIXTURE_ROOT / name)
        if replay_run_id is None:
            return run_fixture(fixture)
        return run_fixture(fixture, replay_run_id=replay_run_id)

    def locate_at(self, session, subject_id: str, source_sequence: int):
        return locate(
            session,
            QueryRequest(
                subject_id=subject_id,
                world_scope=session.world_scope,
                replay_run_id=session.replay_run_id,
                as_of_source_sequence=source_sequence,
            ),
        )

    def assert_fixture_rejected(self, name: str, error_type=FixtureError):
        with self.assertRaises(error_type):
            fixture = load_fixture(FIXTURE_ROOT / name)
            run_fixture(fixture)

    def test_frozen_fixture_bytes_match_the_versioned_manifest(self):
        manifest = json.loads(
            (FIXTURE_ROOT / "fixture_manifest_v1.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["manifest_version"], 1)
        self.assertEqual(manifest["use_class"], "D0_SYNTHETIC")
        for item in manifest["fixtures"]:
            with self.subTest(path=item["path"]):
                payload = (FIXTURE_ROOT / item["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), item["sha256"])

    def test_key_inside_bag_then_bag_at_sofa_is_scoped_and_traceable(self):
        session = self.run_named_fixture("b0_key_bag_sofa_v1.json")

        self.assertEqual(session.world_scope, "fixture:b0-key-bag-sofa@1")
        answer = self.locate_at(session, "key", 2)

        self.assertEqual(answer.status, QueryStatus.FOUND)
        self.assertEqual(answer.location_id, "sofa")
        self.assertEqual(answer.epistemic_status, "estimated")
        self.assertEqual(len(answer.relation_path), 2)
        self.assertEqual(
            tuple(step.source_offset for step in answer.relation_path), (0, 1)
        )
        self.assertEqual(
            tuple(answer.source_claim_ids),
            ("claim-key-inside-bag", "claim-bag-at-sofa"),
        )
        self.assertEqual(answer.world_scope, session.world_scope)
        self.assertEqual(answer.replay_run_id, session.replay_run_id)
        self.assertEqual(answer.as_of_source_sequence, 2)
        self.assertEqual(answer.projection_frontier, session.projection_frontier)
        self.assertEqual(answer.source_content_hash, session.source_content_hash)
        self.assertEqual(answer.validator_version, "b0-claim-validator/1")
        self.assertEqual(answer.projector_version, "b0-relation-projector/1")

    def test_direct_bag_location_preserves_reported_epistemic_status(self):
        session = self.run_named_fixture("b0_key_bag_sofa_v1.json")
        answer = self.locate_at(session, "bag", 2)

        self.assertEqual(answer.status, QueryStatus.FOUND)
        self.assertEqual(answer.location_id, "sofa")
        self.assertEqual(answer.epistemic_status, "reported")
        self.assertEqual(tuple(answer.source_claim_ids), ("claim-bag-at-sofa",))
        self.assertEqual(len(answer.relation_path), 1)

    def test_take_out_ends_the_location_inherited_through_the_bag(self):
        session = self.run_named_fixture("b0_take_out_v1.json")

        before_take_out = self.locate_at(session, "key", 2)
        after_take_out = self.locate_at(session, "key", 3)

        self.assertEqual(before_take_out.status, QueryStatus.FOUND)
        self.assertEqual(before_take_out.location_id, "sofa")
        self.assertEqual(after_take_out.status, QueryStatus.UNKNOWN)
        self.assertIsNone(after_take_out.location_id)

    def test_duplicate_delivery_is_idempotent(self):
        session = self.run_named_fixture("b0_duplicate_v1.json")

        self.assertEqual(
            tuple(claim.claim_id for claim in session.accepted_claims),
            ("claim-key-inside-bag", "claim-bag-at-sofa"),
        )
        answer = self.locate_at(session, "key", 2)
        self.assertEqual(answer.status, QueryStatus.FOUND)
        self.assertEqual(answer.location_id, "sofa")

    def test_same_identity_with_different_payload_is_a_conflict(self):
        self.assert_fixture_rejected(
            "b0_identity_conflict_v1.json", ClaimConflictError
        )

    def test_containment_cycle_is_rejected(self):
        self.assert_fixture_rejected("b0_containment_cycle_v1.json", CycleError)

    def test_missing_query_scope_fails_closed(self):
        session = self.run_named_fixture("b0_key_bag_sofa_v1.json")
        valid = {
            "subject_id": "key",
            "world_scope": session.world_scope,
            "replay_run_id": session.replay_run_id,
            "as_of_source_sequence": 2,
        }
        missing_cases = {
            "world_scope": "",
            "replay_run_id": "",
            "as_of_source_sequence": None,
        }

        for field, missing_value in missing_cases.items():
            with self.subTest(field=field):
                fields = dict(valid)
                fields[field] = missing_value
                answer = locate(session, QueryRequest(**fields))
                self.assertEqual(answer.status, QueryStatus.SCOPE_REQUIRED)
                self.assertIsNone(answer.location_id)
                self.assertTrue(answer.reason)

    def test_unknown_subject_abstains_inside_the_requested_scope(self):
        session = self.run_named_fixture("b0_key_bag_sofa_v1.json")
        answer = self.locate_at(session, "missing-object", 2)

        self.assertEqual(answer.status, QueryStatus.UNKNOWN)
        self.assertIsNone(answer.location_id)
        self.assertEqual(tuple(answer.source_claim_ids), ())
        self.assertEqual(answer.world_scope, session.world_scope)
        self.assertEqual(answer.replay_run_id, session.replay_run_id)
        self.assertEqual(answer.as_of_source_sequence, 2)

    def test_mismatched_scope_and_future_frontier_fail_closed(self):
        session = self.run_named_fixture("b0_key_bag_sofa_v1.json")
        cases = (
            (
                QueryRequest(
                    subject_id="key",
                    world_scope="fixture:another-world@1",
                    replay_run_id=session.replay_run_id,
                    as_of_source_sequence=2,
                ),
                QueryStatus.OUT_OF_SCOPE,
            ),
            (
                QueryRequest(
                    subject_id="key",
                    world_scope=session.world_scope,
                    replay_run_id="another-run",
                    as_of_source_sequence=2,
                ),
                QueryStatus.OUT_OF_SCOPE,
            ),
            (
                QueryRequest(
                    subject_id="key",
                    world_scope=session.world_scope,
                    replay_run_id=session.replay_run_id,
                    as_of_source_sequence=3,
                ),
                QueryStatus.FRONTIER_MISMATCH,
            ),
        )

        for request, expected in cases:
            with self.subTest(expected=expected):
                answer = locate(session, request)
                self.assertEqual(answer.status, expected)
                self.assertIsNone(answer.location_id)

    def test_multiple_active_locations_return_conflict_without_guessing(self):
        session = self.run_named_fixture("b0_multi_location_conflict_v1.json")
        answer = self.locate_at(session, "key", 2)

        self.assertEqual(answer.status, QueryStatus.CONFLICT)
        self.assertIsNone(answer.location_id)
        self.assertEqual(answer.candidate_location_ids, ("sofa", "table"))

    def test_out_of_order_new_claim_is_rejected(self):
        fixture = load_fixture(FIXTURE_ROOT / "b0_out_of_order_v1.json")
        with self.assertRaises(FixtureError) as caught:
            run_fixture(fixture)
        self.assertEqual(caught.exception.error_code, ErrorCode.SOURCE_ORDER)

    def test_malformed_and_duplicate_key_json_are_rejected(self):
        for name in ("b0_malformed_v1.json", "b0_duplicate_json_key_v1.json"):
            with self.subTest(name=name):
                with self.assertRaises(FixtureError) as caught:
                    load_fixture(FIXTURE_ROOT / name)
                self.assertEqual(caught.exception.error_code, ErrorCode.INVALID_JSON)

    def test_url_fixture_path_is_rejected_before_io(self):
        with self.assertRaises(FixtureError) as caught:
            load_fixture("https://example.invalid/fixture.json")
        self.assertEqual(caught.exception.error_code, ErrorCode.INVALID_FIXTURE_PATH)

    def test_action_shaped_fixture_is_rejected(self):
        self.assert_fixture_rejected("b0_action_shaped_v1.json")

    def test_unknown_top_level_field_is_rejected(self):
        self.assert_fixture_rejected("b0_unknown_field_v1.json")

    def test_unknown_relation_predicate_is_rejected(self):
        self.assert_fixture_rejected("b0_unknown_predicate_v1.json")

    def test_automatic_run_ids_are_unique_without_changing_semantic_output(self):
        first = self.run_named_fixture("b0_key_bag_sofa_v1.json")
        second = self.run_named_fixture("b0_key_bag_sofa_v1.json")

        self.assertNotEqual(first.replay_run_id, second.replay_run_id)
        self.assertEqual(first.semantic_output, second.semantic_output)
        self.assertEqual(first.canonical_hash, second.canonical_hash)
        self.assertRegex(first.canonical_hash, re.compile(r"^[0-9a-f]{64}$"))
        self.assertEqual(
            tuple(claim.claim_id for claim in first.accepted_claims),
            tuple(claim.claim_id for claim in second.accepted_claims),
        )

    def test_explicit_run_id_is_reproducible(self):
        first = self.run_named_fixture(
            "b0_key_bag_sofa_v1.json", replay_run_id="contract-run-001"
        )
        second = self.run_named_fixture(
            "b0_key_bag_sofa_v1.json", replay_run_id="contract-run-001"
        )

        self.assertEqual(first.replay_run_id, "contract-run-001")
        self.assertEqual(second.replay_run_id, "contract-run-001")
        self.assertEqual(first.semantic_output, second.semantic_output)
        self.assertEqual(first.canonical_hash, second.canonical_hash)


if __name__ == "__main__":
    unittest.main()
