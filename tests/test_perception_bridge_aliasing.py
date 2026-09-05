"""Tests for household aliasing and visual enrollment integration in PerceptionBridge."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
from whole_home_agent.memory_query import answer_question
from whole_home_agent.perception_bridge import PerceptionBridge
from whole_home_agent.fixture import load_fixture
from whole_home_agent.orchestrator import run_fixture


class TestPerceptionBridgeAliasing(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(__file__).resolve().parents[1]
        self.db_path = Path(self._temp_dir.name) / "test-memory-aliasing.sqlite3"
        self.archive = SQLiteReplayArchive(self.db_path)
        fixture = load_fixture(self.root / "examples/fixtures/b0_key_bag_sofa_v1.json")
        session = run_fixture(fixture, replay_run_id="test-alias-init")
        self.archive.save_completed(session)
        self.bridge = PerceptionBridge(
            self.archive,
            default_zone="desk",
            min_stable_frames=3,
            min_confidence=0.25,
            enable_household_aliases=True,
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_household_aliasing_resolution(self) -> None:
        # With household aliases enabled:
        self.assertEqual(
            self.bridge.resolve_entity_id("remote", apply_household_aliases=True),
            "phone",
        )
        self.assertEqual(
            self.bridge.resolve_entity_id("bottle", apply_household_aliases=True),
            "cup",
        )
        # Without household aliases:
        self.assertEqual(
            self.bridge.resolve_entity_id("remote", apply_household_aliases=False),
            "remote",
        )
        self.assertEqual(
            self.bridge.resolve_entity_id("bottle", apply_household_aliases=False),
            "bottle",
        )

    def test_remote_detection_commits_as_phone_and_answers(self) -> None:
        # Camera detects 'remote' (which is the classic COCO misclassification of smartphone)
        remote_det = [
            {"raw_label": "remote", "label": "遙控器", "confidence": 0.85, "x": 100, "y": 100, "w": 60, "h": 120}
        ]

        # 3 consecutive frames at desk
        for _ in range(2):
            res = self.bridge.process_detections(remote_det, zone_id="desk")
            self.assertEqual(res, [])

        # Frame 3: stabilizes and commits
        res3 = self.bridge.process_detections(remote_det, zone_id="desk")
        self.assertEqual(len(res3), 1)
        self.assertEqual(res3[0]["status"], "COMMITTED")
        self.assertEqual(res3[0]["subject_id"], "phone")
        self.assertEqual(res3[0]["zone_id"], "desk")

        # Now query: "我的手機在哪"
        answer = answer_question(self.archive, "我的手機在哪")
        self.assertEqual(answer["answer"]["status"], "FOUND")
        self.assertEqual(answer["answer"]["location_id"], "desk")

    def test_bottle_detection_commits_as_cup_and_answers(self) -> None:
        # Camera detects 'bottle' (classic COCO misclassification of tumbler/water cup)
        bottle_det = [
            {"raw_label": "bottle", "label": "水瓶", "confidence": 0.80, "x": 200, "y": 150, "w": 50, "h": 110}
        ]

        for _ in range(2):
            self.bridge.process_detections(bottle_det, zone_id="table")

        res = self.bridge.process_detections(bottle_det, zone_id="table")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["status"], "COMMITTED")
        self.assertEqual(res[0]["subject_id"], "cup")
        self.assertEqual(res[0]["zone_id"], "table")

        # Query: "你有看到我的水杯嗎"
        answer = answer_question(self.archive, "你有看到我的水杯嗎")
        self.assertEqual(answer["answer"]["status"], "FOUND")
        self.assertEqual(answer["answer"]["location_id"], "table")


if __name__ == "__main__":
    unittest.main()
