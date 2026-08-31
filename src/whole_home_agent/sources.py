"""Narrow candidate-source port and deterministic offline implementations."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, replace
from typing import Iterator, Protocol, runtime_checkable

from .errors import ErrorCode, SourceError
from .model import (
    ClaimCandidate,
    EvidenceRef,
    ProducerRef,
    ReplayFixture,
    SourceDescriptor,
    SourceKind,
    SourcePosition,
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_sha256(value: str) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_descriptor(descriptor: SourceDescriptor) -> None:
    """Fail closed on mutable, ambiguous, or operational source descriptors."""

    if not isinstance(descriptor, SourceDescriptor):
        raise SourceError(
            "candidate source descriptor has the wrong type",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    identifiers = {
        "source_id": descriptor.source_id,
        "source_revision": descriptor.source_revision,
        "license_manifest_id": descriptor.license_manifest_id,
        "world_scope": descriptor.world_scope,
    }
    invalid = [
        name
        for name, value in identifiers.items()
        if type(value) is not str
        or not value
        or value != value.strip()
        or len(value) > 512
    ]
    expected_scope_prefix = (
        "fixture"
        if descriptor.source_kind is SourceKind.SEMANTIC_FIXTURE
        else "source"
    )
    expected_scope = (
        f"{expected_scope_prefix}:{descriptor.source_id}@{descriptor.source_revision}"
    )
    invalid_manifest = (
        "://" in descriptor.license_manifest_id
        or "\\" in descriptor.license_manifest_id
        or descriptor.license_manifest_id.startswith("/")
        or ".." in descriptor.license_manifest_id.split("/")
        or (
            len(descriptor.license_manifest_id) >= 2
            and descriptor.license_manifest_id[1] == ":"
        )
    )
    if (
        invalid
        or not isinstance(descriptor.source_kind, SourceKind)
        or not _is_sha256(descriptor.content_hash)
        or descriptor.world_scope != expected_scope
        or invalid_manifest
    ):
        raise SourceError(
            "candidate source descriptor is incomplete or unpinned",
            error_code=ErrorCode.INVALID_SOURCE,
            details={"invalid_fields": invalid},
        )


def validate_candidate(candidate: ClaimCandidate, descriptor: SourceDescriptor) -> None:
    """Validate canonical values and bounded evidence before claim admission."""

    if not isinstance(candidate, ClaimCandidate):
        raise SourceError(
            "candidate source yielded a non-ClaimCandidate value",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    position = candidate.source_position
    producer = candidate.producer_ref
    identifier_values = (
        candidate.claim_id,
        candidate.subject_id,
        candidate.object_id,
    )
    if (
        any(
            type(value) is not str
            or not value
            or value != value.strip()
            or len(value) > 256
            for value in identifier_values
        )
        or type(candidate.source_sequence) is not int
        or candidate.source_sequence < 0
        or type(candidate.source_offset) is not int
        or candidate.source_offset < 0
        or not hasattr(candidate.operation, "value")
        or not hasattr(candidate.predicate, "value")
        or not hasattr(candidate.epistemic_status, "value")
    ):
        raise SourceError(
            "candidate has invalid canonical claim fields",
            error_code=ErrorCode.INVALID_SOURCE,
            details={"claim_id": getattr(candidate, "claim_id", None)},
        )
    if position is None or producer is None or not candidate.evidence_refs:
        raise SourceError(
            "candidate is missing source position, producer, or evidence metadata",
            error_code=ErrorCode.INVALID_SOURCE,
            details={"claim_id": candidate.claim_id},
        )
    if (
        position.source_sequence != candidate.source_sequence
        or position.source_offset != candidate.source_offset
        or position.timestamp_basis is not descriptor.timestamp_basis
    ):
        raise SourceError(
            "candidate position disagrees with its canonical source coordinates",
            error_code=ErrorCode.INVALID_SOURCE,
            details={"claim_id": candidate.claim_id},
        )
    if (
        not _is_sha256(producer.artifact_hash)
        or not _is_sha256(producer.config_hash)
        or any(
            type(value) is not str or not value or value != value.strip()
            for value in (producer.component, producer.version)
        )
    ):
        raise SourceError(
            "candidate producer is not pinned by artifact and config hashes",
            error_code=ErrorCode.INVALID_SOURCE,
            details={"claim_id": candidate.claim_id},
        )
    if descriptor.timestamp_basis.value == "media_pts":
        if (
            position.frame_index is None
            or position.pts is None
            or position.time_base_numerator is None
            or position.time_base_denominator is None
            or position.time_base_denominator <= 0
        ):
            raise SourceError(
                "media candidate position requires frame, PTS, and time base",
                error_code=ErrorCode.INVALID_SOURCE,
                details={"claim_id": candidate.claim_id},
            )
    for evidence in candidate.evidence_refs:
        _validate_evidence(evidence, candidate, descriptor)


def _validate_evidence(
    evidence: EvidenceRef,
    candidate: ClaimCandidate,
    descriptor: SourceDescriptor,
) -> None:
    if not isinstance(evidence, EvidenceRef):
        raise SourceError(
            "candidate evidence has the wrong type",
            error_code=ErrorCode.INVALID_SOURCE,
            details={"claim_id": candidate.claim_id},
        )
    if (
        type(evidence.evidence_id) is not str
        or not evidence.evidence_id
        or evidence.evidence_id != evidence.evidence_id.strip()
        or "://" in evidence.evidence_id
        or "\\" in evidence.evidence_id
        or "/" in evidence.evidence_id
        or type(evidence.quality) is not str
        or evidence.quality
        not in {
            "unknown",
            "synthetic_report",
            "model_report",
            "perception_report",
            "manual_annotation",
        }
        or (
            evidence.confidence is not None
            and (
                type(evidence.confidence) is not float
                or not math.isfinite(evidence.confidence)
                or evidence.confidence < 0.0
                or evidence.confidence > 1.0
            )
        )
    ):
        raise SourceError(
            "candidate evidence contains invalid scalar metadata",
            error_code=ErrorCode.INVALID_SOURCE,
            details={"claim_id": candidate.claim_id},
        )
    if evidence.source_id != descriptor.source_id:
        raise SourceError(
            "evidence source identity does not match the replay source",
            error_code=ErrorCode.INVALID_SOURCE,
            details={
                "claim_id": candidate.claim_id,
                "evidence_id": evidence.evidence_id,
            },
        )
    if (
        evidence.start.timestamp_basis is not descriptor.timestamp_basis
        or evidence.end.timestamp_basis is not descriptor.timestamp_basis
        or evidence.start.source_sequence > evidence.end.source_sequence
        or evidence.start.source_offset > evidence.end.source_offset
    ):
        raise SourceError(
            "evidence range is reversed or uses a mismatched time basis",
            error_code=ErrorCode.INVALID_SOURCE,
            details={"evidence_id": evidence.evidence_id},
        )


@runtime_checkable
class ClaimCandidateSource(Protocol):
    """Sequential source of canonical candidates with explicit close semantics."""

    @property
    def descriptor(self) -> SourceDescriptor: ...

    def __iter__(self) -> Iterator[ClaimCandidate]: ...

    def close(self) -> None: ...


class FixtureCandidateSource:
    """Translate a frozen B0 fixture into the generic source contract."""

    def __init__(self, fixture: ReplayFixture) -> None:
        self._fixture = fixture
        self._closed = False
        self._descriptor = SourceDescriptor(
            source_id=fixture.fixture_id,
            source_revision=fixture.fixture_revision,
            source_kind=SourceKind.SEMANTIC_FIXTURE,
            use_class=fixture.use_class,
            timestamp_basis=fixture.timestamp_basis,
            content_hash=fixture.content_hash,
            license_manifest_id="examples/fixtures/fixture_manifest_v1.json",
            world_scope=fixture.world_scope,
        )
        self._producer = ProducerRef(
            component="b0-fixture-translator",
            version="1",
            artifact_hash=fixture.content_hash,
            config_hash=_sha256_text("b0-fixture-schema-v1"),
        )

    @property
    def descriptor(self) -> SourceDescriptor:
        return self._descriptor

    def __iter__(self) -> Iterator[ClaimCandidate]:
        if self._closed:
            raise SourceError(
                "candidate source is already closed",
                error_code=ErrorCode.SOURCE_FAILURE,
            )
        for candidate in self._fixture.claims:
            position = SourcePosition(
                source_sequence=candidate.source_sequence,
                source_offset=candidate.source_offset,
                timestamp_basis=self._fixture.timestamp_basis,
            )
            yield replace(
                candidate,
                source_position=position,
                producer_ref=self._producer,
                evidence_refs=(
                    EvidenceRef(
                        evidence_id=f"fixture-record:{candidate.source_offset}",
                        source_id=self._fixture.fixture_id,
                        start=position,
                        end=position,
                        quality="synthetic_report",
                    ),
                ),
            )

    def close(self) -> None:
        self._closed = True


@dataclass(slots=True)
class InMemoryCandidateSource:
    """Synthetic fake adapter used by contract and failure-injection tests."""

    descriptor: SourceDescriptor
    candidates: tuple[ClaimCandidate, ...]
    fail_after: int | None = None
    closed: bool = False

    def __iter__(self) -> Iterator[ClaimCandidate]:
        if self.closed:
            raise SourceError("candidate source is already closed")
        for index, candidate in enumerate(self.candidates):
            if self.fail_after is not None and index >= self.fail_after:
                raise SourceError(
                    "synthetic source failure",
                    details={"processed_candidates": index},
                )
            yield candidate
        if self.fail_after is not None and self.fail_after >= len(self.candidates):
            raise SourceError(
                "synthetic source failure",
                details={"processed_candidates": len(self.candidates)},
            )

    def close(self) -> None:
        self.closed = True
