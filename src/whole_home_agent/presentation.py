"""Local presentation boundary for one minimized location-answer context."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .llm_context import CONTEXT_SCHEMA


PRESENTATION_SCHEMA = "whole-home-agent.presentation-result.v1"
DETERMINISTIC_PRESENTER_ID = "deterministic-location/1"
PRESENTED = "PRESENTED"
FALLBACK = "FALLBACK"
PRESENTER_FAILURE = "PRESENTER_FAILURE"
MAX_PRESENTATION_CHARACTERS = 500
FALLBACK_TEXT = "無法產生文字摘要；請以結構化答案與證據鏈為準。"

_PURPOSE = "verbalize_location_answer"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_PRESENTER_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")
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
_EPISTEMIC_STATUSES = frozenset({"estimated", "reported"})

# One line per abstention kind. CONFLICT cannot name its candidates here because
# `location-context.v1` withholds them from every presenter; widening that packet
# is a separate recorded decision, not something this renderer may assume.
_ABSTENTION_PROSE = {
    "UNKNOWN": (
        "在這段固定重播中，沒有有效證據可以定位{subject}；"
        "系統回傳 {status}，不補猜位置。"
    ),
    "CONFLICT": (
        "在這段固定重播中，{subject}的位置證據互相衝突；"
        "系統回傳 {status}，不會替你選一個，也不補猜位置。"
    ),
    "FRONTIER_MISMATCH": (
        "你問的時間點超出這段重播已提交的範圍；"
        "系統回傳 {status}，不補猜位置。"
    ),
    "OUT_OF_SCOPE": (
        "這個問題不屬於目前這段重播的範圍；系統回傳 {status}，不補猜位置。"
    ),
    "SCOPE_REQUIRED": (
        "查詢沒有帶足範圍資訊；系統回傳 {status}，不補猜位置。"
    ),
}
_PREDICATES = frozenset({"at_zone", "inside"})
_DISPLAY_NAMES = {
    "bag": "包包",
    "book": "書",
    "desk": "書桌",
    "drawer": "抽屜",
    "key": "鑰匙",
    "remote": "遙控器",
    "shelf": "書架",
    "sofa": "沙發",
    "phone": "手機",
    "cup": "水杯",
    "laptop": "筆記型電腦",
    "desk": "書桌",
    # The two branches disagreed here: 餐桌 for a dining table, 茶几 for a coffee
    # table. Keeping the one already on main, because renaming something that has
    # shipped surprises more than a remote control resting on the wrong kind of
    # table. One word to change if the inventory replay reads better the other way.
    "table": "餐桌",
    "drawer": "抽屜",
    "shelf": "書架",
    "wallet": "錢包",
    "remote": "遙控器",
    "book": "書",
}


class LocationPresenter(Protocol):
    """Narrow presentation-only port; it has no state, tool, or authority handle."""

    presenter_id: str

    def present(self, context: Mapping[str, object]) -> str:
        """Return prose for one already-scoped, validated location context."""


@dataclass(frozen=True, slots=True)
class _RelationFact:
    subject_id: str
    predicate: str
    object_id: str
    epistemic_status: str


@dataclass(frozen=True, slots=True)
class _LocationContext:
    subject_id: str
    status: str
    location_id: str | None
    epistemic_status: str
    relation_facts: tuple[_RelationFact, ...]


@dataclass(frozen=True, slots=True)
class PresentationResult:
    """Sanitized result of one presentation attempt."""

    status: str
    presenter_id: str
    context_schema: str
    text: str
    fallback_used: bool
    failure_code: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": PRESENTATION_SCHEMA,
            "status": self.status,
            "presenter_id": self.presenter_id,
            "context_schema": self.context_schema,
            "text": self.text,
            "fallback_used": self.fallback_used,
            "failure_code": self.failure_code,
        }


def _exact_mapping(
    value: object, *, path: str, fields: frozenset[str]
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be a mapping")
    if set(value) != fields:
        raise ValueError(f"{path} fields do not match the presentation contract")
    return value


def _required_text(record: Mapping[str, object], key: str, *, path: str) -> str:
    value = record[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path}.{key} must be a non-empty string")
    return value


def _identifier_text(record: Mapping[str, object], key: str, *, path: str) -> str:
    value = _required_text(record, key, path=path)
    if _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{path}.{key} is outside the identifier contract")
    return value


def _parse_context(context: Mapping[str, object]) -> _LocationContext:
    root = _exact_mapping(
        context,
        path="context",
        fields=frozenset({"schema", "purpose", "answer", "relation_facts"}),
    )
    if root["schema"] != CONTEXT_SCHEMA or root["purpose"] != _PURPOSE:
        raise ValueError("context schema or purpose is unsupported")

    answer = _exact_mapping(
        root["answer"],
        path="context.answer",
        fields=frozenset(
            {"subject_id", "status", "location_id", "epistemic_status"}
        ),
    )
    subject_id = _identifier_text(answer, "subject_id", path="context.answer")
    status = _required_text(answer, "status", path="context.answer")
    if status not in _QUERY_STATUSES:
        raise ValueError("context.answer.status is unsupported")
    epistemic_status = _required_text(
        answer, "epistemic_status", path="context.answer"
    )
    # A resolved answer carries the evidence's own epistemic status; an unresolved
    # one echoes its query status. Accepting only the resolved pair rejected every
    # non-FOUND context before any presenter ran, so abstentions could not be
    # verbalized at all.
    expected_epistemic = (
        _EPISTEMIC_STATUSES if status == "FOUND" else frozenset({status.lower()})
    )
    if epistemic_status not in expected_epistemic:
        raise ValueError("context.answer.epistemic_status is unsupported")

    raw_location = answer["location_id"]
    location_id: str | None
    if raw_location is None:
        location_id = None
    elif isinstance(raw_location, str) and _IDENTIFIER.fullmatch(raw_location):
        location_id = raw_location
    else:
        raise ValueError("context.answer.location_id is outside the identifier contract")
    if status == "FOUND" and location_id is None:
        raise ValueError("FOUND context requires a location")
    if status != "FOUND" and location_id is not None:
        raise ValueError("non-FOUND context must abstain from location")

    raw_facts = root["relation_facts"]
    if not isinstance(raw_facts, list):
        raise ValueError("context.relation_facts must be a list")
    if status != "FOUND" and raw_facts:
        raise ValueError("non-FOUND context must abstain from relation facts")

    facts: list[_RelationFact] = []
    for index, raw_fact in enumerate(raw_facts):
        path = f"context.relation_facts[{index}]"
        fact = _exact_mapping(
            raw_fact,
            path=path,
            fields=frozenset(
                {"subject_id", "predicate", "object_id", "epistemic_status"}
            ),
        )
        predicate = _required_text(fact, "predicate", path=path)
        if predicate not in _PREDICATES:
            raise ValueError(f"{path}.predicate is unsupported")
        fact_epistemic_status = _required_text(
            fact, "epistemic_status", path=path
        )
        if fact_epistemic_status not in _EPISTEMIC_STATUSES:
            raise ValueError(f"{path}.epistemic_status is unsupported")
        facts.append(
            _RelationFact(
                subject_id=_identifier_text(fact, "subject_id", path=path),
                predicate=predicate,
                object_id=_identifier_text(fact, "object_id", path=path),
                epistemic_status=fact_epistemic_status,
            )
        )
    return _LocationContext(
        subject_id=subject_id,
        status=status,
        location_id=location_id,
        epistemic_status=epistemic_status,
        relation_facts=tuple(facts),
    )


def _normalized_context(context: Mapping[str, object]) -> dict[str, object]:
    parsed = _parse_context(context)
    return {
        "schema": CONTEXT_SCHEMA,
        "purpose": _PURPOSE,
        "answer": {
            "subject_id": parsed.subject_id,
            "status": parsed.status,
            "location_id": parsed.location_id,
            "epistemic_status": parsed.epistemic_status,
        },
        "relation_facts": [
            {
                "subject_id": fact.subject_id,
                "predicate": fact.predicate,
                "object_id": fact.object_id,
                "epistemic_status": fact.epistemic_status,
            }
            for fact in parsed.relation_facts
        ],
    }


def _display_name(identifier: str) -> str:
    if identifier in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[identifier]
    if identifier.startswith("custom_"):
        return identifier[len("custom_") :]
    return identifier


class DeterministicLocationPresenter:
    """Pure local renderer that verbalizes only the active relation context."""

    presenter_id = DETERMINISTIC_PRESENTER_ID

    def present(self, context: Mapping[str, object]) -> str:
        parsed = _parse_context(context)
        subject = _display_name(parsed.subject_id)
        if parsed.status != "FOUND":
            # Abstentions differ in kind. Saying "not enough evidence" for a
            # CONFLICT is wrong -- there is too much, pointing two ways -- and for
            # a scope error it describes the wrong failure entirely.
            template = _ABSTENTION_PROSE.get(parsed.status)
            if template is None:
                return (
                    f"在這段固定重播中，系統沒有回答{subject}的位置；"
                    f"回傳 {parsed.status}，不補猜位置。"
                )
            return template.format(subject=subject, status=parsed.status)

        assert parsed.location_id is not None
        location = _display_name(parsed.location_id)
        verb = "估計" if parsed.epistemic_status == "estimated" else "記錄"
        for inside in parsed.relation_facts:
            if inside.subject_id != parsed.subject_id or inside.predicate != "inside":
                continue
            for at_zone in parsed.relation_facts:
                if (
                    at_zone.subject_id == inside.object_id
                    and at_zone.predicate == "at_zone"
                    and at_zone.object_id == parsed.location_id
                ):
                    container = _display_name(inside.object_id)
                    return (
                        f"在這段固定重播中，系統{verb}{subject}在{container}裡，"
                        f"且{container}位於{location}；"
                        f"所以{subject}可能在{location}上的{container}裡。"
                    )

        return f"在這段固定重播中，系統{verb}{subject}位於{location}。"


def _safe_presenter_id(presenter: object) -> str:
    value = getattr(presenter, "presenter_id", None)
    if isinstance(value, str) and _PRESENTER_IDENTIFIER.fullmatch(value):
        return value
    return "unavailable"


def _valid_output(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("presenter output must be non-empty text")
    if len(value) > MAX_PRESENTATION_CHARACTERS:
        raise ValueError("presenter output exceeds the bounded presentation size")
    if any(ord(character) < 32 for character in value):
        raise ValueError("presenter output contains control characters")
    return value


def present_location_context(
    context: Mapping[str, object], presenter: LocationPresenter
) -> PresentationResult:
    """Validate, minimize, present, and fall back without exposing failure content."""

    presenter_id = _safe_presenter_id(presenter)
    try:
        normalized = _normalized_context(context)
        if presenter_id == "unavailable":
            raise ValueError("presenter identity is invalid")
        text = _valid_output(presenter.present(normalized))
    except Exception:
        return PresentationResult(
            status=FALLBACK,
            presenter_id=presenter_id,
            context_schema=CONTEXT_SCHEMA,
            text=FALLBACK_TEXT,
            fallback_used=True,
            failure_code=PRESENTER_FAILURE,
        )
    return PresentationResult(
        status=PRESENTED,
        presenter_id=presenter_id,
        context_schema=CONTEXT_SCHEMA,
        text=text,
        fallback_used=False,
        failure_code=None,
    )
