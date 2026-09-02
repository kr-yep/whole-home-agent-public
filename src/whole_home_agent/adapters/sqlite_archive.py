"""SQLite adapter for complete, synthetic/public replay sessions only."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path

from whole_home_agent.errors import ArchiveError, ErrorCode
from whole_home_agent.memory import ARCHIVE_SCHEMA, ArchiveWriteReceipt
from whole_home_agent.model import (
    PROJECTOR_VERSION,
    VALIDATOR_VERSION,
    ClaimCommit,
    ClaimCandidate,
    ClaimOperation,
    EpistemicStatus,
    EvidenceRef,
    Predicate,
    ProducerRef,
    ReplaySession,
    SourceDescriptor,
    SourceKind,
    SourcePosition,
    TimestampBasis,
    UseClass,
)
from whole_home_agent.relations import reduce_relations
from whole_home_agent.serialization import canonical_json, semantic_document
from whole_home_agent.ledger import build_ledger_from_candidates
from whole_home_agent.sources import validate_candidate, validate_descriptor


_DATABASE_VERSION = 1


def _position_dict(position: SourcePosition) -> dict[str, object]:
    return {
        "source_sequence": position.source_sequence,
        "source_offset": position.source_offset,
        "timestamp_basis": position.timestamp_basis.value,
        "frame_index": position.frame_index,
        "pts": position.pts,
        "time_base_numerator": position.time_base_numerator,
        "time_base_denominator": position.time_base_denominator,
    }


def _position(value: object) -> SourcePosition:
    if not isinstance(value, Mapping) or set(value) != {
        "source_sequence",
        "source_offset",
        "timestamp_basis",
        "frame_index",
        "pts",
        "time_base_numerator",
        "time_base_denominator",
    }:
        raise ArchiveError("archived source position is invalid")
    integer_fields = ("source_sequence", "source_offset")
    optional_integer_fields = (
        "frame_index",
        "pts",
        "time_base_numerator",
        "time_base_denominator",
    )
    if any(type(value[field]) is not int for field in integer_fields) or any(
        value[field] is not None and type(value[field]) is not int
        for field in optional_integer_fields
    ):
        raise ArchiveError("archived source position integer fields are invalid")
    try:
        return SourcePosition(
            source_sequence=value["source_sequence"],
            source_offset=value["source_offset"],
            timestamp_basis=TimestampBasis(value["timestamp_basis"]),
            frame_index=value["frame_index"],
            pts=value["pts"],
            time_base_numerator=value["time_base_numerator"],
            time_base_denominator=value["time_base_denominator"],
        )
    except (TypeError, ValueError) as error:
        raise ArchiveError("archived source position is invalid") from error


def _producer_dict(value: ProducerRef) -> dict[str, str]:
    return {
        "component": value.component,
        "version": value.version,
        "artifact_hash": value.artifact_hash,
        "config_hash": value.config_hash,
    }


def _producer(value: object) -> ProducerRef | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {
        "component",
        "version",
        "artifact_hash",
        "config_hash",
    }:
        raise ArchiveError("archived producer reference is invalid")
    try:
        return ProducerRef(**value)
    except TypeError as error:
        raise ArchiveError("archived producer reference is invalid") from error


def _evidence_dict(value: EvidenceRef) -> dict[str, object]:
    return {
        "evidence_id": value.evidence_id,
        "source_id": value.source_id,
        "start": _position_dict(value.start),
        "end": _position_dict(value.end),
        "confidence": value.confidence,
        "quality": value.quality,
    }


def _evidence(value: object) -> EvidenceRef:
    if not isinstance(value, Mapping) or set(value) != {
        "evidence_id",
        "source_id",
        "start",
        "end",
        "confidence",
        "quality",
    }:
        raise ArchiveError("archived evidence reference is invalid")
    try:
        return EvidenceRef(
            evidence_id=value["evidence_id"],
            source_id=value["source_id"],
            start=_position(value["start"]),
            end=_position(value["end"]),
            confidence=value["confidence"],
            quality=value["quality"],
        )
    except TypeError as error:
        raise ArchiveError("archived evidence reference is invalid") from error


def _claim_dict(value: ClaimCommit) -> dict[str, object]:
    return {
        "commit_index": value.commit_index,
        "claim_id": value.claim_id,
        "source_sequence": value.source_sequence,
        "source_offset": value.source_offset,
        "operation": value.operation.value,
        "subject_id": value.subject_id,
        "predicate": value.predicate.value,
        "object_id": value.object_id,
        "epistemic_status": value.epistemic_status.value,
        "source_position": (
            _position_dict(value.source_position)
            if value.source_position is not None
            else None
        ),
        "producer_ref": (
            _producer_dict(value.producer_ref) if value.producer_ref is not None else None
        ),
        "evidence_refs": [_evidence_dict(item) for item in value.evidence_refs],
    }


def _claim(value: object, expected_index: int) -> ClaimCommit:
    fields = {
        "commit_index",
        "claim_id",
        "source_sequence",
        "source_offset",
        "operation",
        "subject_id",
        "predicate",
        "object_id",
        "epistemic_status",
        "source_position",
        "producer_ref",
        "evidence_refs",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ArchiveError("archived claim is invalid")
    if value["commit_index"] != expected_index or not isinstance(value["evidence_refs"], list):
        raise ArchiveError("archived claim ordering is invalid")
    try:
        return ClaimCommit(
            commit_index=expected_index,
            claim_id=value["claim_id"],
            source_sequence=value["source_sequence"],
            source_offset=value["source_offset"],
            operation=ClaimOperation(value["operation"]),
            subject_id=value["subject_id"],
            predicate=Predicate(value["predicate"]),
            object_id=value["object_id"],
            epistemic_status=EpistemicStatus(value["epistemic_status"]),
            source_position=(
                _position(value["source_position"])
                if value["source_position"] is not None
                else None
            ),
            producer_ref=_producer(value["producer_ref"]),
            evidence_refs=tuple(_evidence(item) for item in value["evidence_refs"]),
        )
    except (TypeError, ValueError) as error:
        raise ArchiveError("archived claim is invalid") from error


def _descriptor_dict(value: SourceDescriptor) -> dict[str, str]:
    return {
        "source_id": value.source_id,
        "source_revision": value.source_revision,
        "source_kind": value.source_kind.value,
        "use_class": value.use_class.value,
        "timestamp_basis": value.timestamp_basis.value,
        "content_hash": value.content_hash,
        "license_manifest_id": value.license_manifest_id,
        "world_scope": value.world_scope,
    }


def _descriptor(value: object) -> SourceDescriptor:
    if not isinstance(value, Mapping) or set(value) != {
        "source_id",
        "source_revision",
        "source_kind",
        "use_class",
        "timestamp_basis",
        "content_hash",
        "license_manifest_id",
        "world_scope",
    }:
        raise ArchiveError("archived source descriptor is invalid")
    try:
        descriptor = SourceDescriptor(
            source_id=value["source_id"],
            source_revision=value["source_revision"],
            source_kind=SourceKind(value["source_kind"]),
            use_class=UseClass(value["use_class"]),
            timestamp_basis=TimestampBasis(value["timestamp_basis"]),
            content_hash=value["content_hash"],
            license_manifest_id=value["license_manifest_id"],
            world_scope=value["world_scope"],
        )
    except (TypeError, ValueError) as error:
        raise ArchiveError("archived source descriptor is invalid") from error
    if descriptor.use_class not in {UseClass.D0_SYNTHETIC, UseClass.D0_PUBLIC}:
        raise ArchiveError("archive accepts only D0 synthetic or public sources")
    validate_descriptor(descriptor)
    return descriptor


def _session_document(session: ReplaySession) -> dict[str, object]:
    descriptor = session.source_descriptor
    if descriptor is None or descriptor.use_class not in {
        UseClass.D0_SYNTHETIC,
        UseClass.D0_PUBLIC,
    }:
        raise ArchiveError("archive accepts only complete D0 replay sessions")
    if session.rejections:
        raise ArchiveError("archive accepts only sessions without claim rejections")
    if session.validator_version != VALIDATOR_VERSION or session.projector_version != PROJECTOR_VERSION:
        raise ArchiveError("session rule versions are not supported by this archive")
    if hashlib.sha256(session.semantic_output.encode("utf-8")).hexdigest() != session.canonical_hash:
        raise ArchiveError("session semantic hash does not verify")
    rebuilt_projection = reduce_relations(session.accepted_claims)
    rebuilt_output = canonical_json(
        semantic_document(descriptor, session.ledger, rebuilt_projection)
    )
    if (
        rebuilt_output != session.semantic_output
        or rebuilt_projection.frontier != session.projection_frontier
    ):
        raise ArchiveError("session does not match its deterministic projection")
    return {
        "schema": ARCHIVE_SCHEMA,
        "replay_run_id": session.replay_run_id,
        "descriptor": _descriptor_dict(descriptor),
        "claims": [_claim_dict(item) for item in session.accepted_claims],
        "semantic_output": session.semantic_output,
        "canonical_hash": session.canonical_hash,
        "validator_version": session.validator_version,
        "projector_version": session.projector_version,
        "projection_frontier": session.projection_frontier,
    }


def _restore_session(payload: str) -> ReplaySession:
    try:
        document = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as error:
        raise ArchiveError("archived session JSON is invalid") from error
    if not isinstance(document, Mapping) or set(document) != {
        "schema",
        "replay_run_id",
        "descriptor",
        "claims",
        "semantic_output",
        "canonical_hash",
        "validator_version",
        "projector_version",
        "projection_frontier",
    }:
        raise ArchiveError("archived session fields are invalid")
    if document["schema"] != ARCHIVE_SCHEMA:
        raise ArchiveError("archived session schema is unsupported")
    run_id = document["replay_run_id"]
    if (
        not isinstance(run_id, str)
        or not run_id
        or run_id != run_id.strip()
        or len(run_id) > 256
        or any(ord(character) < 32 or ord(character) == 127 for character in run_id)
    ):
        raise ArchiveError("archived replay run identity is invalid")
    if document["validator_version"] != VALIDATOR_VERSION or document["projector_version"] != PROJECTOR_VERSION:
        raise ArchiveError("archived session rule version is unsupported")
    if not isinstance(document["claims"], list) or not isinstance(document["semantic_output"], str):
        raise ArchiveError("archived claims or semantic output are invalid")

    descriptor = _descriptor(document["descriptor"])
    claims = tuple(_claim(item, index) for index, item in enumerate(document["claims"]))
    candidates = tuple(
        ClaimCandidate(
            claim_id=claim.claim_id,
            source_sequence=claim.source_sequence,
            source_offset=claim.source_offset,
            operation=claim.operation,
            subject_id=claim.subject_id,
            predicate=claim.predicate,
            object_id=claim.object_id,
            epistemic_status=claim.epistemic_status,
            source_position=claim.source_position,
            producer_ref=claim.producer_ref,
            evidence_refs=claim.evidence_refs,
        )
        for claim in claims
    )
    for candidate in candidates:
        validate_candidate(candidate, descriptor)
    ledger = build_ledger_from_candidates(candidates)
    if ledger.accepted_claims != claims:
        raise ArchiveError("archived claim commits failed deterministic rebuild")
    projection = reduce_relations(claims)
    rebuilt = canonical_json(semantic_document(descriptor, ledger, projection))
    digest = hashlib.sha256(rebuilt.encode("utf-8")).hexdigest()
    if (
        rebuilt != document["semantic_output"]
        or digest != document["canonical_hash"]
        or projection.frontier != document["projection_frontier"]
    ):
        raise ArchiveError("archived replay failed deterministic rebuild")
    return ReplaySession(
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
        semantic_output=rebuilt,
        canonical_hash=digest,
        source_descriptor=descriptor,
    )


class SQLiteReplayArchive:
    """One-table append-oriented archive with deterministic rebuild on every read."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path) or not path.name:
            raise ArchiveError("archive path must name one SQLite file")
        self._path = path.resolve()

    def _connect(self, *, create: bool) -> sqlite3.Connection:
        connection: sqlite3.Connection | None = None
        try:
            if create:
                self._path.parent.mkdir(parents=True, exist_ok=True)
            elif not self._path.is_file():
                raise ArchiveError(
                    "archive contains no completed replay",
                    error_code=ErrorCode.ARCHIVE_NOT_FOUND,
                )
            connection = sqlite3.connect(self._path, timeout=5)
            connection.execute("PRAGMA foreign_keys = ON")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, _DATABASE_VERSION) or (
                version == 0 and not create
            ):
                raise ArchiveError("archive database version is unsupported")
            if version == 0:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS replay_sessions (
                        archive_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        world_scope TEXT NOT NULL,
                        replay_run_id TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        payload_sha256 TEXT NOT NULL,
                        UNIQUE(world_scope, replay_run_id)
                    )
                    """
                )
                connection.execute(f"PRAGMA user_version = {_DATABASE_VERSION}")
                connection.commit()
            return connection
        except ArchiveError:
            if connection is not None:
                connection.close()
            raise
        except (OSError, sqlite3.Error) as error:
            if connection is not None:
                connection.close()
            raise ArchiveError("archive database could not be opened") from error

    def save_completed(self, session: ReplaySession) -> ArchiveWriteReceipt:
        document = _session_document(session)
        payload = canonical_json(document)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        connection = self._connect(create=True)
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT payload_sha256 FROM replay_sessions WHERE world_scope = ? AND replay_run_id = ?",
                (session.world_scope, session.replay_run_id),
            ).fetchone()
            if existing is not None:
                if existing[0] != payload_hash:
                    raise ArchiveError(
                        "archive identity already contains a different completed replay",
                        error_code=ErrorCode.ARCHIVE_CONFLICT,
                    )
                connection.commit()
                status = "UNCHANGED"
            else:
                connection.execute(
                    "INSERT INTO replay_sessions(world_scope, replay_run_id, payload_json, payload_sha256) VALUES (?, ?, ?, ?)",
                    (session.world_scope, session.replay_run_id, payload, payload_hash),
                )
                connection.commit()
                status = "INSERTED"
        except ArchiveError:
            connection.rollback()
            raise
        except sqlite3.Error as error:
            connection.rollback()
            raise ArchiveError("archive write failed") from error
        finally:
            connection.close()
        return ArchiveWriteReceipt(
            status=status,
            world_scope=session.world_scope,
            replay_run_id=session.replay_run_id,
            canonical_hash=session.canonical_hash,
        )

    def load_latest(self) -> ReplaySession:
        connection = self._connect(create=False)
        try:
            row = connection.execute(
                "SELECT payload_json, payload_sha256 FROM replay_sessions ORDER BY archive_sequence DESC LIMIT 1"
            ).fetchone()
        except sqlite3.Error as error:
            raise ArchiveError("archive read failed") from error
        finally:
            connection.close()
        if row is None:
            raise ArchiveError(
                "archive contains no completed replay",
                error_code=ErrorCode.ARCHIVE_NOT_FOUND,
            )
        payload, expected_hash = row
        if not isinstance(payload, str) or not isinstance(expected_hash, str):
            raise ArchiveError("archived payload columns are invalid")
        actual_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if actual_hash != expected_hash:
            raise ArchiveError("archived payload hash does not verify")
        return _restore_session(payload)
