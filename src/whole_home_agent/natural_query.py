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

# The replay fixtures name these, and a question is read against whichever of
# them the archive actually holds.
_FIXTURE_ALIASES: Mapping[str, tuple[str, ...]] = {
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

# What the camera can put into the archive on its own. The detector reports the
# eighty COCO classes, PerceptionBridge maps fifteen of them onto household names
# and lets the rest through under their own label, so an entity like "person" or
# "frisbee" reached the memory while the only way to ask after it was to type its
# English label -- which is what a question in Chinese kept missing.
#
# Every id here is one the bridge can commit: the values of its COCO_TO_ENTITY_MAP
# plus the slug each remaining class falls back to. A test checks that mapping's
# outputs against this table, so a class added on the detector side cannot quietly
# become unaskable again.
_DETECTOR_ALIASES: Mapping[str, tuple[str, ...]] = {
    "person": ("person", "people", "人", "人影"),
    "bicycle": ("bicycle", "bike", "腳踏車", "脚踏车", "單車", "自行車"),
    "car": ("car", "汽車", "汽车", "轎車"),
    "motorcycle": ("motorcycle", "機車", "机车", "摩托車"),
    "airplane": ("airplane", "飛機", "飞机"),
    "bus": ("bus", "公車", "公车", "巴士"),
    "train": ("train", "火車", "火车"),
    "truck": ("truck", "卡車", "卡车", "貨車"),
    "boat": ("boat", "船"),
    "traffic_light": ("traffic light", "紅綠燈", "红绿灯", "號誌燈"),
    "fire_hydrant": ("fire hydrant", "消防栓"),
    "stop_sign": ("stop sign", "停車標誌", "停止標誌"),
    "parking_meter": ("parking meter", "停車計時器"),
    "bench": ("bench", "長椅", "长椅", "板凳"),
    "bird": ("bird", "鳥", "鸟"),
    "cat": ("cat", "貓", "猫", "貓咪"),
    "dog": ("dog", "狗", "狗狗", "小狗"),
    "horse": ("horse", "馬", "马"),
    "sheep": ("sheep", "羊", "綿羊"),
    "cow": ("cow", "牛", "乳牛"),
    "elephant": ("elephant", "大象"),
    "bear": ("bear", "熊"),
    "zebra": ("zebra", "斑馬", "斑马"),
    "giraffe": ("giraffe", "長頸鹿", "长颈鹿"),
    "umbrella": ("umbrella", "雨傘", "雨伞", "傘"),
    "tie": ("tie", "necktie", "領帶", "领带"),
    "suitcase": ("suitcase", "行李箱", "行李"),
    "frisbee": ("frisbee", "飛盤", "飞盘"),
    "skis": ("skis", "ski", "滑雪板", "雪橇"),
    "snowboard": ("snowboard", "單板滑雪板"),
    "sports_ball": ("sports ball", "球", "皮球"),
    "kite": ("kite", "風箏", "风筝"),
    "baseball_bat": ("baseball bat", "球棒", "棒球棒"),
    "baseball_glove": ("baseball glove", "棒球手套"),
    "skateboard": ("skateboard", "滑板"),
    "surfboard": ("surfboard", "衝浪板", "冲浪板"),
    "tennis_racket": ("tennis racket", "網球拍", "网球拍", "球拍"),
    "bottle": ("bottle", "瓶子", "水瓶", "寶特瓶"),
    "wine_glass": ("wine glass", "酒杯", "紅酒杯", "高腳杯"),
    "cup": ("cup", "杯子", "馬克杯", "水杯"),
    "fork": ("fork", "叉子"),
    "knife": ("knife", "刀子", "菜刀"),
    "spoon": ("spoon", "湯匙", "汤匙", "調羹"),
    "bowl": ("bowl", "碗"),
    "banana": ("banana", "香蕉"),
    "apple": ("apple", "蘋果", "苹果"),
    "sandwich": ("sandwich", "三明治"),
    "orange": ("orange", "柳橙", "橘子"),
    "broccoli": ("broccoli", "花椰菜", "西蘭花"),
    "carrot": ("carrot", "紅蘿蔔", "胡蘿蔔"),
    "hot_dog": ("hot dog", "熱狗", "热狗"),
    "pizza": ("pizza", "披薩", "比薩"),
    "donut": ("donut", "甜甜圈"),
    "cake": ("cake", "蛋糕"),
    "chair": ("chair", "椅子", "椅"),
    "potted_plant": ("potted plant", "盆栽", "盆景"),
    "bed": ("bed", "床", "床鋪"),
    "toilet": ("toilet", "馬桶", "马桶"),
    "tv": ("tv", "television", "電視", "电视", "電視機"),
    "laptop": ("laptop", "筆電", "笔电", "筆記型電腦", "電腦"),
    "mouse": ("mouse", "滑鼠", "鼠標"),
    "keyboard": ("keyboard", "鍵盤", "键盘"),
    "phone": ("phone", "cell phone", "mobile", "手機", "手机", "電話"),
    "microwave": ("microwave", "微波爐", "微波炉"),
    "oven": ("oven", "烤箱", "烤爐"),
    "toaster": ("toaster", "烤麵包機", "吐司機"),
    "sink": ("sink", "水槽", "洗手台"),
    "refrigerator": ("refrigerator", "fridge", "冰箱"),
    "clock": ("clock", "時鐘", "时钟", "鐘"),
    "vase": ("vase", "花瓶"),
    "scissors": ("scissors", "剪刀"),
    "teddy_bear": ("teddy bear", "泰迪熊", "玩具熊"),
    "hair_drier": ("hair drier", "hair dryer", "吹風機", "吹风机"),
    "toothbrush": ("toothbrush", "牙刷"),
}

DEFAULT_ENTITY_ALIASES: Mapping[str, tuple[str, ...]] = {
    **_DETECTOR_ALIASES,
    # The fixture wording wins where both name the same id, because those are the
    # objects the written replays are about.
    **_FIXTURE_ALIASES,
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


def _named_entities(
    text: str,
    allowed: Iterable[str],
    aliases: Mapping[str, tuple[str, ...]],
) -> dict[str, str]:
    """Every entity the text names, each with the longest alias that matched it.

    Chinese has no spaces, so an alias is found by substring, and shorter
    household words live inside longer ones: 書 inside 書桌 and 書架, 桌 inside
    both of those again. Asking where the desk was therefore named three objects
    at once and was refused for being ambiguous, which it never was to a reader.
    Keeping the longest reading of each overlap is what a reader does without
    noticing, and it is what lets this table hold a detector's whole vocabulary
    -- 狗 sits inside 熱狗 the same way -- rather than only a curated ten.

    Entities named by genuinely different words still all come back. Two objects
    in one question is real ambiguity, and refusing it stays the caller's job.
    """

    named: dict[str, str] = {}
    for entity_id in allowed:
        matched = [
            alias
            for alias in (*aliases.get(entity_id, ()), entity_id)
            if _contains_alias(text, alias.lower())
        ]
        if matched:
            named[entity_id] = max(matched, key=len)

    words = set(named.values())
    return {
        entity_id: alias
        for entity_id, alias in named.items()
        if not any(alias != other and alias in other for other in words)
    }


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
    matches = sorted(_named_entities(normalized, allowed, aliases))
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
    # Positions come from the alias that actually named each entity, so a word
    # that only appeared inside a longer one cannot claim that longer one's
    # position and be read as the subject.
    matches = sorted(
        (normalized.find(alias.lower()), entity_id)
        for entity_id, alias in _named_entities(normalized, allowed, aliases).items()
    )
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

    ordered = sorted(
        (normalized.find(alias.lower()), entity_id)
        for entity_id, alias in _named_entities(
            normalized, sorted(set(allowed_entity_ids)), aliases
        ).items()
    )

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

    matches = sorted(
        _named_entities(normalized, sorted(set(allowed_entity_ids)), aliases)
    )
    if len(matches) != 1:
        raise QuestionError(
            "question must name exactly one known container",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
            details={"matched_entity_count": len(matches)},
        )
    return matches[0]
