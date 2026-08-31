"""Deterministic semantic serialization for replay sessions."""

from __future__ import annotations

import json
from typing import Any

from .model import (
    PROJECTOR_VERSION,
    VALIDATOR_VERSION,
    EvidenceRef,
    ProducerRef,
    SourceDescriptor,
    SourceKind,
    SourcePosition,
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _position_dict(position: SourcePosition) -> dict[str, object]:
    return {
        "frame_index": position.frame_index,
        "pts": position.pts,
        "source_offset": position.source_offset,
        "source_sequence": position.source_sequence,
        "time_base_denominator": position.time_base_denominator,
        "time_base_numerator": position.time_base_numerator,
        "timestamp_basis": position.timestamp_basis.value,
    }


def _evidence_dict(reference: EvidenceRef) -> dict[str, object]:
    return {
        "confidence": reference.confidence,
        "end": _position_dict(reference.end),
        "evidence_id": reference.evidence_id,
        "quality": reference.quality,
        "source_id": reference.source_id,
        "start": _position_dict(reference.start),
    }


def _producer_dict(reference: ProducerRef) -> dict[str, str]:
    return {
        "artifact_hash": reference.artifact_hash,
        "component": reference.component,
        "config_hash": reference.config_hash,
        "version": reference.version,
    }


def semantic_document(
    descriptor: SourceDescriptor,
    ledger: object,
    projection: object,
) -> dict[str, object]:
    """Build the frozen B0 shape or the provenance-rich B1 shape."""

    accepted_claims = getattr(ledger, "accepted_claims")
    active_relations = getattr(projection, "active_relations")
    frontier = getattr(projection, "frontier")
    if descriptor.source_kind is SourceKind.SEMANTIC_FIXTURE:
        return {
            "accepted_claims": [claim.semantic_dict() for claim in accepted_claims],
            "fixture": {
                "fixture_id": descriptor.source_id,
                "fixture_revision": descriptor.source_revision,
                "schema_version": 1,
                "timestamp_basis": descriptor.timestamp_basis.value,
                "use_class": descriptor.use_class.value,
            },
            "projection": {
                "active_relations": [
                    relation.semantic_dict() for relation in active_relations
                ],
                "frontier": frontier,
            },
            "rules": {
                "projector_version": PROJECTOR_VERSION,
                "validator_version": VALIDATOR_VERSION,
            },
            "world_scope": descriptor.world_scope,
        }

    claims: list[dict[str, object]] = []
    for claim in accepted_claims:
        item: dict[str, object] = claim.semantic_dict()
        item["evidence_refs"] = [
            _evidence_dict(reference) for reference in claim.evidence_refs
        ]
        item["producer_ref"] = (
            _producer_dict(claim.producer_ref)
            if claim.producer_ref is not None
            else None
        )
        item["source_position"] = (
            _position_dict(claim.source_position)
            if claim.source_position is not None
            else None
        )
        claims.append(item)
    return {
        "accepted_claims": claims,
        "projection": {
            "active_relations": [
                relation.semantic_dict() for relation in active_relations
            ],
            "frontier": frontier,
        },
        "rules": {
            "projector_version": PROJECTOR_VERSION,
            "validator_version": VALIDATOR_VERSION,
        },
        "source": {
            "content_hash": descriptor.content_hash,
            "license_manifest_id": descriptor.license_manifest_id,
            "source_id": descriptor.source_id,
            "source_kind": descriptor.source_kind.value,
            "source_revision": descriptor.source_revision,
            "timestamp_basis": descriptor.timestamp_basis.value,
            "use_class": descriptor.use_class.value,
        },
        "world_scope": descriptor.world_scope,
    }
