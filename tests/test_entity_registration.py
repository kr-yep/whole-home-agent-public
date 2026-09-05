"""Tests for dynamic entity registration and custom entity mapping."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from whole_home_agent.entity_registry import (
    EntityRegistry,
    try_parse_registration,
    _clean_entity_name,
)


class TestEntityRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.storage_file = Path(self.tmp_dir.name) / "test_entities.json"
        self.registry = EntityRegistry(storage_path=self.storage_file)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_register_standard_items(self) -> None:
        rec_phone = self.registry.register("手機")
        self.assertEqual(rec_phone["entity_id"], "phone")
        self.assertEqual(rec_phone["display_name"], "手機")
        self.assertEqual(rec_phone["provenance"], "user_confirmed")

        rec_cup = self.registry.register("水杯")
        self.assertEqual(rec_cup["entity_id"], "cup")
        self.assertEqual(rec_cup["display_name"], "水杯")

    def test_register_custom_item(self) -> None:
        rec = self.registry.register("阿公的藥袋", aliases=["藥袋"])
        self.assertEqual(rec["entity_id"], "custom_阿公的藥袋")
        self.assertEqual(rec["display_name"], "阿公的藥袋")
        self.assertIn("藥袋", rec["aliases"])
        self.assertIn("阿公的藥袋", rec["aliases"])

    def test_persistence_reload(self) -> None:
        self.registry.register("保溫杯")
        reloaded = EntityRegistry(storage_path=self.storage_file)
        entities = reloaded.list_entities()
        self.assertTrue(any(e["display_name"] == "保溫杯" for e in entities))

    def test_get_aliases_map(self) -> None:
        self.registry.register("眼鏡")
        alias_map = self.registry.get_aliases_map()
        self.assertIn("key", alias_map)
        self.assertIn("bag", alias_map)
        self.assertIn("phone", alias_map)
        self.assertIn("custom_眼鏡", alias_map)
        self.assertIn("眼鏡", alias_map["custom_眼鏡"])


class TestRegistrationParsing(unittest.TestCase):
    def test_parse_valid_patterns(self) -> None:
        cases = [
            ("這是水杯", "水杯"),
            ("這是一個水杯", "水杯"),
            ("這是我的手機", "手機"),
            ("這是我的包包喔", "包包"),
            ("請幫我記這個是阿公的藥袋", "阿公的藥袋"),
            ("這個叫做保溫杯", "保溫杯"),
            ("記住，這是鑰匙", "鑰匙"),
        ]
        for sentence, expected in cases:
            with self.subTest(sentence=sentence):
                parsed = try_parse_registration(sentence)
                self.assertEqual(parsed, expected)

    def test_reject_questions_and_actions(self) -> None:
        reject_cases = [
            "這是什麼？",
            "這是甚麼",
            "這是誰的？",
            "鑰匙在哪裡",
            "你有看到我的手機嗎",
            "幫我開燈",
            "關閉冷氣",
        ]
        for sentence in reject_cases:
            with self.subTest(sentence=sentence):
                self.assertIsNone(try_parse_registration(sentence))


if __name__ == "__main__":
    unittest.main()
