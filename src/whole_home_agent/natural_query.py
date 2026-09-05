"""Deterministic free-text reduction to one allowlisted location subject."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .errors import ErrorCode, QuestionError


QUESTION_PARSER_ID = "bounded-location-question/1"
TIMELINE_PARSER_ID = "bounded-timeline-question/1"
MAX_QUESTION_CHARACTERS = 200

DEFAULT_ENTITY_ALIASES: Mapping[str, tuple[str, ...]] = {
    "key": ("key", "keys", "鑰匙", "钥匙"),
    "bag": ("bag", "backpack", "包包", "背包"),
    "sofa": ("sofa", "couch", "沙發", "沙发"),
    "wallet": ("wallet", "錢包", "钱包"),
    "remote": ("remote", "remote control", "遙控器", "遥控器"),
    "book": ("book", "書", "书"),
    "drawer": ("drawer", "抽屜", "抽屉"),
    "desk": ("desk", "書桌", "书桌", "桌子"),
    "table": ("table", "茶几", "桌"),
    "shelf": ("shelf", "書架", "书架", "架子"),
}

_ENGLISH_LOCATION_INTENT = re.compile(r"\b(where|locate|find|location)\b")
_CJK_LOCATION_INTENT = ("在哪", "哪裡", "哪里", "位置", "放哪", "找", "看到", "看見", "見過")
_ENGLISH_TIMELINE_INTENT = re.compile(r"\b(when|last seen|last recorded|what time)\b")
_CJK_TIMELINE_INTENT = ("什麼時候", "什么时候", "何時", "何时", "幾秒", "几秒", "最後記錄", "最后记录")
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


def parse_timeline_question(
    question: str,
    *,
    allowed_entity_ids: Iterable[str],
    aliases: Mapping[str, tuple[str, ...]] = DEFAULT_ENTITY_ALIASES,
) -> str:
    """Return one entity for a bounded recorded-time question.

    The answer describes only the timestamp basis embedded in the stored replay.
    It never converts a replay position into a real-world clock time.
    """

    if not isinstance(question, str):
        raise QuestionError("question must be text")
    if any(ord(character) < 32 or ord(character) == 127 for character in question):
        raise QuestionError("question contains control characters")
    normalized = unicodedata.normalize("NFKC", question).strip().lower()
    if not normalized or len(normalized) > MAX_QUESTION_CHARACTERS:
        raise QuestionError("question is empty, overlong, or contains control characters")
    if not (
        _ENGLISH_TIMELINE_INTENT.search(normalized)
        or any(token in normalized for token in _CJK_TIMELINE_INTENT)
    ):
        raise QuestionError(
            "not a bounded replay-time question",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )
    if _ENGLISH_ACTION.search(normalized) or any(
        token in normalized for token in _CJK_ACTION
    ):
        raise QuestionError(
            "action-shaped questions are outside the timeline-query capability",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )
    allowed = tuple(sorted(set(allowed_entity_ids)))
    matches = [
        (position, entity_id)
        for entity_id in allowed
        if (position := _first_position(
            normalized, aliases.get(entity_id, ()) + (entity_id,)
        )) is not None
    ]
    # A relation question normally names both ends, for example "when did the
    # key enter the bag?".  The first mentioned entity is the subject; the
    # result still reports the relation's recorded target from the claim.
    matches.sort()
    if not matches or len(matches) > 2:
        raise QuestionError(
            "question must name exactly one known object",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
            details={"matched_entity_count": len(matches)},
        )
    return matches[0][1]


VERIFICATION_PARSER_ID = "bounded-location-verification/1"

_CJK_VERIFY_INTENT = ("嗎", "吗", "是不是", "在不在", "有沒有", "有没有")
_ENGLISH_VERIFY_INTENT = re.compile(r"\b(is|are|was|were)\b.+\b(at|on|in|inside)\b")
_CJK_SPATIAL = ("在", "上", "裡", "裏", "里", "內", "内")
# "what is in my bag" satisfies is...in, but it asks for contents, not a verdict.
# Answering it as a yes/no about the bag's own location is worse than refusing.
_ENGLISH_WH = re.compile(r"^(what|which|who|whom|whose|where|when|why|how)\b")


@dataclass(frozen=True, slots=True)
class LocationVerification:
    """One subject, and the place the asker proposed for it.

    ``target_id`` is None when the sentence named a place this replay has never
    heard of. That is answerable rather than a rejection: the subject's own
    location is still known, and saying so is more use than refusing.
    """

    subject_id: str
    target_id: str | None


def _first_position(text: str, entity_aliases: tuple[str, ...]) -> int | None:
    positions = [
        text.index(alias.lower())
        for alias in entity_aliases
        if _contains_alias(text, alias.lower())
    ]
    return min(positions) if positions else None


def parse_location_verification(
    question: str,
    *,
    allowed_entity_ids: Iterable[str],
    aliases: Mapping[str, tuple[str, ...]] = DEFAULT_ENTITY_ALIASES,
) -> LocationVerification:
    """Reduce a yes/no location question to one subject and one proposed place.

    Word order decides which is which: the first entity named is the thing being
    asked about. This parser still chooses nothing about the answer -- it only
    names the two ends of a comparison the projection performs.
    """

    if not isinstance(question, str):
        raise QuestionError("question must be text")
    if any(ord(character) < 32 or ord(character) == 127 for character in question):
        raise QuestionError("question contains control characters")
    normalized = unicodedata.normalize("NFKC", question).strip().lower()
    if not normalized or len(normalized) > MAX_QUESTION_CHARACTERS:
        raise QuestionError("question is empty, overlong, or contains control characters")

    # A yes/no marker alone is not enough. "嗎" is a bare question particle, so
    # "沙發好看嗎" would otherwise be routed here and answered as if it asked
    # about a location. A spatial marker has to be present too.
    cjk_verification = any(
        token in normalized for token in _CJK_VERIFY_INTENT
    ) and any(token in normalized for token in _CJK_SPATIAL)
    english_verification = (
        _ENGLISH_VERIFY_INTENT.search(normalized) is not None
        and _ENGLISH_WH.match(normalized) is None
    )
    if not (english_verification or cjk_verification):
        raise QuestionError(
            "not a yes/no location question",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )
    if _ENGLISH_ACTION.search(normalized) or any(
        token in normalized for token in _CJK_ACTION
    ):
        raise QuestionError(
            "action-shaped questions are outside the location-query capability",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )

    ordered: list[tuple[int, str]] = []
    for entity_id in sorted(set(allowed_entity_ids)):
        position = _first_position(normalized, aliases.get(entity_id, ()) + (entity_id,))
        if position is not None:
            ordered.append((position, entity_id))
    ordered.sort()

    if not ordered:
        raise QuestionError(
            "question names nothing this replay knows about",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
            details={"matched_entity_count": 0},
        )
    if len(ordered) > 2:
        raise QuestionError(
            "question names more than two known objects",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
            details={"matched_entity_count": len(ordered)},
        )
    subject_id = ordered[0][1]
    target_id = ordered[1][1] if len(ordered) == 2 else None
    return LocationVerification(subject_id=subject_id, target_id=target_id)


CONTENTS_PARSER_ID = "bounded-container-contents/1"

_CJK_CONTENTS_INTENT = (
    "有什麼", "有什么", "有哪些", "裝了什麼", "装了什么", "放了什麼", "放了什么",
)
_ENGLISH_CONTENTS_INTENT = re.compile(
    r"^what(?:'s| is| are)?\b.*\b(in|inside|contain|contains)\b"
)


def parse_container_question(
    question: str,
    *,
    allowed_entity_ids: Iterable[str],
    aliases: Mapping[str, tuple[str, ...]] = DEFAULT_ENTITY_ALIASES,
) -> str:
    """Return the one container whose contents were asked for.

    This is the reverse of :func:`parse_location_question`. The projection already
    holds the containment edge in both directions; only the question surface was
    one-way.
    """

    if not isinstance(question, str):
        raise QuestionError("question must be text")
    if any(ord(character) < 32 or ord(character) == 127 for character in question):
        raise QuestionError("question contains control characters")
    normalized = unicodedata.normalize("NFKC", question).strip().lower()
    if not normalized or len(normalized) > MAX_QUESTION_CHARACTERS:
        raise QuestionError("question is empty, overlong, or contains control characters")

    if not (
        _ENGLISH_CONTENTS_INTENT.search(normalized)
        or any(token in normalized for token in _CJK_CONTENTS_INTENT)
    ):
        raise QuestionError(
            "not a container-contents question",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )
    if _ENGLISH_ACTION.search(normalized) or any(
        token in normalized for token in _CJK_ACTION
    ):
        raise QuestionError(
            "action-shaped questions are outside the location-query capability",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )

    matches = [
        entity_id
        for entity_id in sorted(set(allowed_entity_ids))
        if _first_position(normalized, aliases.get(entity_id, ()) + (entity_id,))
        is not None
    ]
    if len(matches) != 1:
        raise QuestionError(
            "question must name exactly one known container",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
            details={"matched_entity_count": len(matches)},
        )
    return matches[0]
