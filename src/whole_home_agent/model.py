"""Canonical immutable values shared by the B0 replay components."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


VALIDATOR_VERSION = "b0-claim-validator/1"
PROJECTOR_VERSION = "b0-relation-projector/1"


class ClaimOperation(str, Enum):
    ASSERT = "assert"
    RETRACT = "retract"


class Predicate(str, Enum):
    INSIDE = "inside"
    AT_ZONE = "at_zone"


class EpistemicStatus(str, Enum):
    REPORTED = "reported"
    ESTIMATED = "estimated"


class UseClass(str, Enum):
    D0_SYNTHETIC = "D0_SYNTHETIC"
    D0_PUBLIC = "D0_PUBLIC"


class TimestampBasis(str, Enum):
    SYNTHETIC = "synthetic"
    MEDIA_PTS = "media_pts"
    SOURCE_FRAME_INDEX = "source_frame_index"


class SourceKind(str, Enum):
    SEMANTIC_FIXTURE = "semantic_fixture"
    RECORDED_VIDEO = "recorded_video"
    RECORDED_FRAME_SET = "recorded_frame_set"


class RunStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"


class QueryStatus(str, Enum):
    FOUND = "FOUND"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"
    SCOPE_REQUIRED = "SCOPE_REQUIRED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    FRONTIER_MISMATCH = "FRONTIER_MISMATCH"


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    """Immutable identity and use envelope for one replayable source."""

    source_id: str
    source_revision: str
    source_kind: SourceKind
    use_class: UseClass
    timestamp_basis: TimestampBasis
    content_hash: str
    license_manifest_id: str
    world_scope: str


@dataclass(frozen=True, slots=True)
class SourcePosition:
    """Position in a source without relying on filesystem timestamps."""

    source_sequence: int
    source_offset: int
    timestamp_basis: TimestampBasis
    frame_index: int | None = None
    pts: int | None = None
    time_base_numerator: int | None = None
    time_base_denominator: int | None = None

    def identity_payload(self) -> tuple[Any, ...]:
        return (
            self.source_sequence,
            self.source_offset,
            self.timestamp_basis.value,
            self.frame_index,
            self.pts,
            self.time_base_numerator,
            self.time_base_denominator,
        )


@dataclass(frozen=True, slots=True)
class ProducerRef:
    """Pinned producer identity for a model, rule, or fixture translator."""

    component: str
    version: str
    artifact_hash: str
    config_hash: str

    def identity_payload(self) -> tuple[str, ...]:
        return (
            self.component,
            self.version,
            self.artifact_hash,
            self.config_hash,
        )


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """Minimum evidence pointer; raw media is deliberately excluded."""

    evidence_id: str
    source_id: str
    start: SourcePosition
    end: SourcePosition
    confidence: float | None = None
    quality: str = "unknown"

    def identity_payload(self) -> tuple[Any, ...]:
        return (
            self.evidence_id,
            self.source_id,
            self.start.identity_payload(),
            self.end.identity_payload(),
            self.confidence,
            self.quality,
        )


@dataclass(frozen=True, slots=True)
class ClaimCandidate:
    """A schema-valid claim before it receives a session commit index."""

    claim_id: str
    source_sequence: int
    operation: ClaimOperation
    subject_id: str
    predicate: Predicate
    object_id: str
    epistemic_status: EpistemicStatus
    source_offset: int
    source_position: SourcePosition | None = None
    producer_ref: ProducerRef | None = None
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def identity_payload(self) -> tuple[Any, ...]:
        """Canonical identity payload; delivery offset is deliberately excluded."""

        return (
            self.claim_id,
            self.source_sequence,
            self.operation.value,
            self.subject_id,
            self.predicate.value,
            self.object_id,
            self.epistemic_status.value,
        )


@dataclass(frozen=True, slots=True)
class ReplayFixture:
    schema_version: int
    fixture_id: str
    fixture_revision: str
    use_class: UseClass
    timestamp_basis: TimestampBasis
    claims: tuple[ClaimCandidate, ...]
    source_path: Path
    content_hash: str

    @property
    def world_scope(self) -> str:
        return f"fixture:{self.fixture_id}@{self.fixture_revision}"


@dataclass(frozen=True, slots=True)
class ClaimCommit:
    """One unique, immutable claim admitted to a replay session ledger."""

    commit_index: int
    claim_id: str
    source_sequence: int
    source_offset: int
    operation: ClaimOperation
    subject_id: str
    predicate: Predicate
    object_id: str
    epistemic_status: EpistemicStatus
    source_position: SourcePosition | None = None
    producer_ref: ProducerRef | None = None
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def identity_payload(self) -> tuple[Any, ...]:
        return (
            self.claim_id,
            self.source_sequence,
            self.operation.value,
            self.subject_id,
            self.predicate.value,
            self.object_id,
            self.epistemic_status.value,
        )

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "epistemic_status": self.epistemic_status.value,
            "object_id": self.object_id,
            "operation": self.operation.value,
            "predicate": self.predicate.value,
            "source_offset": self.source_offset,
            "source_sequence": self.source_sequence,
            "subject_id": self.subject_id,
        }


@dataclass(frozen=True, slots=True)
class ClaimRejection:
    """Reserved evidence for recoverable admission failures.

    The frozen B0 contract currently fails closed on invalid claims, so successful
    sessions normally expose an empty tuple.  Keeping the type explicit prevents a
    later implementation from silently dropping recoverable rejection evidence.
    """

    claim_id: str | None
    error_code: str
    reason: str
    source_offset: int | None = None


@dataclass(frozen=True, slots=True)
class SessionLedger:
    accepted_claims: tuple[ClaimCommit, ...]
    rejections: tuple[ClaimRejection, ...]


@dataclass(frozen=True, slots=True)
class ProjectionRelation:
    subject_id: str
    predicate: Predicate
    object_id: str
    source_claim_id: str
    source_sequence: int
    source_offset: int
    epistemic_status: EpistemicStatus = EpistemicStatus.REPORTED

    def semantic_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "predicate": self.predicate.value,
            "source_claim_id": self.source_claim_id,
            "source_offset": self.source_offset,
            "source_sequence": self.source_sequence,
            "subject_id": self.subject_id,
        }


@dataclass(frozen=True, slots=True)
class ProjectionState:
    frontier: int
    active_relations: tuple[ProjectionRelation, ...]


@dataclass(frozen=True, slots=True)
class RelationStep:
    subject_id: str
    predicate: Predicate
    object_id: str
    source_claim_id: str
    source_sequence: int
    source_offset: int
    epistemic_status: EpistemicStatus = EpistemicStatus.REPORTED


@dataclass(frozen=True, slots=True)
class QueryRequest:
    """A location query whose evidence scope is validated by :func:`locate`.

    Scope values intentionally remain nullable/empty at construction so hostile
    boundary tests receive a typed abstention instead of an incidental TypeError.
    """

    subject_id: str
    world_scope: str
    replay_run_id: str
    as_of_source_sequence: int | None


@dataclass(frozen=True, slots=True)
class AnswerTrace:
    status: QueryStatus
    subject_id: str
    location_id: str | None
    relation_path: tuple[RelationStep, ...]
    source_claim_ids: tuple[str, ...]
    world_scope: str
    replay_run_id: str
    as_of_source_sequence: int | None
    projection_frontier: int
    source_content_hash: str
    validator_version: str
    projector_version: str
    epistemic_status: str
    candidate_location_ids: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ReplaySession:
    fixture_id: str
    fixture_revision: str
    world_scope: str
    replay_run_id: str
    projection_frontier: int
    source_content_hash: str
    validator_version: str
    projector_version: str
    ledger: SessionLedger
    projection: ProjectionState
    semantic_output: str
    canonical_hash: str
    source_descriptor: SourceDescriptor | None = None

    @property
    def accepted_claims(self) -> tuple[ClaimCommit, ...]:
        return self.ledger.accepted_claims

    @property
    def rejections(self) -> tuple[ClaimRejection, ...]:
        return self.ledger.rejections

    @property
    def semantic_output_hash(self) -> str:
        """Compatibility alias naming what ``canonical_hash`` hashes."""

        return self.canonical_hash

    def locate(self, request: QueryRequest) -> AnswerTrace:
        from .relations import locate

        return locate(self, request)

    @property
    def source_id(self) -> str:
        return (
            self.source_descriptor.source_id
            if self.source_descriptor is not None
            else self.fixture_id
        )

    @property
    def source_revision(self) -> str:
        return (
            self.source_descriptor.source_revision
            if self.source_descriptor is not None
            else self.fixture_revision
        )


@dataclass(frozen=True, slots=True)
class StageTiming:
    stage: str
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class RunReceipt:
    """Non-authoritative execution evidence for one bounded replay attempt."""

    replay_run_id: str
    status: RunStatus
    source_id: str
    source_revision: str
    source_content_hash: str
    candidate_count: int
    accepted_claim_count: int
    rejected_claim_count: int
    duplicate_claim_count: int
    validator_version: str
    projector_version: str
    producer_refs: tuple[ProducerRef, ...]
    stage_timings: tuple[StageTiming, ...]
    projection_frontier: int | None = None
    semantic_output_hash: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted_claim_count": self.accepted_claim_count,
            "candidate_count": self.candidate_count,
            "duplicate_claim_count": self.duplicate_claim_count,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
            "producer_refs": [
                {
                    "artifact_hash": item.artifact_hash,
                    "component": item.component,
                    "config_hash": item.config_hash,
                    "version": item.version,
                }
                for item in self.producer_refs
            ],
            "projector_version": self.projector_version,
            "projection_frontier": self.projection_frontier,
            "rejected_claim_count": self.rejected_claim_count,
            "replay_run_id": self.replay_run_id,
            "source_content_hash": self.source_content_hash,
            "source_id": self.source_id,
            "source_revision": self.source_revision,
            "stage_timings_ms": {
                item.stage: item.elapsed_ms for item in self.stage_timings
            },
            "status": self.status.value,
            "semantic_output_hash": self.semantic_output_hash,
            "validator_version": self.validator_version,
        }


@dataclass(frozen=True, slots=True)
class ReplayRunResult:
    """A completed session or a typed failed attempt, never partial state."""

    status: RunStatus
    receipt: RunReceipt
    session: ReplaySession | None

    @property
    def complete(self) -> bool:
        return self.status is RunStatus.COMPLETE and self.session is not None
