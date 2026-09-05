"""End-to-end integration tests for web_app camera frame ingest with PerceptionBridge."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
from whole_home_agent.camera_ingest import FRAME_HEIGHT, FRAME_WIDTH, CameraIngest
from whole_home_agent.fixture import load_fixture
from whole_home_agent.orchestrator import run_fixture
from whole_home_agent.perception_bridge import PerceptionBridge
from whole_home_agent.web_app import Handler


def _dummy_jpeg() -> bytes:
    # Minimal 1280x720 JPEG byte sequence
    # 0xFFD8 (SOI), 0xFFC0 (SOF0 with H=720, W=1280), 0xFFD9 (EOI), padded
    header = (
        b"\xff\xd8"
        b"\xff\xc0\x00\x11\x08"
        + (720).to_bytes(2, "big")
        + (1280).to_bytes(2, "big")
        + b"\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    )
    padding = b"\x00" * 2000
    trailer = b"\xff\xd9"
    return header + padding + trailer


class TestWebCameraBridge(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(__file__).resolve().parents[1]
        self.db_path = Path(self._temp_dir.name) / "test-memory.sqlite3"
        self.archive = SQLiteReplayArchive(self.db_path)

        fixture = load_fixture(self.root / "examples/fixtures/b0_key_bag_sofa_v1.json")
        session = run_fixture(fixture, replay_run_id="test-web-bridge-run")
        self.archive.save_completed(session)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_camera_frames_bridge_to_memory_and_query(self) -> None:
        # Create a fresh CameraIngest instance with a mock sink that simulates seeing a cell phone
        mock_sink = lambda payload, w, h: [{"raw_label": "cell phone", "confidence": 0.88}]
        test_camera = CameraIngest(default_sink=mock_sink)

        with patch("whole_home_agent.web_app.CAMERA", test_camera):
            # 1. Start camera session
            start_payload = json.dumps({"device_label": "test-cam"}).encode("utf-8")
            start_handler = object.__new__(Handler)
            start_handler.database = self.db_path
            start_handler.headers = {"Content-Length": str(len(start_payload))}
            start_handler.rfile = io.BytesIO(start_payload)
            with patch.object(start_handler, "_json") as mock_json:
                start_handler._camera_post("/api/camera/start", {})
                self.assertEqual(mock_json.call_args.args[0], 200)
                session_id = mock_json.call_args.args[1]["session_id"]

            jpeg = _dummy_jpeg()
            bridge = PerceptionBridge(self.archive, min_stable_frames=3, min_confidence=0.35)
            Handler.bridge = bridge

            # 2. Send 3 frames to /api/camera/frame
            for seq in range(3):
                frame_handler = object.__new__(Handler)
                frame_handler.database = self.db_path
                frame_handler.headers = {"Content-Length": str(len(jpeg))}
                frame_handler.rfile = io.BytesIO(jpeg)
                with patch.object(frame_handler, "_json") as mock_json:
                    frame_handler._camera_post(
                        "/api/camera/frame",
                        {
                            "session": [session_id],
                            "sequence": [str(seq)],
                            "captured_ns": [str(1000000 * (seq + 1))],
                            "zone": ["desk"],
                        },
                    )
                    self.assertEqual(mock_json.call_args.args[0], 200)
                    resp = mock_json.call_args.args[1]
                    if seq < 2:
                        self.assertEqual(resp.get("committed", []), [])
                    else:
                        # 3rd frame must commit
                        self.assertEqual(len(resp.get("committed", [])), 1)
                        committed = resp["committed"][0]
                        self.assertEqual(committed["status"], "COMMITTED")
                        self.assertEqual(committed["subject_id"], "phone")
                        self.assertEqual(committed["zone_id"], "desk")

            # 3. Query /api/ask for "我的手機在哪"
            ask_payload = json.dumps({"question": "我的手機在哪", "character": "rem"}).encode("utf-8")
            ask_handler = object.__new__(Handler)
            ask_handler.database = self.db_path
            ask_handler.headers = {"Content-Length": str(len(ask_payload))}
            ask_handler.rfile = io.BytesIO(ask_payload)
            ask_handler.path = "/api/ask"
            with patch.object(ask_handler, "_json") as mock_json:
                ask_handler.do_POST()
                self.assertEqual(mock_json.call_args.args[0], 200)
                result = mock_json.call_args.args[1]

            # Verify that Rem finds the phone at the desk
            self.assertEqual(result["answer"]["status"], "FOUND")
            self.assertEqual(result["answer"]["location_id"], "desk")
            self.assertIn("書桌", result["presentation"]["text"])


if __name__ == "__main__":
    unittest.main()
