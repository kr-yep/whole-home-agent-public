"""Deterministic free-text reduction to one allowlisted location subject."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping

from .errors import ErrorCode, QuestionError


QUESTION_PARSER_ID = "bounded-location-question/1"
MAX_QUESTION_CHARACTERS = 200

DEFAULT_ENTITY_ALIASES: Mapping[str, tuple[str, ...]] = {
    "key": ("key", "keys", "鑰匙", "钥匙"),
    "bag": ("bag", "backpack", "包包", "背包"),
    "sofa": ("sofa", "couch", "沙發", "沙发"),
}

_ENGLISH_LOCATION_INTENT = re.compile(r"\b(where|locate|find|location)\b")
_CJK_LOCATION_INTENT = ("在哪", "哪裡", "哪里", "位置", "放哪", "找")
_ENGLISH_ACTION = re.compile(r"\b(open|close|unlock|buy|purchase|send|message)\b")
_CJK_ACTION = (
    "開門",
    "开门",
    "關門",
    "关门",
    "解鎖",
    "解锁",
    "開燈",
    "开灯",
    "關燈",
    "关灯",
    "購買",
    "购买",
    "傳訊",
    "传讯",
    "發送",
    "发送",
)


def _contains_alias(text: str, alias: str) -> bool:
    if alias.isascii():
        return re.search(rf"(?<![a-z0-9_]){re.escape(alias)}(?![a-z0-9_])", text) is not None
    return alias in text


def parse_location_question(
    question: str,
    *,
    allowed_entity_ids: Iterable[str],
    aliases: Mapping[str, tuple[str, ...]] = DEFAULT_ENTITY_ALIASES,
) -> str:
    """Return exactly one subject ID or reject without guessing.

    This parser recognizes only a bounded location intent.  It never executes text,
    changes policy, opens storage, or asks a model to choose the query target.
    """

    if not isinstance(question, str):
        raise QuestionError("question must be text")
    if any(ord(character) < 32 or ord(character) == 127 for character in question):
        raise QuestionError("question contains control characters")
    normalized = unicodedata.normalize("NFKC", question).strip().lower()
    if (
        not normalized
        or len(normalized) > MAX_QUESTION_CHARACTERS
    ):
        raise QuestionError("question is empty, overlong, or contains control characters")

    if not (
        _ENGLISH_LOCATION_INTENT.search(normalized)
        or any(token in normalized for token in _CJK_LOCATION_INTENT)
    ):
        raise QuestionError(
            "only bounded object-location questions are supported",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )
    if _ENGLISH_ACTION.search(normalized) or any(
        token in normalized for token in _CJK_ACTION
    ):
        raise QuestionError(
            "action-shaped questions are outside the location-query capability",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )

    allowed = tuple(sorted(set(allowed_entity_ids)))
    matches: list[str] = []
    for entity_id in allowed:
        entity_aliases = aliases.get(entity_id, ()) + (entity_id,)
        if any(_contains_alias(normalized, alias.lower()) for alias in entity_aliases):
            matches.append(entity_id)
    if len(matches) != 1:
        raise QuestionError(
            "question must name exactly one known object",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
            details={"matched_entity_count": len(matches)},
        )
    return matches[0]
