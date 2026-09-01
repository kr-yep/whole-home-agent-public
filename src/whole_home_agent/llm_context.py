"""Minimized text-only presentation context for an optional language layer."""

from __future__ import annotations

from collections.abc import Mapping


CONTEXT_SCHEMA = "whole-home-agent.location-context.v1"
_QUERY_STATUSES = frozenset(
    {
        "CONFLICT",
        "FOUND",
        "FRONTIER_MISMATCH",
        "OUT_OF_SCOPE",
        "SCOPE_REQUIRED",
        "UNKNOWN",
    }
)


def _required_text(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _optional_text(record: Mapping[str, object], key: str) -> str | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be null or a non-empty string")
    return value


def build_llm_text_context(answer: Mapping[str, object]) -> dict[str, object]:
    """Project only the fields needed to verbalize one scoped location answer.

    The input is the already-scoped public answer presentation, never a ledger,
    filesystem, model, credential, or provider object.  The returned mapping is a
    local preview; constructing it performs no I/O and grants no egress authority.
    """

    if not isinstance(answer, Mapping):
        raise TypeError("answer must be a mapping")

    status = _required_text(answer, "status")
    if status not in _QUERY_STATUSES:
        raise ValueError(f"unsupported answer status: {status}")

    location_id = _optional_text(answer, "location_id")
    if status == "FOUND" and location_id is None:
        raise ValueError("FOUND answers require location_id")
    if status != "FOUND" and location_id is not None:
        raise ValueError("non-FOUND answers must not expose location_id")

    relation_path = answer.get("relation_path")
    if not isinstance(relation_path, (list, tuple)):
        raise ValueError("relation_path must be a list or tuple")
    if status != "FOUND" and relation_path:
        raise ValueError("non-FOUND answers must not expose relation facts")

    relation_facts: list[dict[str, str]] = []
    for index, value in enumerate(relation_path):
        if not isinstance(value, Mapping):
            raise ValueError(f"relation_path[{index}] must be a mapping")
        relation_facts.append(
            {
                "subject_id": _required_text(value, "subject_id"),
                "predicate": _required_text(value, "predicate"),
                "object_id": _required_text(value, "object_id"),
                "epistemic_status": _required_text(value, "epistemic_status"),
            }
        )

    return {
        "schema": CONTEXT_SCHEMA,
        "purpose": "verbalize_location_answer",
        "answer": {
            "subject_id": _required_text(answer, "subject_id"),
            "status": status,
            "location_id": location_id,
            "epistemic_status": _required_text(answer, "epistemic_status"),
        },
        "relation_facts": relation_facts,
    }
