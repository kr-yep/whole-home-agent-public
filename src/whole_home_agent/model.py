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


class UseClass(str, Enum):
    D0_SYNTHETIC = "D0_SYNTHETIC"


class TimestampBasis(str, Enum):
    SYNTHETIC = "synthetic"


class QueryStatus(str, Enum):
    FOUND = "FOUND"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"
    SCOPE_REQUIRED = "SCOPE_REQUIRED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    FRONTIER_MISMATCH = "FRONTIER_MISMATCH"


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
