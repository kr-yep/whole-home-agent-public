"""Persistent D0 replay, bounded language query, and loopback presenter tests."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from whole_home_agent.adapters.loopback_llm import (
    LOOPBACK_PRESENTER_ID,
    LoopbackChatPresenter,
)
from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
from whole_home_agent.cli import main as cli_main
from whole_home_agent.errors import ArchiveError, ErrorCode, PresenterConfigError, QuestionError
from whole_home_agent.fixture import load_fixture
from whole_home_agent.memory_query import answer_latest_memory
from whole_home_agent.natural_query import parse_location_question
from whole_home_agent.orchestrator import run_fixture
from whole_home_agent.presentation import PRESENTED, present_location_context


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "fixtures" / "b0_key_bag_sofa_v1.json"
HAS_VIDEO = importlib.util.find_spec("av") is not None and importlib.util.find_spec(
    "numpy"
) is not None
HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None


def _session(run_id: str = "archive-test"):
    return run_fixture(load_fixture(FIXTURE), replay_run_id=run_id)


def _context():
    return {
        "schema": "whole-home-agent.location-context.v1",
        "purpose": "verbalize_location_answer",
        "answer": {
            "subject_id": "key",
            "status": "FOUND",
            "location_id": "sofa",
            "epistemic_status": "estimated",
        },
        "relation_facts": [
            {
                "subject_id": "key",
                "predicate": "inside",
                "object_id": "bag",
                "epistemic_status": "estimated",
            },
            {
                "subject_id": "bag",
                "predicate": "at_zone",
                "object_id": "sofa",
                "epistemic_status": "estimated",
            },
        ],
    }


class _Response:
    def __init__(self, payload: object):
        self._payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit: int):
        return self._payload


class SQLiteReplayArchiveTests(unittest.TestCase):
    def test_restart_rebuild_and_idempotent_write_preserve_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            session = _session()
            first = SQLiteReplayArchive(path).save_completed(session)
            second = SQLiteReplayArchive(path).save_completed(session)
            restored = SQLiteReplayArchive(path).load_latest()

        self.assertEqual(first.status, "INSERTED")
        self.assertEqual(second.status, "UNCHANGED")
        self.assertEqual(restored.semantic_output, session.semantic_output)
        self.assertEqual(restored.canonical_hash, session.canonical_hash)
        self.assertEqual(restored.accepted_claims, session.accepted_claims)

    def test_missing_read_does_not_create_a_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "memory.sqlite3"
            with self.assertRaises(ArchiveError) as caught:
                SQLiteReplayArchive(path).load_latest()
            self.assertEqual(caught.exception.error_code, ErrorCode.ARCHIVE_NOT_FOUND)
            self.assertFalse(path.exists())
            self.assertFalse(path.parent.exists())

    def test_tampered_payload_fails_before_query(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            SQLiteReplayArchive(path).save_completed(_session())
            connection = sqlite3.connect(path)
            connection.execute(
                "UPDATE replay_sessions SET payload_json = payload_json || 'x'"
            )
            connection.commit()
            connection.close()
            with self.assertRaises(ArchiveError):
                SQLiteReplayArchive(path).load_latest()

    def test_same_archive_identity_with_different_payload_hash_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            session = _session()
            archive = SQLiteReplayArchive(path)
            archive.save_completed(session)
            connection = sqlite3.connect(path)
            connection.execute(
                "UPDATE replay_sessions SET payload_sha256 = ?", ("0" * 64,)
            )
            connection.commit()
            connection.close()
            with self.assertRaises(ArchiveError) as caught:
                archive.save_completed(session)
            self.assertEqual(caught.exception.error_code, ErrorCode.ARCHIVE_CONFLICT)

    def test_archive_contains_semantics_not_question_key_or_media(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            SQLiteReplayArchive(path).save_completed(_session())
            raw = path.read_bytes()
        self.assertIn(b"claim-key-inside-bag", raw)
        self.assertNotIn("鑰匙在哪裡".encode("utf-8"), raw)
        self.assertNotIn(b"WHA_LLM_API_KEY", raw)
        self.assertNotIn(b"ftyp", raw)


class NaturalQuestionTests(unittest.TestCase):
    def test_chinese_and_english_location_questions_map_to_one_subject(self):
        allowed = ("key", "bag", "sofa")
        self.assertEqual(
            parse_location_question("鑰匙在哪裡？", allowed_entity_ids=allowed),
            "key",
        )
        self.assertEqual(
            parse_location_question("Where is my backpack?", allowed_entity_ids=allowed),
            "bag",
        )

    def test_action_ambiguous_unknown_and_control_questions_fail_closed(self):
        cases = (
            "幫我開門",
            "鑰匙和包包在哪裡",
            "where is the phone?",
            "key在哪\n",
            "鑰匙在哪裡，然後開門",
            "where is the key and open the door",
        )
        for question in cases:
            with self.subTest(question=question), self.assertRaises(QuestionError):
                parse_location_question(
                    question, allowed_entity_ids=("key", "bag", "sofa")
                )

    def test_query_restores_latest_session_and_does_not_store_question(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            archive = SQLiteReplayArchive(path)
            archive.save_completed(_session("natural-query-restart"))
            result = answer_latest_memory(
                SQLiteReplayArchive(path), "鑰匙放在哪裡？"
            )
            raw = path.read_bytes()
        self.assertEqual(result["answer"]["status"], "FOUND")
        self.assertEqual(result["answer"]["subject_id"], "key")
        self.assertEqual(result["answer"]["location_id"], "sofa")
        self.assertEqual(result["query"]["stored"], False)
        self.assertNotIn("鑰匙放在哪裡".encode("utf-8"), raw)


class LoopbackPresenterTests(unittest.TestCase):
    def test_public_endpoints_and_names_are_rejected(self):
        for endpoint in (
            "https://api.openai.com/v1/chat/completions",
            "http://8.8.8.8/v1/chat/completions",
            "http://localhost/v1/chat/completions",   # a name, not an address
            "http://192.168.1.50/v1/chat/completions",  # shared LAN, not a tunnel
            # Assembled rather than written out: a literal userinfo URL trips
            # this repository's own credential scanner, which is correct of it.
            "http://{}@127.0.0.1/v1/chat/completions".format("u:p"),
            "https://127.0.0.1/v1/chat/completions",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(PresenterConfigError):
                LoopbackChatPresenter(endpoint=endpoint, model="model-v1")

    def test_loopback_and_tailnet_addresses_are_accepted(self):
        for endpoint in (
            "http://127.0.0.1:11434/v1/chat/completions",
            "http://100.123.132.69:11435/v1/chat/completions",
        ):
            with self.subTest(endpoint=endpoint):
                presenter = LoopbackChatPresenter(endpoint=endpoint, model="model-v1")
                self.assertEqual(presenter.presenter_id, LOOPBACK_PRESENTER_ID)

    def test_request_disables_reasoning_so_the_budget_reaches_the_answer(self):
        """A reasoning model would spend max_tokens thinking and return ""."""

        response = _Response({"choices": [{"message": {"content": "好"}}]})
        presenter = LoopbackChatPresenter(
            endpoint="http://127.0.0.1:11434/v1/chat/completions", model="m-v1"
        )
        with mock.patch(
            "whole_home_agent.adapters.loopback_llm._open_request", return_value=response
        ) as opened:
            presenter.present(_context())
        sent = json.loads(opened.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(sent["reasoning_effort"], "none")

    def test_one_loopback_request_contains_only_minimized_context(self):
        response = _Response(
            {"choices": [{"message": {"content": "鑰匙可能在沙發上的包包裡。"}}]}
        )
        presenter = LoopbackChatPresenter(
            endpoint="http://127.0.0.1:11434/v1/chat/completions",
            model="qwen-local:fixed",
            authorization_value="local-test-key",
        )
        with mock.patch(
            "whole_home_agent.adapters.loopback_llm._open_request", return_value=response
        ) as request_mock:
            result = present_location_context(_context(), presenter)

        self.assertEqual(result.status, PRESENTED)
        self.assertEqual(result.presenter_id, LOOPBACK_PRESENTER_ID)
        request = request_mock.call_args.args[0]
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["messages"][1]["content"], json.dumps(
            _context(), ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        ))
        serialized = json.dumps(sent, ensure_ascii=False)
        self.assertNotIn("source_claim", serialized)
        self.assertNotIn("replay_run", serialized)
        self.assertEqual(request.get_header("Authorization"), "Bearer local-test-key")

    def test_provider_failure_returns_deterministic_fallback(self):
        presenter = LoopbackChatPresenter(
            endpoint="http://127.0.0.1:11434/v1/chat/completions",
            model="qwen-local:fixed",
        )
        with mock.patch(
            "whole_home_agent.adapters.loopback_llm._open_request",
            side_effect=OSError("secret failure"),
        ):
            result = present_location_context(_context(), presenter)
        self.assertTrue(result.fallback_used)
        self.assertNotIn("secret", result.text)


@unittest.skipUnless(HAS_VIDEO, "video optional dependencies are not installed")
class OfflineMemoryCliTests(unittest.TestCase):
    def test_remember_then_ask_work_across_two_cli_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            remember_stdout = io.StringIO()
            with contextlib.redirect_stdout(remember_stdout):
                remember_code = cli_main(
                    ["remember-demo", "--db", str(path), "--run-id", "cli-memory"]
                )
            ask_stdout = io.StringIO()
            with contextlib.redirect_stdout(ask_stdout):
                ask_code = cli_main(
                    [
                        "ask-memory",
                        "--db",
                        str(path),
                        "--question",
                        "Where is the key?",
                    ]
                )
            remembered = json.loads(remember_stdout.getvalue())
            answer = json.loads(ask_stdout.getvalue())

        self.assertEqual(remember_code, 0)
        self.assertEqual(ask_code, 0)
        self.assertEqual(remembered["archive"]["status"], "INSERTED")
        self.assertEqual(answer["answer"]["location_id"], "sofa")
        self.assertEqual(answer["presentation"]["status"], PRESENTED)

    def test_cli_reads_api_key_only_for_explicit_local_presenter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            SQLiteReplayArchive(path).save_completed(_session("cli-loopback"))
            response = _Response(
                {"choices": [{"message": {"content": "本機模型回答。"}}]}
            )
            stdout = io.StringIO()
            with (
                mock.patch.dict(os.environ, {"WHA_LLM_API_KEY": "loopback-only"}),
                mock.patch(
                    "whole_home_agent.adapters.loopback_llm._open_request",
                    return_value=response,
                ),
                contextlib.redirect_stdout(stdout),
            ):
                code = cli_main(
                    [
                        "ask-memory",
                        "--db",
                        str(path),
                        "--question",
                        "鑰匙在哪裡？",
                        "--presenter",
                        "local-api",
                        "--llm-endpoint",
                        "http://127.0.0.1:11434/v1/chat/completions",
                        "--llm-model",
                        "qwen-local:fixed",
                    ]
                )
            payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["presentation"]["text"], "本機模型回答。")


class MemoryUiBoundaryTests(unittest.TestCase):
    def test_checkout_disables_streamlit_usage_telemetry(self):
        config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("gatherUsageStats = false", config)

    def test_separate_memory_ui_has_text_query_but_no_camera_or_upload(self):
        source = (ROOT / "src" / "whole_home_agent" / "memory_app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("st.text_input", source)
        self.assertNotIn("camera_input", source)
        self.assertNotIn("file_uploader", source)
        self.assertNotIn("api_key", source.lower())

    @unittest.skipUnless(HAS_VIDEO and HAS_STREAMLIT, "demo extra is not installed")
    def test_memory_ui_records_then_answers_without_live_input(self):
        from streamlit.testing.v1 import AppTest

        app_path = ROOT / "src" / "whole_home_agent" / "memory_app.py"
        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(directory):
            def click(app, label):
                """Select by label; index-based selection breaks on any layout change."""

                for button in app.button:
                    if button.label == label:
                        return button.click().run(timeout=30)
                raise AssertionError(f"no button labelled {label!r}")

            app = AppTest.from_file(str(app_path)).run(timeout=30)
            self.assertEqual(app.exception, [])

            app = click(app, "建立示範記憶")
            self.assertEqual(app.exception, [])
            self.assertTrue(Path(".whole-home-agent/demo-memory.sqlite3").is_file())

            # The closed vocabulary is disclosed as one chip per askable entity.
            chip_labels = {button.label for button in app.button}
            self.assertLessEqual({"🔑 鑰匙", "👜 包包", "🛋 沙發"}, chip_labels)

            app = click(app, "🔑 鑰匙")
            self.assertEqual(app.exception, [])
            self.assertTrue(any("沙發" in item.value for item in app.success))

            # A rejected question explains itself instead of printing an error code.
            app.text_input[0].set_value("鑰匙跟包包在哪？").run(timeout=30)
            app = click(app, "詢問記憶")
            self.assertEqual(app.exception, [])
            self.assertTrue(any("一次只能問一個東西。" in item.value for item in app.info))
            self.assertFalse(any("unsupported_question" in item.value for item in app.warning))


if __name__ == "__main__":
    unittest.main()


class LocationVerificationTests(unittest.TestCase):
    """Yes/no questions answer from the resolved chain, or abstain as before."""

    def _archive(self, directory: str, fixture: str = "b0_key_bag_sofa_v1.json"):
        path = Path(directory) / "memory.sqlite3"
        session = run_fixture(
            load_fixture(ROOT / "examples" / "fixtures" / fixture),
            replay_run_id="verify-test",
        )
        SQLiteReplayArchive(path).save_completed(session)
        return SQLiteReplayArchive(path)

    def test_proposed_zone_and_container_both_count_as_yes(self):
        from whole_home_agent.memory_query import verify_latest_memory

        with tempfile.TemporaryDirectory() as directory:
            archive = self._archive(directory)
            for question in ("鑰匙在沙發上嗎", "鑰匙在包包裡嗎", "is my key on the sofa?"):
                with self.subTest(question=question):
                    result = verify_latest_memory(archive, question)
                    self.assertEqual(result["verification"]["verdict"], "YES")

    def test_wrong_place_is_no_and_still_reports_the_known_one(self):
        from whole_home_agent.memory_query import verify_latest_memory

        with tempfile.TemporaryDirectory() as directory:
            result = verify_latest_memory(self._archive(directory), "包包在鑰匙裡嗎")
        verification = result["verification"]
        self.assertEqual(verification["verdict"], "NO")
        self.assertIn("沙發", verification["text"])

    def test_unknown_place_answers_from_what_it_does_know(self):
        """The case a person actually hits: asking about a thing never recorded."""

        from whole_home_agent.memory_query import verify_latest_memory

        with tempfile.TemporaryDirectory() as directory:
            result = verify_latest_memory(self._archive(directory), "鑰匙在我的桌上嗎")
        verification = result["verification"]
        self.assertEqual(verification["verdict"], "TARGET_UNKNOWN")
        self.assertIsNone(verification["target_id"])
        self.assertIn("包包", verification["text"])

    def test_unresolved_subject_refuses_to_answer_yes_or_no(self):
        from whole_home_agent.memory_query import verify_latest_memory

        with tempfile.TemporaryDirectory() as directory:
            archive = self._archive(directory, "b0_take_out_v1.json")
            result = verify_latest_memory(archive, "鑰匙在沙發上嗎")
        verification = result["verification"]
        self.assertEqual(verification["verdict"], "UNRESOLVED")
        self.assertIn("UNKNOWN", verification["text"])

    def test_router_sends_each_question_shape_to_its_own_path(self):
        from whole_home_agent.memory_query import answer_question

        with tempfile.TemporaryDirectory() as directory:
            archive = self._archive(directory)
            self.assertIn("verification", answer_question(archive, "鑰匙在沙發上嗎"))
            self.assertIn("presentation", answer_question(archive, "鑰匙在哪"))
            with self.assertRaises(QuestionError):
                answer_question(archive, "幫我開門")
            with self.assertRaises(QuestionError):
                answer_question(archive, "沙發好看嗎")

    def test_verification_does_not_store_the_question(self):
        from whole_home_agent.memory_query import verify_latest_memory

        with tempfile.TemporaryDirectory() as directory:
            archive = self._archive(directory)
            verify_latest_memory(archive, "鑰匙在沙發上嗎")
            raw = (Path(directory) / "memory.sqlite3").read_bytes()
        self.assertNotIn("鑰匙在沙發上嗎".encode("utf-8"), raw)


class ContainerContentsTests(unittest.TestCase):
    """The reverse of a location question, read from the same active relations."""

    def _archive(self, directory: str):
        path = Path(directory) / "memory.sqlite3"
        SQLiteReplayArchive(path).save_completed(_session("contents-test"))
        return SQLiteReplayArchive(path)

    def test_container_lists_what_the_projection_already_holds(self):
        from whole_home_agent.memory_query import list_container_contents

        with tempfile.TemporaryDirectory() as directory:
            archive = self._archive(directory)
            for question in ("包包裡有什麼", "我的包包裡面有什麼", "what is in my bag"):
                with self.subTest(question=question):
                    result = list_container_contents(archive, question)
                    self.assertEqual(result["contents"]["contained_entity_ids"], ["key"])
                    self.assertIn("鑰匙", result["contents"]["text"])

    def test_a_zone_reports_what_stands_at_it_not_inside_it(self):
        from whole_home_agent.memory_query import list_container_contents

        with tempfile.TemporaryDirectory() as directory:
            result = list_container_contents(self._archive(directory), "沙發上有什麼")
        self.assertEqual(result["contents"]["contained_entity_ids"], ["bag"])
        self.assertIn("沙發上有包包", result["contents"]["text"])

    def test_empty_container_says_unrecorded_not_empty(self):
        from whole_home_agent.memory_query import list_container_contents

        with tempfile.TemporaryDirectory() as directory:
            result = list_container_contents(self._archive(directory), "鑰匙裡有什麼")
        self.assertEqual(result["contents"]["contained_entity_ids"], [])
        self.assertIn("不代表它是空的", result["contents"]["text"])

    def test_english_contents_question_is_not_routed_to_verification(self):
        """"what is in my bag" satisfies is...in; answering its location is wrong."""

        from whole_home_agent.memory_query import answer_question

        with tempfile.TemporaryDirectory() as directory:
            result = answer_question(self._archive(directory), "what is in my bag")
        self.assertIn("contents", result)
        self.assertNotIn("verification", result)

    def test_router_keeps_the_three_shapes_apart(self):
        from whole_home_agent.memory_query import answer_question

        with tempfile.TemporaryDirectory() as directory:
            archive = self._archive(directory)
            self.assertIn("contents", answer_question(archive, "包包裡有什麼"))
            self.assertIn("verification", answer_question(archive, "鑰匙在沙發上嗎"))
            self.assertIn("presentation", answer_question(archive, "鑰匙在哪"))
            for rejected in ("幫我開門", "沙發好看嗎", "今天天氣如何"):
                with self.subTest(question=rejected), self.assertRaises(QuestionError):
                    answer_question(archive, rejected)
