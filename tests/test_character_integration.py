"""Character choice changes prose, not answers or action authority."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from whole_home_agent.adapters.loopback_llm import character_name
from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
from whole_home_agent.fixture import load_fixture
from whole_home_agent.orchestrator import run_fixture
from whole_home_agent.web_app import Handler, _character_payload


class CharacterIntegrationTests(unittest.TestCase):
    def test_untrusted_character_types_fall_back(self):
        for value in (None, [], {}, 12, "unknown", "__proto__"):
            self.assertEqual(character_name(value), "雷姆")
        self.assertEqual(character_name("nailong"), "奶龍")

    def test_prose_translation_does_not_mutate_evidence(self):
        payload = {"answer": {"subject_id": "雷姆", "location_id": "sofa"},
                   "spoken": {"text": "雷姆的記錄", "speaker": "rem/1"},
                   "text": "雷姆回覆", "reason": "雷姆 is an entity ID"}
        before = copy.deepcopy(payload)
        result = _character_payload(payload, "nailong")
        self.assertEqual(result["spoken"]["text"], "奶龍的記錄")
        self.assertEqual(result["answer"], before["answer"])
        self.assertEqual(result["reason"], before["reason"])
        self.assertEqual(payload, before)

    def test_request_characters_preserve_answer_and_malformed_config_fallback(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "memory.sqlite3"
            SQLiteReplayArchive(database).save_completed(run_fixture(
                load_fixture(root / "examples/fixtures/b0_key_bag_sofa_v1.json"),
                replay_run_id="character-test"))
            reference = None
            for character in ("rem", "nailong", [], {}, None):
                raw = json.dumps({"question": "鑰匙在哪裡", "character": character}).encode()
                handler = object.__new__(Handler)
                handler.path = "/api/ask"
                handler.headers = {"Content-Length": str(len(raw))}
                handler.rfile = io.BytesIO(raw)
                handler.database = database
                with patch.dict("os.environ", {"WHA_LLM_ENDPOINT": "", "WHA_LLM_TEMPERATURE": "bad"}), patch.object(handler, "_json") as reply:
                    handler.do_POST()
                    self.assertEqual(reply.call_args.args[0], 200)
                    result = _character_payload(reply.call_args.args[1], handler.character)
                answer = result["answer"]
                self.assertEqual(answer["location_id"], "sofa")
                if reference is None:
                    reference = answer
                self.assertEqual(answer, reference)
                if isinstance(character, str) and character.startswith("nailong"):
                    self.assertIn("奶龍", result["spoken"]["text"])


if __name__ == "__main__":
    unittest.main()
