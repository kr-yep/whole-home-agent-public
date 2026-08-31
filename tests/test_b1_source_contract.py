"""Contract witnesses for the bounded B1 candidate-source seam."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from whole_home_agent import (
    ErrorCode,
    FixtureError,
    InMemoryCandidateSource,
    QueryRequest,
    QueryStatus,
    RunStatus,
    SourceDescriptor,
    SourceError,
    load_fixture,
    locate,
    run_fixture,
    run_source,
)
from whole_home_agent.sources import FixtureCandidateSource


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "examples" / "fixtures"
GOLDEN_HASH = "226d30a5b826720d607d0b9a29bf3dfb9f5429eeedbbd70ffd1ff23c21233c8f"


def fixture_source_parts():
    fixture = load_fixture(FIXTURE_ROOT / "b0_key_bag_sofa_v1.json")
    source = FixtureCandidateSource(fixture)
    descriptor = source.descriptor
    candidates = tuple(source)
    source.close()
    return fixture, descriptor, candidates


class CandidateSourceContractTests(unittest.TestCase):
    def test_fixture_wrapper_and_generic_source_preserve_b0_semantics(self):
        fixture, descriptor, candidates = fixture_source_parts()
        direct = run_fixture(fixture, replay_run_id="m1-direct")
        generic = run_source(
            InMemoryCandidateSource(descriptor, candidates),
            replay_run_id="m1-generic",
        )

        self.assertTrue(generic.complete)
        self.assertEqual(generic.status, RunStatus.COMPLETE)
        self.assertIsNotNone(generic.session)
        session = generic.session
        assert session is not None
        self.assertEqual(direct.semantic_output, session.semantic_output)
        self.assertEqual(direct.canonical_hash, GOLDEN_HASH)
        self.assertEqual(session.canonical_hash, GOLDEN_HASH)
        self.assertEqual(generic.receipt.semantic_output_hash, GOLDEN_HASH)
        self.assertEqual(generic.receipt.candidate_count, 2)
        self.assertEqual(generic.receipt.accepted_claim_count, 2)
        self.assertEqual(generic.receipt.duplicate_claim_count, 0)

        answer = locate(
            session,
            QueryRequest(
                subject_id="key",
                world_scope=session.world_scope,
                replay_run_id=session.replay_run_id,
                as_of_source_sequence=2,
            ),
        )
        self.assertEqual(answer.status, QueryStatus.FOUND)
        self.assertEqual(answer.location_id, "sofa")

    def test_source_failure_before_first_candidate_returns_no_session(self):
        _, descriptor, candidates = fixture_source_parts()
        source = InMemoryCandidateSource(descriptor, candidates, fail_after=0)
        outcome = run_source(source, replay_run_id="m1-fail-first")

        self.assertEqual(outcome.status, RunStatus.FAILED)
        self.assertIsNone(outcome.session)
        self.assertTrue(source.closed)
        self.assertEqual(outcome.receipt.candidate_count, 0)
        self.assertEqual(outcome.receipt.accepted_claim_count, 0)
        self.assertIsNone(outcome.receipt.semantic_output_hash)
        self.assertEqual(outcome.receipt.failure_code, ErrorCode.SOURCE_FAILURE.value)

    def test_source_failure_after_candidate_discards_partial_state(self):
        _, descriptor, candidates = fixture_source_parts()
        source = InMemoryCandidateSource(descriptor, candidates, fail_after=1)
        outcome = run_source(source, replay_run_id="m1-fail-partial")

        self.assertEqual(outcome.status, RunStatus.INCOMPLETE)
        self.assertIsNone(outcome.session)
        self.assertTrue(source.closed)
        self.assertEqual(outcome.receipt.candidate_count, 1)
        self.assertEqual(outcome.receipt.accepted_claim_count, 0)
        self.assertIsNone(outcome.receipt.projection_frontier)

    def test_missing_evidence_is_failed_before_commit(self):
        _, descriptor, candidates = fixture_source_parts()
        malformed = replace(candidates[0], evidence_refs=())
        outcome = run_source(
            InMemoryCandidateSource(descriptor, (malformed,)),
            replay_run_id="m1-invalid-candidate",
        )

        self.assertEqual(outcome.status, RunStatus.FAILED)
        self.assertIsNone(outcome.session)
        self.assertEqual(outcome.receipt.accepted_claim_count, 0)
        self.assertEqual(outcome.receipt.failure_code, ErrorCode.INVALID_SOURCE.value)

    def test_unpinned_descriptor_is_rejected_and_closed(self):
        _, descriptor, candidates = fixture_source_parts()
        invalid = replace(descriptor, content_hash="latest")
        source = InMemoryCandidateSource(invalid, candidates)

        with self.assertRaises(SourceError) as caught:
            run_source(source)
        self.assertEqual(caught.exception.error_code, ErrorCode.INVALID_SOURCE)
        self.assertTrue(source.closed)

    def test_b0_schema_v1_cannot_self_promote_to_estimated(self):
        document = json.loads(
            (FIXTURE_ROOT / "b0_key_bag_sofa_v1.json").read_text(encoding="utf-8")
        )
        document["claims"][0]["epistemic_status"] = "estimated"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "estimated.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(FixtureError) as caught:
                load_fixture(path)
        self.assertEqual(caught.exception.error_code, ErrorCode.INVALID_FIELD_VALUE)

    def test_descriptor_requires_repo_relative_provenance_manifest(self):
        _, descriptor, candidates = fixture_source_parts()
        cases: tuple[SourceDescriptor, ...] = (
            replace(descriptor, license_manifest_id="https://example.invalid/a.json"),
            replace(descriptor, license_manifest_id="C:\\private\\manifest.json"),
            replace(descriptor, world_scope="fixture:wrong@1"),
        )
        for invalid in cases:
            with self.subTest(invalid=invalid):
                source = InMemoryCandidateSource(invalid, candidates)
                with self.assertRaises(SourceError):
                    run_source(source)
                self.assertTrue(source.closed)


if __name__ == "__main__":
    unittest.main()
