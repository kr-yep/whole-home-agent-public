"""Regression tests for demonstrated demo failures."""
import io
import json
import unittest
import tempfile
import threading
import http.client
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from whole_home_agent.actuation.parser import parse_action_command
from whole_home_agent.actuation.models import ActionType, ActionStatus, ActionReceipt
from whole_home_agent.rem_persona import rem_voice_actuation
from whole_home_agent.web_app import Handler
from whole_home_agent.actuation.policy import ActionPolicy
from whole_home_agent.actuation.models import ActionRequest


class DemoHardeningTests(unittest.TestCase):
    def test_large_temperature_is_not_truncated(self):
        request = parse_action_command("冷氣設為126度")
        self.assertEqual(request.parameters["temperature"], 126)
        self.assertEqual(ActionPolicy().evaluate(request).status, ActionStatus.DENIED)

    def test_http_demo_queries_and_simulated_actions(self):
        from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
        from whole_home_agent.adapters.mock_actuator import MockActuator
        from whole_home_agent.actuation.dispatcher import CommandDispatcher
        from whole_home_agent.fixture import load_fixture
        from whole_home_agent.orchestrator import run_fixture
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"WHA_LLM_ENDPOINT": "", "WHA_LLM_MODEL": ""}):
            database = Path(directory) / "demo.sqlite3"
            SQLiteReplayArchive(database).save_completed(run_fixture(
                load_fixture(root / "examples/fixtures/b0_key_bag_sofa_v1.json"), replay_run_id="http-test"))
            actuator = MockActuator()
            isolated = type("TestHandler", (Handler,), {"database": database, "actuator": actuator,
                                                       "dispatcher": CommandDispatcher(actuator)})
            server = ThreadingHTTPServer(("127.0.0.1", 0), isolated)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            try:
                for question in ("鑰匙在哪裡", "開客廳燈", "不要開冷氣"):
                    connection.request("POST", "/api/ask", json.dumps({"question": question}), {"Content-Type": "application/json"})
                    response = connection.getresponse()
                    result = json.loads(response.read())
                    self.assertEqual(response.status, 200)
                    if question == "鑰匙在哪裡":
                        self.assertEqual(result["answer"]["location_id"], "sofa")
                    elif question == "開客廳燈":
                        self.assertEqual(result["action_receipt"]["status"], "simulated")
                    else:
                        self.assertNotIn("action_receipt", result)
                self.assertFalse(actuator.get_device_state("living_room_ac").is_on)
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
    def test_wrong_device_action_and_missing_position_denied(self):
        for request in (
            ActionRequest("living_room_light", ActionType.SET_TEMPERATURE, {"temperature": 26}),
            ActionRequest("living_room_curtain", ActionType.SET_POSITION),
            ActionRequest("living_room_curtain", ActionType.SET_POSITION, {"position": 50.5}),
        ):
            self.assertEqual(ActionPolicy().evaluate(request).status, ActionStatus.DENIED)
    def test_negated_or_question_commands_do_not_execute(self):
        for question in ("不要開燈", "燈開了嗎？", "別開冷氣", "don't turn on the light", "開燈然後關冷氣"):
            with self.subTest(question=question):
                self.assertIsNone(parse_action_command(question))

    def test_positive_command_still_works(self):
        self.assertEqual(parse_action_command("開客廳燈").action_type, ActionType.TURN_ON)

    def test_unsupported_toggle_does_not_crash_persona(self):
        receipt = ActionReceipt("test", "living_room_light", ActionType.TOGGLE, ActionStatus.SIMULATED, "模擬切換")
        self.assertIn("模擬切換", rem_voice_actuation(receipt))

    def test_malformed_http_inputs_return_json_errors(self):
        for raw, length, expected in ((b"[]", "2", 400), (b"null", "4", 400), (b"{}", "bad", 400), (b"\xff", "1", 400)):
            handler = object.__new__(Handler)
            handler.path = "/api/ask"
            handler.headers = {"Content-Length": length}
            handler.rfile = io.BytesIO(raw)
            with patch.object(handler, "_json") as reply:
                handler.do_POST()
                self.assertEqual(reply.call_args.args[0], expected)

    def test_cross_origin_action_denied(self):
        handler = object.__new__(Handler)
        handler.path = "/api/ask"
        handler.headers = {"Origin": "https://example.org", "Host": "127.0.0.1:8600"}
        with patch.object(handler, "_json") as reply:
            handler.do_POST()
            self.assertEqual(reply.call_args.args[0], 403)
