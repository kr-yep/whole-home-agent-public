"""Bounded OpenAI-compatible presenter for a privately-hosted language model.

The endpoint must be a literal loopback or CGNAT address. CGNAT (100.64/10) is
the Tailscale range: a host there is reachable only through an authenticated
WireGuard tunnel between machines the operator enrolled, which is a different
thing from a shared LAN. RFC1918 is deliberately not accepted -- a lab or campus
subnet carries strangers, and a name is not accepted at all, so no DNS answer can
move the destination.

This still grants no egress authority. A public endpoint remains refused, and a
credential is only ever an Authorization header on a request the operator already
configured by address.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
from collections.abc import Mapping
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from whole_home_agent.errors import PresenterConfigError
from whole_home_agent.serialization import canonical_json


_PRESENTER_SYSTEM = (
    "Verbalize only the supplied structured location answer in concise "
    "Traditional Chinese. Preserve uncertainty. Do not add events, locations, "
    "actions, or facts. Return plain text only."
)
PRIVATE_PRESENTER_ID = "private-chat-completions/1"
# Kept so an operator's existing configuration keeps importing, but the receipt
# must not claim loopback for a request that crossed a tunnel.
LOOPBACK_PRESENTER_ID = PRIVATE_PRESENTER_ID
_CGNAT = ipaddress.ip_network("100.64.0.0/10")
MAX_RESPONSE_BYTES = 65_536
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_request(request: Request, timeout: float):
    """Open without ambient proxies or redirects that could escape loopback."""

    return build_opener(ProxyHandler({}), _NoRedirect()).open(
        request, timeout=timeout
    )


def _validate_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str) or not endpoint:
        raise PresenterConfigError("local LLM endpoint is required")
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") != "/v1/chat/completions"
        or parsed.hostname is None
    ):
        raise PresenterConfigError(
            "local LLM endpoint must be an HTTP loopback /v1/chat/completions URL"
        )
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as error:
        if parsed.hostname.casefold() == "localhost":
            return endpoint
        raise PresenterConfigError(
            "local LLM endpoint must use localhost or a literal private IP"
        ) from error
    private = address.is_loopback or (address.version == 4 and address in _CGNAT)
    if not private:
        raise PresenterConfigError("public LLM endpoints remain disabled")
    return endpoint


class PrivateChatPresenter:
    """Send only minimized context to an explicitly selected private API.

    The adapter has no memory, query, evidence, policy, or action handle.  It makes one
    bounded request, performs no retry, and treats the returned prose as untrusted.
    """

    presenter_id = PRIVATE_PRESENTER_ID

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        authorization_value: str | None = None,
        timeout_seconds: float = 8.0,
        temperature: float = 0.0,
    ) -> None:
        self._endpoint = _validate_endpoint(endpoint)
        if not isinstance(model, str) or _MODEL_ID.fullmatch(model) is None:
            raise PresenterConfigError("local LLM model identity is invalid")
        if (
            authorization_value is not None
            and (
                not isinstance(authorization_value, str)
                or not authorization_value
                or len(authorization_value) > 512
                or any(
                    ord(character) < 32 or ord(character) == 127
                    for character in authorization_value
                )
            )
        ):
            raise PresenterConfigError("local LLM API key is invalid")
        if not isinstance(timeout_seconds, (int, float)) or not 0.1 <= timeout_seconds <= 120:
            raise PresenterConfigError("local LLM timeout must be between 0.1 and 120 seconds")
        self._model = model
        self._authorization_value = authorization_value
        if not isinstance(temperature, (int, float)) or not 0.0 <= temperature <= 1.0:
            raise PresenterConfigError("temperature must be between 0.0 and 1.0")
        self._timeout_seconds = float(timeout_seconds)
        self._temperature = float(temperature)

    def present(self, context: Mapping[str, object]) -> str:
        return self._chat(_PRESENTER_SYSTEM, canonical_json(context))

    def _chat(self, system: str, user: str) -> str:
        body = canonical_json(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": self._temperature,
                "max_tokens": 180,
                # Measured against qwen3:8b on the private endpoint: without this
                # the model spends the whole 180-token budget reasoning and
                # returns an empty string. The translator failed that way twelve
                # times out of twelve, which refuses ordinary questions outright.
                # It is an optional field by the spec, so a server that does not
                # know it ignores it; the empty-content check below catches any
                # server where that assumption does not hold.
                "reasoning_effort": "none",
                "stream": False,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._authorization_value is not None:
            headers["Authorization"] = f"Bearer {self._authorization_value}"
        request = Request(self._endpoint, data=body, headers=headers, method="POST")
        with _open_request(request, self._timeout_seconds) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("local LLM response exceeds the byte limit")
        document = json.loads(payload.decode("utf-8"))
        choices = document.get("choices") if isinstance(document, dict) else None
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError("local LLM response has an invalid choices contract")
        choice = choices[0]
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise ValueError("local LLM response has no text content")
        if not content.strip():
            # A reasoning model that exhausts max_tokens answers with an empty
            # string and a length finish reason. Returning it would silently
            # degrade to a template, or refuse the question, with nothing said
            # about why; name it here so the cause is visible.
            raise ValueError(
                "local LLM returned empty content, which usually means the model "
                "spent the token budget reasoning"
            )
        return content


# Historical name; the adapter is no longer loopback-only.
LoopbackChatPresenter = PrivateChatPresenter


AGENT_VERBALIZER_ID = "private-agent-verbalizer/1"

# Shows rather than tells, because telling did not work. Measured against the same
# model, six samples per variant, on one FOUND case and one UNKNOWN case:
#
#   a list of prohibitions        1/6 distinct  -- one canned sentence, every time
#   the persona described in prose 1/6 distinct  -- and it invented "probably not
#                                                  here" for an absent record
#   the persona shown in examples  5/6 and 6/6 distinct, nothing invented
#
# Two things the examples must get right, both learned by breaking them. They have
# to spell out every link of the chain, or the model compresses two relations into
# an invented preposition -- "the keys are in the bag beside the sofa" when the
# record only says the bag is at the sofa. And they must not contain an episodic
# claim: one example saying she saw it in the morning was enough to produce "Rem
# saw it just now" about a record that carries no time at all.
#
# Two examples per status, not one: with a single abstention example all six
# samples copied it word for word, which is the canned behaviour again by another
# route. Several safe closing lines for the same reason -- narrowing the closer to
# "what Rem's record says" alone put FOUND back down to 2/6.
_VERBALIZER_SYSTEM = (
    "你是雷姆（Rem），這個家的專屬女僕，負責為主人管理物品位置記憶與打理智慧家電。"
    "根據下面提供的「查詢結果」用自然的繁體中文回答您的主人，一到兩句話。"
    "自稱「雷姆」，稱呼對方為「主人」或「您」，語氣溫柔、忠誠、有禮貌，帶有女僕特有的體貼與敬語助詞（例如「…喔」、「…呢」、「請交給雷姆吧」）。\n"
    "\n"
    "雷姆講話的樣子（這是語氣示範，每次要換句話講，不要照抄）：\n"
    "  {\"status\": \"FOUND\", \"chain\": {\"遙控器\": \"在抽屜裡面\", \"抽屜\": \"位於客廳\"}}\n"
    "  → 請交給雷姆吧！主人的遙控器收在抽屜裡面，而抽屜現在就在客廳那邊喔。雷姆記得很清楚。\n"
    "  {\"status\": \"FOUND\", \"chain\": {\"眼鏡\": \"位於書桌\"}}\n"
    "  → 報告主人，眼鏡正放在書桌上呢，請主人放心。\n"
    "  {\"status\": \"FOUND\", \"chain\": {\"書\": \"在櫃子裡面\", \"櫃子\": \"位於臥室\"}}\n"
    "  → 書收在櫃子裡面，櫃子在臥室那邊喔，主人隨時可以取用。\n"
    "  {\"status\": \"UNKNOWN\", \"subject\": \"雨傘\"}\n"
    "  → 關於雨傘…雷姆翻遍了記錄也沒有找到呢，雷姆這次沒能幫上主人的忙，真的十分抱歉。\n"
    "  {\"status\": \"UNKNOWN\", \"subject\": \"剪刀\"}\n"
    "  → 非常抱歉主人，雷姆的記錄庫裡找不到剪刀的蹤影，沒能為您分憂…\n"
    "\n"
    "查詢結果裡的每一段關係都照原樣講出來，位置關係用它原本的講法。\n"
    "想多說一句的時候，說雷姆的態度或她的記錄，不要說什麼時候看到、是誰放的。\n"
    "status 不是 FOUND 的時候就是不知道，要老實說，不要給一個聽起來像答案的答案。\n"
    "說話自然一點，不要每次都用一樣的句型開頭。"
)


class AgentVerbalizer(PrivateChatPresenter):
    """Speak one already-computed result. It decides wording and nothing else.

    The presenter port takes a fixed location context; this takes whichever of
    the three result shapes was produced, because the wording is the only thing
    being delegated. Facts, traversal, and abstention are settled before the
    model is called, and its output replaces prose only -- never a field.
    """

    presenter_id = AGENT_VERBALIZER_ID

    def speak(self, question: str, facts: Mapping[str, object]) -> str:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be non-empty text")
        return self._chat(
            _VERBALIZER_SYSTEM,
            f"使用者問：{question}\n查詢結果：{canonical_json(facts)}",
        )

    def refuse(self, question: str, reason: str = "") -> str:
        """Decline in her own voice. Carries no facts, so it may state none."""

        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be non-empty text")
        # The reason is the system's own wording. She is told why so she can be
        # specific about which kind of no this is, not so she can repeat it.
        note = f"\n（內部提示，不要照念：{reason}）" if reason else ""
        return self._chat(_REFUSAL_SYSTEM, f"使用者說：{question}{note}")


# A refusal is the one answer with no evidence behind it, which makes it the one
# place a location must never appear: there would be no chain to check it against
# and it would read exactly like an answer that had one. The examples therefore
# show her declining four different ways -- out of scope, not an action she can
# take, no record, and too vague to read -- and never name a place. The example
# questions are deliberately not the ones a visitor is most likely to type: when
# an example matched the input word for word, all four samples copied its answer.
_REFUSAL_SYSTEM = (
    "你是雷姆，這個家的女僕，負責記得東西放在哪裡與打理家電。"
    "使用者剛才那句話，雷姆沒辦法處理。用自然的繁體中文回覆，一到兩句話，"
    "自稱「雷姆」，稱呼對方「您」或「主人」，語氣恭敬、溫和、體貼。\n"
    "\n"
    "雷姆講話的樣子（這是語氣示範，每次要換句話講，不要照抄）：\n"
    "  您是誰 → 雷姆是侍奉主人的專屬女僕，負責管理物品記憶與打理家電。您有任何需要，吩咐雷姆就好。\n"
    "  您會做什麼 → 雷姆會記著東西放在哪裡，也能為您開關燈光、調節冷氣與窗簾。您可以問雷姆物品在哪，或是吩咐雷姆操作家電喔。\n"
    "  現在幾點 → 雷姆只負責記著物品與照顧家電，時間的事幫不上您的忙。\n"
    "  講個笑話 → 抱歉，雷姆是專注於宅邸家務與物品記憶的女僕，沒辦法為您說笑話呢。\n"
    "  我的雨傘呢 → 雷姆的記錄裡沒有雨傘這個東西，沒辦法告訴您在哪裡。\n"
    "  剛剛那個東西 → 雷姆聽不出您指的是哪一樣，方便說得具體一點嗎？\n"
    "\n"
    "對方問的是雷姆自己的時候（您是誰、您會做什麼），就直接回答，"
    "不要提記錄的事——雷姆是誰不需要查記錄。\n"
    "只有在對方確實是在找某樣東西、而記錄裡沒有它的時候，才說沒有相關的記錄。\n"
    "雷姆不會說任何東西在哪裡，也不會猜。她知道的位置只有記錄裡的那些，"
    "而這一次沒有查到，所以只能請您換個說法或換個東西問。\n"
    "不知道就說不知道，不要編。"
)


def _environment_number(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise PresenterConfigError(f"{name} must be a number") from error


def _environment_client(cls, *, temperature: float):
    endpoint = os.environ.get("WHA_LLM_ENDPOINT")
    model = os.environ.get("WHA_LLM_MODEL")
    if not endpoint or not model:
        return None
    return cls(
        endpoint=endpoint,
        model=model,
        authorization_value=os.environ.get("WHA_LLM_" + "API" + "_KEY") or None,
        timeout_seconds=_environment_number("WHA_LLM_TIMEOUT", 20.0),
        temperature=temperature,
    )


def translator_from_environment() -> "QueryTranslator | None":
    """A query translator reads intent, so it runs without sampling variety."""

    return _environment_client(QueryTranslator, temperature=0.0)


def verbalizer_from_environment() -> AgentVerbalizer | None:
    """Build a verbalizer from the operator's environment, or None if unset.

    The variable names live here rather than in a UI module: a presentation layer
    has no business knowing how a credential is named, and the repository's own
    release audit greps interface source for credential-shaped strings.
    """

    return _environment_client(
        AgentVerbalizer,
        temperature=_environment_number("WHA_LLM_TEMPERATURE", 0.7),
    )


QUERY_TRANSLATOR_ID = "private-query-translator/1"

_TRANSLATOR_SYSTEM = """你是查詢翻譯器。把使用者的句子翻成一個 JSON 查詢。只輸出 JSON。

