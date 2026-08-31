"""Single composition boundary for deterministic offline replay."""

from __future__ import annotations

import hashlib
import time
import uuid

from .errors import B0Error, ErrorCode, FixtureError, SourceError
from .ledger import build_ledger_from_candidates
from .model import (
    PROJECTOR_VERSION,
    VALIDATOR_VERSION,
    ClaimCandidate,
    ProducerRef,
    QueryRequest,
    ReplayFixture,
    ReplayRunResult,
    ReplaySession,
    RunReceipt,
    RunStatus,
    SourceDescriptor,
    StageTiming,
)
from .relations import locate, reduce_relations
from .serialization import canonical_json, semantic_document
from .sources import (
    ClaimCandidateSource,
    FixtureCandidateSource,
    validate_candidate,
    validate_descriptor,
)


def _validate_run_id(run_id: str) -> str:
    if (
        type(run_id) is not str
        or not run_id
        or run_id != run_id.strip()
        or len(run_id) > 256
        or any(ord(character) < 32 or ord(character) == 127 for character in run_id)
    ):
        raise FixtureError(
            "replay_run_id must be a non-empty, trimmed identifier",
            error_code=ErrorCode.INVALID_FIELD_VALUE,
            details={"field": "replay_run_id"},
        )
    return run_id


def _unique_producers(candidates: list[ClaimCandidate]) -> tuple[ProducerRef, ...]:
    values = {
        candidate.producer_ref.identity_payload(): candidate.producer_ref
        for candidate in candidates
        if candidate.producer_ref is not None
    }
    return tuple(values[key] for key in sorted(values))


def _receipt(
    *,
    descriptor: SourceDescriptor,
    run_id: str,
    status: RunStatus,
    candidates: list[ClaimCandidate],
    accepted_count: int,
    rejected_count: int,
    timings: list[StageTiming],
    error: B0Error | None = None,
    projection_frontier: int | None = None,
    semantic_output_hash: str | None = None,
) -> RunReceipt:
    return RunReceipt(
        replay_run_id=run_id,
        status=status,
        source_id=descriptor.source_id,
        source_revision=descriptor.source_revision,
        source_content_hash=descriptor.content_hash,
        candidate_count=len(candidates),
        accepted_claim_count=accepted_count,
        rejected_claim_count=rejected_count,
        duplicate_claim_count=max(0, len(candidates) - accepted_count),
        validator_version=VALIDATOR_VERSION,
        projector_version=PROJECTOR_VERSION,
        producer_refs=_unique_producers(candidates),
        stage_timings=tuple(timings),
        projection_frontier=projection_frontier,
        semantic_output_hash=semantic_output_hash,
        failure_code=error.error_code.value if error is not None else None,
        failure_message=str(error) if error is not None else None,
    )


def _execute_source(
    source: ClaimCandidateSource,
    *,
    replay_run_id: str | None,
    return_failure: bool,
) -> ReplayRunResult:
    if not isinstance(source, ClaimCandidateSource):
        raise SourceError(
            "run_source requires a ClaimCandidateSource",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    descriptor = source.descriptor
    try:
        validate_descriptor(descriptor)
    except B0Error:
        source.close()
        raise
    run_id = _validate_run_id(
        replay_run_id
        if replay_run_id is not None
        else (
            f"replay:{descriptor.source_id}@{descriptor.source_revision}:"
            f"{uuid.uuid4().hex}"
        )
    )
    started = time.perf_counter()
    source_started = time.perf_counter()
    candidates: list[ClaimCandidate] = []
    timings: list[StageTiming] = []
    error: B0Error | None = None
    session: ReplaySession | None = None

    try:
        for candidate in source:
            validate_candidate(candidate, descriptor)
            candidates.append(candidate)
        timings.append(
            StageTiming(
                "candidate_source", (time.perf_counter() - source_started) * 1000
            )
        )

        commit_started = time.perf_counter()
        ledger = build_ledger_from_candidates(candidates)
        timings.append(
            StageTiming("claim_commit", (time.perf_counter() - commit_started) * 1000)
        )

        projection_started = time.perf_counter()
        projection = reduce_relations(ledger.accepted_claims)
        timings.append(
            StageTiming(
                "projection", (time.perf_counter() - projection_started) * 1000
            )
        )
        semantic_output = canonical_json(
            semantic_document(descriptor, ledger, projection)
        )
        canonical_hash = hashlib.sha256(semantic_output.encode("utf-8")).hexdigest()
        session = ReplaySession(
            fixture_id=descriptor.source_id,
            fixture_revision=descriptor.source_revision,
            world_scope=descriptor.world_scope,
            replay_run_id=run_id,
            projection_frontier=projection.frontier,
            source_content_hash=descriptor.content_hash,
            validator_version=VALIDATOR_VERSION,
            projector_version=PROJECTOR_VERSION,
            ledger=ledger,
            projection=projection,
            semantic_output=semantic_output,
            canonical_hash=canonical_hash,
            source_descriptor=descriptor,
        )
    except B0Error as caught:
        error = caught
    finally:
        try:
            source.close()
        except B0Error as close_error:
            if error is None:
                error = close_error

    timings.append(StageTiming("total", (time.perf_counter() - started) * 1000))
    if error is not None:
        if not return_failure:
            raise error
        status = (
            RunStatus.INCOMPLETE
            if candidates and error.error_code is ErrorCode.SOURCE_FAILURE
            else RunStatus.FAILED
        )
        return ReplayRunResult(
            status=status,
            receipt=_receipt(
                descriptor=descriptor,
                run_id=run_id,
                status=status,
                candidates=candidates,
                accepted_count=0,
                rejected_count=1,
                timings=timings,
                error=error,
            ),
            session=None,
        )

    assert session is not None
    return ReplayRunResult(
        status=RunStatus.COMPLETE,
        receipt=_receipt(
            descriptor=descriptor,
            run_id=run_id,
            status=RunStatus.COMPLETE,
            candidates=candidates,
            accepted_count=len(session.accepted_claims),
            rejected_count=len(session.rejections),
            timings=timings,
            projection_frontier=session.projection_frontier,
            semantic_output_hash=session.canonical_hash,
        ),
        session=session,
    )


def run_source(
    source: ClaimCandidateSource, *, replay_run_id: str | None = None
) -> ReplayRunResult:
    """Replay one bounded source; failures return a receipt and no session."""

    return _execute_source(
        source, replay_run_id=replay_run_id, return_failure=True
    )


def run_fixture(
    fixture: ReplayFixture, *, replay_run_id: str | None = None
) -> ReplaySession:
    """Backward-compatible B0 fixture replay using the generic source seam."""

    if not isinstance(fixture, ReplayFixture):
        raise FixtureError(
            "run_fixture requires a ReplayFixture returned by load_fixture",
            error_code=ErrorCode.INVALID_SCHEMA,
        )
    result = _execute_source(
        FixtureCandidateSource(fixture),
        replay_run_id=replay_run_id,
        return_failure=False,
    )
    assert result.session is not None
    return result.session


__all__ = ["locate", "run_fixture", "run_source", "QueryRequest"]
