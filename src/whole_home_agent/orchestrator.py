"""Single composition boundary for the offline deterministic B0 replay."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from .errors import ErrorCode, FixtureError
from .ledger import build_ledger
from .model import (
    PROJECTOR_VERSION,
    VALIDATOR_VERSION,
    QueryRequest,
    ReplayFixture,
    ReplaySession,
)
from .relations import locate, reduce_relations


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


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def run_fixture(
    fixture: ReplayFixture, *, replay_run_id: str | None = None
) -> ReplaySession:
    """Validate, commit, and reduce one already-loaded fixture.

    This function is the B0 composition root: it wires pure ledger/reducer pieces
    synchronously and creates no cameras, queues, databases, network clients, or
    action executors.
    """

    if not isinstance(fixture, ReplayFixture):
        raise FixtureError(
            "run_fixture requires a ReplayFixture returned by load_fixture",
            error_code=ErrorCode.INVALID_SCHEMA,
        )
    run_id = _validate_run_id(
        replay_run_id
        if replay_run_id is not None
        else (
            f"replay:{fixture.fixture_id}@{fixture.fixture_revision}:"
            f"{uuid.uuid4().hex}"
        )
    )
    ledger = build_ledger(fixture)
    projection = reduce_relations(ledger.accepted_claims)
    semantic_document = {
        "accepted_claims": [
            claim.semantic_dict() for claim in ledger.accepted_claims
        ],
        "fixture": {
            "fixture_id": fixture.fixture_id,
            "fixture_revision": fixture.fixture_revision,
            "schema_version": fixture.schema_version,
            "timestamp_basis": fixture.timestamp_basis.value,
            "use_class": fixture.use_class.value,
        },
        "projection": {
            "active_relations": [
                relation.semantic_dict() for relation in projection.active_relations
            ],
            "frontier": projection.frontier,
        },
        "rules": {
            "projector_version": PROJECTOR_VERSION,
            "validator_version": VALIDATOR_VERSION,
        },
        "world_scope": fixture.world_scope,
    }
    semantic_output = _canonical_json(semantic_document)
    canonical_hash = hashlib.sha256(semantic_output.encode("utf-8")).hexdigest()
    return ReplaySession(
        fixture_id=fixture.fixture_id,
        fixture_revision=fixture.fixture_revision,
        world_scope=fixture.world_scope,
        replay_run_id=run_id,
        projection_frontier=projection.frontier,
        source_content_hash=fixture.content_hash,
        validator_version=VALIDATOR_VERSION,
        projector_version=PROJECTOR_VERSION,
        ledger=ledger,
        projection=projection,
        semantic_output=semantic_output,
        canonical_hash=canonical_hash,
    )


__all__ = ["locate", "run_fixture", "QueryRequest"]
