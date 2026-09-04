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

from .adapters.loopback_llm import (
    translator_from_environment,
    verbalizer_from_environment,
)
from .adapters.sqlite_archive import SQLiteReplayArchive
from .errors import B0Error
from .memory_query import answer_question, list_known_entities

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"
DEFAULT_DATABASE = Path(".whole-home-agent/demo-memory.sqlite3")
MAX_QUESTION_BYTES = 4096


class Handler(SimpleHTTPRequestHandler):
    database: Path

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

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

        try:
            result = answer_question(
                SQLiteReplayArchive(self.database),
                question,
                verbalizer=verbalizer_from_environment(),
                translator=translator_from_environment(),
            )
        except B0Error as error:
            # A refusal is an answer here: the page shows it as speech, so the
            # character says it rather than the page rendering an error box.
            self._json(
                200,
                {
                    "refused": True,
                    "text": str(error),
                    "details": getattr(error, "details", None) or {},
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
