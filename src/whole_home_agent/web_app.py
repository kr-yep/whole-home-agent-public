"""Static-file and JSON entry point for the character front end.

The Streamlit page and this one answer with the same use case; only the surface
differs. Everything below is presentation: it holds a read-only archive handle
and calls one function, so nothing here can admit a claim or widen a scope.

Standard library only, matching the rest of the package.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .actuation.dispatcher import CommandDispatcher
from .actuation.models import ActionStatus
from .actuation.port import ActuatorPort
from .adapters.mock_actuator import MockActuator
from .adapters.loopback_llm import (
    translator_from_environment,
    verbalizer_from_environment,
)
from .adapters.sqlite_archive import SQLiteReplayArchive
from .errors import B0Error
from .memory_query import answer_question, list_known_entities

from .rem_persona import (
    RemLocationPresenter,
    rem_voice_actuation,
    rem_voice_contents,
    rem_voice_refusal,
    rem_voice_verification,
)

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"
DEFAULT_DATABASE = Path(".whole-home-agent/demo-memory.sqlite3")
MAX_QUESTION_BYTES = 4096


def _voiced_refusal(verbalizer: object | None, question: str, message: str) -> str:
    """Let her say the refusal in her own words, or fall back to the system's.

    The refusal itself was decided before either could speak, so nothing here can
    change whether the answer is a refusal -- only how it sounds. Any failure at
    all keeps the original wording, because a refusal that does not arrive is
    worse than one that arrives blunt.
    """

    if verbalizer is None:
        return message
    try:
        voiced = verbalizer.refuse(question, message)
    except Exception:
        return message
    return voiced.strip() if isinstance(voiced, str) and voiced.strip() else message


class Handler(SimpleHTTPRequestHandler):
    database: Path = DEFAULT_DATABASE
    actuator: ActuatorPort = MockActuator()
    dispatcher: CommandDispatcher = CommandDispatcher(actuator)
    presenter: LocationPresenter = RemLocationPresenter()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def end_headers(self) -> None:
        # SimpleHTTPRequestHandler sends Last-Modified and nothing else, which
        # lets a browser apply heuristic caching and serve a stale stylesheet
        # without asking. That cost an afternoon of looking at a fixed layout
        # that had not reached the page. This is a demo server; always revalidate.
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/entities":
            try:
                archive = SQLiteReplayArchive(self.database)
                self._json(200, {"entities": list(list_known_entities(archive))})
            except B0Error as error:
                self._json(200, {"entities": [], "error": str(error)})
            return
        if self.path == "/api/devices":
            self._json(200, {"devices": [d.as_dict() for d in self.actuator.list_devices()]})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/ask":
            self._json(404, {"error": "no such route"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_QUESTION_BYTES:
            self._json(413, {"error": "question size unsupported"})
            return
        try:
            question = json.loads(self.rfile.read(length)).get("question")
        except json.JSONDecodeError:
            self._json(400, {"error": "body must be JSON"})
            return
        if not isinstance(question, str) or not question.strip():
            self._json(400, {"error": "question must be non-empty text"})
            return

        verbalizer = verbalizer_from_environment()

        # 1. Dispatch device actuation commands
        action_receipt = self.dispatcher.dispatch(question)
        if action_receipt is not None:
            voiced_actuation = rem_voice_actuation(action_receipt)
            if action_receipt.status == ActionStatus.DENIED:
                self._json(
                    200,
                    {
                        "refused": True,
                        "text": _voiced_refusal(verbalizer, question, voiced_actuation),
                        "reason": action_receipt.message,
                        "details": action_receipt.as_dict(),
                        "action_receipt": action_receipt.as_dict(),
                    },
                )
            else:
                self._json(
                    200,
                    {
                        "refused": False,
                        "action_receipt": action_receipt.as_dict(),
                        "spoken": {
                            "text": voiced_actuation,
                            "speaker": "actuator",
                            "fallback_used": False,
                        },
                        "text": voiced_actuation,
                    },
                )
            return

        # 2. Dispatch memory location questions
        try:
            result = answer_question(
                SQLiteReplayArchive(self.database),
                question,
                presenter=self.presenter,
                verbalizer=verbalizer,
                translator=translator_from_environment(),
            )
            # Polish container or verification spoken text with Rem persona if verbalizer is not active
            if verbalizer is None:
                if result.get("contents"):
                    result["spoken"] = {
                        "text": rem_voice_contents(result["contents"]),
                        "speaker": self.presenter.presenter_id,
                        "fallback_used": False,
                    }
                elif result.get("verification"):
                    result["spoken"] = {
                        "text": rem_voice_verification(result["verification"], result.get("answer", {})),
                        "speaker": self.presenter.presenter_id,
                        "fallback_used": False,
                    }
        except B0Error as error:
            details = getattr(error, "details", None) or {}
            refusal_text = rem_voice_refusal(question, str(error), details)
            self._json(
                200,
                {
                    "refused": True,
                    "text": _voiced_refusal(verbalizer, question, refusal_text),
                    "reason": str(error),
                    "details": details,
                },
            )
            return
        self._json(200, result)


def main() -> None:
    parser = argparse.ArgumentParser(prog="whole-home-agent-web")
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8600)
    arguments = parser.parse_args()

    mimetypes.add_type("application/json", ".json")
    mimetypes.add_type("application/octet-stream", ".moc3")
    Handler.database = arguments.db
    server = ThreadingHTTPServer((arguments.bind, arguments.port), Handler)
    print(f"serving {WEB_ROOT} on http://{arguments.bind}:{arguments.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
