"""Bounded OpenAI-compatible presenter for a loopback-hosted language model."""

from __future__ import annotations

import ipaddress
import json
import re
from collections.abc import Mapping
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from whole_home_agent.errors import PresenterConfigError
from whole_home_agent.serialization import canonical_json


LOOPBACK_PRESENTER_ID = "loopback-chat-completions/1"
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
        raise PresenterConfigError("local LLM endpoint must use a literal loopback IP") from error
    if not address.is_loopback:
        raise PresenterConfigError("remote LLM endpoints remain disabled")
    return endpoint


class LoopbackChatPresenter:
    """Send only minimized context to an explicitly selected local API.

    The adapter has no memory, query, evidence, policy, or action handle.  It makes one
    bounded request, performs no retry, and treats the returned prose as untrusted.
    """

    presenter_id = LOOPBACK_PRESENTER_ID

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        authorization_value: str | None = None,
        timeout_seconds: float = 8.0,
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
        if not isinstance(timeout_seconds, (int, float)) or not 0.1 <= timeout_seconds <= 30:
            raise PresenterConfigError("local LLM timeout must be between 0.1 and 30 seconds")
        self._model = model
        self._authorization_value = authorization_value
        self._timeout_seconds = float(timeout_seconds)

    def present(self, context: Mapping[str, object]) -> str:
        body = canonical_json(
            {
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Verbalize only the supplied structured location answer in "
                            "concise Traditional Chinese. Preserve uncertainty. Do not add "
                            "events, locations, actions, or facts. Return plain text only."
                        ),
                    },
                    {"role": "user", "content": canonical_json(context)},
                ],
                "temperature": 0,
                "max_tokens": 180,
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
        return content
