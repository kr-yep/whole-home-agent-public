"""Tests for PerceptionBridge: debouncing, canonical claim emission, and archive commits."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
from whole_home_agent.memory_query import answer_question
from whole_home_agent.model import (
    ClaimOperation,
    EpistemicStatus,
    Predicate,
    ReplaySession,
)
from whole_home_agent.perception_bridge import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MIN_STABLE_FRAMES,
    PerceptionBridge,
)
from whole_home_agent.fixture import load_fixture
from whole_home_agent.orchestrator import run_fixture


class TestPerceptionBridge(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(__file__).resolve().parents[1]
        self.db_path = Path(self._temp_dir.name) / "test-memory.sqlite3"
        self.archive = SQLiteReplayArchive(self.db_path)
        # Seed initial session with the standard B0 fixture (key in bag at sofa)
        fixture = load_fixture(self.root / "examples/fixtures/b0_key_bag_sofa_v1.json")
        session = run_fixture(fixture, replay_run_id="test-bridge-init")
        self.archive.save_completed(session)
        self.bridge = PerceptionBridge(
            self.archive,
            default_zone="desk",
            min_stable_frames=3,
            min_confidence=0.35,
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_resolve_entity_id(self) -> None:
        self.assertEqual(self.bridge.resolve_entity_id("cell phone"), "phone")
        self.assertEqual(self.bridge.resolve_entity_id("Cell Phone"), "phone")
        self.assertEqual(self.bridge.resolve_entity_id("cup"), "cup")
        self.assertEqual(self.bridge.resolve_entity_id("bottle"), "bottle")
        self.assertEqual(self.bridge.resolve_entity_id("laptop"), "laptop")
        self.assertEqual(self.bridge.resolve_entity_id("backpack"), "bag")
        self.assertEqual(self.bridge.resolve_entity_id("handbag"), "bag")
        self.assertEqual(self.bridge.resolve_entity_id("couch"), "sofa")
        self.assertEqual(self.bridge.resolve_entity_id("dining table"), "table")
        self.assertIsNone(self.bridge.resolve_entity_id(""))
        self.assertIsNone(self.bridge.resolve_entity_id("   "))

    def test_debounce_accumulation_and_commit(self) -> None:
        phone_det = [{"raw_label": "cell phone", "confidence": 0.88}]

        # Frame 1: count = 1 -> no commit
        r1 = self.bridge.process_detections(phone_det, zone_id="desk")
        self.assertEqual(r1, [])

        # Frame 2: count = 2 -> no commit
        r2 = self.bridge.process_detections(phone_det, zone_id="desk")
        self.assertEqual(r2, [])

        # Frame 3: count = 3 -> commit!
        r3 = self.bridge.process_detections(phone_det, zone_id="desk")
        self.assertEqual(len(r3), 1)
        self.assertEqual(r3[0]["status"], "COMMITTED")
        self.assertEqual(r3[0]["subject_id"], "phone")
        self.assertEqual(r3[0]["zone_id"], "desk")
        self.assertEqual(r3[0]["operation"], "ASSERT")

        # Frame 4: count = 4 -> already active, no duplicate commit
        r4 = self.bridge.process_detections(phone_det, zone_id="desk")
        self.assertEqual(r4, [])

        # Verify query against archive resolves phone at desk
        ans = answer_question(self.archive, "我的手機在哪")
        self.assertEqual(ans["answer"]["status"], "FOUND")
        self.assertEqual(ans["answer"]["location_id"], "desk")

    def test_idempotent_commit(self) -> None:
        # First commit
        res1 = self.bridge.commit_observation("phone", "desk", confidence=0.9)
        self.assertEqual(res1.status, "COMMITTED")

        # Second commit with same subject and zone -> UNCHANGED
        res2 = self.bridge.commit_observation("phone", "desk", confidence=0.9)
        self.assertEqual(res2.status, "UNCHANGED")

    def test_relocation_with_retraction(self) -> None:
        phone_det = [{"raw_label": "cell phone", "confidence": 0.9}]

        # Stabilize at desk
        for _ in range(3):
            self.bridge.process_detections(phone_det, zone_id="desk")

        ans1 = answer_question(self.archive, "我的手機在哪")
        self.assertEqual(ans1["answer"]["location_id"], "desk")

        # Now phone is moved to dining table
        table_det = [{"raw_label": "cell phone", "confidence": 0.92}]
        for _ in range(2):
            r = self.bridge.process_detections(table_det, zone_id="table")
            self.assertEqual(r, [])

        # Third frame at table triggers relocation
        r3 = self.bridge.process_detections(table_det, zone_id="table")
        self.assertEqual(len(r3), 1)
        self.assertEqual(r3[0]["status"], "COMMITTED")
        self.assertEqual(r3[0]["zone_id"], "table")
        self.assertEqual(r3[0]["details"]["retracted_count"], 1)

        # Verify archive only has 1 location for phone (no conflict!)
        session = self.archive.load_latest()
        phone_relations = [
            r for r in session.projection.active_relations if r.subject_id == "phone"
        ]
        self.assertEqual(len(phone_relations), 1)
        self.assertEqual(phone_relations[0].object_id, "table")

        ans2 = answer_question(self.archive, "我的手機在哪")
        self.assertEqual(ans2["answer"]["status"], "FOUND")
        self.assertEqual(ans2["answer"]["location_id"], "table")

    def test_taking_object_out_of_container(self) -> None:
        # Baseline has key inside bag
        ans_init = answer_question(self.archive, "我的鑰匙在哪")
        self.assertEqual(ans_init["answer"]["location_id"], "sofa")  # key -> bag -> sofa
        self.assertEqual(len(ans_init["answer"]["relation_path"]), 2)

        # Camera sees key on desk
        key_det = [{"raw_label": "key", "confidence": 0.85}]
        for _ in range(2):
            self.bridge.process_detections(key_det, zone_id="desk")
        commits = self.bridge.process_detections(key_det, zone_id="desk")
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["status"], "COMMITTED")

        # Key is now directly at desk, not inside bag anymore!
        ans_after = answer_question(self.archive, "我的鑰匙在哪")
        self.assertEqual(ans_after["answer"]["status"], "FOUND")
        self.assertEqual(ans_after["answer"]["location_id"], "desk")
        self.assertEqual(len(ans_after["answer"]["relation_path"]), 1)
        self.assertEqual(ans_after["answer"]["relation_path"][0]["predicate"], "at_zone")

    def test_low_confidence_filtered(self) -> None:
        low_conf = [{"raw_label": "cell phone", "confidence": 0.20}]
        for _ in range(5):
            res = self.bridge.process_detections(low_conf, zone_id="desk")
            self.assertEqual(res, [])

        session = self.archive.load_latest()
        phone_rels = [
            r for r in session.projection.active_relations if r.subject_id == "phone"
        ]
        self.assertEqual(len(phone_rels), 0)

    def test_decay_on_disappearance(self) -> None:
        phone_det = [{"raw_label": "cell phone", "confidence": 0.8}]
        empty_det: list[dict] = []

        # 2 frames of phone
        self.bridge.process_detections(phone_det, zone_id="desk")
        self.bridge.process_detections(phone_det, zone_id="desk")

        # 2 frames of nothing (decays count back to 0)
        self.bridge.process_detections(empty_det, zone_id="desk")
        self.bridge.process_detections(empty_det, zone_id="desk")

        # 1 more frame of phone (count should be 1, not 3)
        res = self.bridge.process_detections(phone_det, zone_id="desk")
        self.assertEqual(res, [])


if __name__ == "__main__":
    unittest.main()