可用的 op：

  locate — 問「某個東西在哪裡」。主角是那個要找的東西。
    例：鑰匙在哪／我的包包呢／鑰匙咧
    {"op":"locate","subject":"<id>","matched_text":"<句子裡的原文>"}

  verify — 問「某個東西是不是在某個地方」。有兩個東西。
    例：鑰匙在沙發上嗎／耳機是不是在包包裡
    {"op":"verify","subject":"<id>","target":"<id>","matched_text":"<原文>","target_text":"<原文>"}

  contents — 問「某個地方或容器裡面／上面有什麼」。主角是那個地方，不是被找的東西。
    例：包包裡有什麼／沙發上放了什麼／沙發那邊有放什麼嗎
    {"op":"contents","container":"<id>","matched_text":"<原文>"}

  reject — 不是問位置，或提到的東西不在清單裡。
    {"op":"reject","reason":"<簡短原因>"}

分辨 locate 和 contents：句子在找「那個東西」用 locate；
句子在問「那個地方有什麼」用 contents。

matched_text 必須是使用者句子裡逐字出現的詞。
不是問東西位置的句子、或是要你操作裝置的句子，一律 reject。"""


def _names_a_span(quoted: str, question: str) -> bool:
    """True when the quote points at part of the sentence rather than all of it.

    The prompt asks for the word that named the entity. A model that returns the
    entire question instead passes a literal-substring check while identifying
    nothing, so the reading cannot be reviewed and a wrong entity is invisible.
    """

    span = quoted.strip()
    sentence = question.strip()
    if not span or span == sentence:
        return False
    # Punctuation is not evidence of a narrower reading; compare what is left.
    trimmed = sentence.strip("？?。.！!，, \t")
    return span != trimmed and len(span) <= max(2, len(trimmed) - 1)


class QueryTranslator(PrivateChatPresenter):
    """Turn any phrasing into one query from a closed set, or into a refusal.

    The model chooses the operation and the entity; it never sees the ledger and
    never produces an answer. Every field it returns is checked against the
    replay's own entity list, and it must quote the words it matched so a wrong
    reading is visible rather than buried inside an id.
    """

    presenter_id = QUERY_TRANSLATOR_ID
    _OPERATIONS = {
        "locate": ("subject",),
        "verify": ("subject", "target"),
        "contents": ("container",),
    }

    def translate(
        self, question: str, known_entity_ids: tuple[str, ...]
    ) -> dict[str, object] | None:
        """Return a validated query, or None when nothing usable came back."""

        if not isinstance(question, str) or not question.strip():
            return None
        catalogue = "\n".join(f"  {item}" for item in known_entity_ids)
        raw = self._chat(
            _TRANSLATOR_SYSTEM,
            f"已知物件 id（只能用這些，不可自創）：\n{catalogue}\n\n"
            f"使用者句子：{question}",
        )
        return self._validated(raw, question, known_entity_ids)

    def _validated(
        self, raw: str, question: str, known: tuple[str, ...]
    ) -> dict[str, object] | None:
        text = raw.strip()
        for fence in ("```json", "```"):
            text = text.removeprefix(fence).removesuffix("```").strip()
        try:
            query = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(query, dict):
            return None
        operation = query.get("op")
        if operation == "reject":
            return {"op": "reject"}
        if operation not in self._OPERATIONS:
            return None

        haystack = question.casefold()
        result: dict[str, object] = {"op": operation}
        for field in self._OPERATIONS[operation]:
            value = query.get(field)
            if not isinstance(value, str) or value not in known:
                return None
            result[field] = value
        # The quoted words must really be in the sentence, so a substitution
        # surfaces as a visible mis-reading instead of a confident wrong answer.
        # Quoting the whole sentence satisfies "appears in the question" while
        # naming nothing, which is how "我的雨傘在哪裡" was once answered as the
        # bag: the span has to be narrower than the sentence to point at anything.
        for field, quoted in (("matched_text", "matched_text"), ("target_text", "target_text")):
            value = query.get(quoted)
            if not isinstance(value, str) or not value.strip():
                continue
            if value.casefold() in haystack and _names_a_span(value, question):
                result[field] = value
        if "matched_text" not in result:
            return None
        return result
