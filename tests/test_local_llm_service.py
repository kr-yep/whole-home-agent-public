"""The offline stand-in for a model, checked against the prompts it must read.

tools/local_llm_service.py answers the three prompts this package sends when no
real model is configured. It routes on phrases from those prompts, so a reworded
prompt can silently send every request down the wrong branch -- which is what had
happened to the refusal branch: it was keyed on a sentence no prompt contained
and had never run, so a question about something the archive had no record of was
answered with a pleasantry rather than an honest no.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

from whole_home_agent.adapters.loopback_llm import (
    CHARACTER_NAMES,
    _TRANSLATOR_SYSTEM,
    _refusal_system,
    _verbalizer_system,
)

_SERVICE = Path(__file__).resolve().parents[1] / "tools" / "local_llm_service.py"
_spec = importlib.util.spec_from_file_location("local_llm_service", _SERVICE)
service = importlib.util.module_from_spec(_spec)
sys.modules["local_llm_service"] = service
_spec.loader.exec_module(service)


def _route(system_prompt: str) -> str:
    """Which generator the service itself picks -- its own routing, not a copy."""

    return {
        service._generate_translator_response: "translator",
        service._generate_refusal_response: "refusal",
        service._generate_verbalizer_response: "verbalizer",
    }[service.generator_for(system_prompt)]


class RoutingTests(unittest.TestCase):
    def test_each_prompt_reaches_its_own_generator(self):
        for name in CHARACTER_NAMES.values():
            with self.subTest(character=name):
                self.assertEqual(_route(_TRANSLATOR_SYSTEM), "translator")
                self.assertEqual(_route(_refusal_system(name)), "refusal")
                self.assertEqual(_route(_verbalizer_system(name)), "verbalizer")

    def test_the_markers_do_not_depend_on_the_character(self):
        """Both characters share one service; a name in a marker would split it."""

        for name in CHARACTER_NAMES.values():
            self.assertNotIn(name, "查詢翻譯器沒辦法處理")


class VerbalizerTests(unittest.TestCase):
    def speak(self, facts: dict) -> str:
        return service._generate_verbalizer_response(
            [
                {"role": "system", "content": _verbalizer_system("雷姆")},
                {"role": "user", "content": f"使用者問：測試\n查詢結果：{json.dumps(facts, ensure_ascii=False)}"},
            ]
        )

    def test_one_hop_names_the_place_once(self):
        """It used to read the chain and the location field, and say both."""

        spoken = self.speak(
            {"status": "FOUND", "subject": "遙控器", "chain": [{"遙控器": "位於餐桌"}]}
        )
        self.assertIn("遙控器位於餐桌", spoken)
        self.assertNotIn("而該處位於", spoken)
        self.assertEqual(spoken.count("餐桌"), 1)

    def test_two_hops_still_name_both_places(self):
        spoken = self.speak(
            {
                "status": "FOUND",
                "subject": "錢包",
                "chain": [{"錢包": "在抽屜裡面"}, {"抽屜": "位於書桌"}],
            }
        )
        self.assertIn("錢包在抽屜裡面", spoken)
        self.assertIn("抽屜位於書桌", spoken)

    def test_a_recorded_time_is_voiced_rather_than_swallowed(self):
        recorded = "這段固定重播的第 1 筆記錄，顯示鑰匙進入包包；沒有可換算的影片秒數。"
        spoken = self.speak({"status": "TIMELINE", "text": recorded})
        self.assertIn(recorded, spoken)

    def test_contents_are_listed(self):
        spoken = self.speak(
            {"status": "CONTENTS", "container": "包包", "items": ["鑰匙", "錢包"]}
        )
        self.assertIn("鑰匙", spoken)
        self.assertIn("錢包", spoken)


class RefusalTests(unittest.TestCase):
    def refuse(self, question: str, hint: str = "") -> str:
        note = f"\n（內部提示，不要照念：{hint}）" if hint else ""
        return service._generate_refusal_response(
            [
                {"role": "system", "content": _refusal_system("雷姆")},
                {"role": "user", "content": f"使用者說：{question}{note}"},
            ]
        )

    def test_a_refusal_says_there_is_no_record(self):
        self.assertIn("沒有找到", self.refuse("冰箱在哪裡"))

    def test_the_hint_naming_the_character_is_not_read_as_a_greeting(self):
        """rem_voice_refusal names her, and the hint carries that wording."""

        spoken = self.refuse(
            "冰箱在哪裡",
            "非常抱歉主人，雷姆沒能完全理解您的意思…您可以詢問雷姆物品的位置。",
        )
        self.assertIn("沒有找到", spoken)
        self.assertNotIn("一直都在這裡等您", spoken)

    def test_being_addressed_by_name_is_not_a_greeting(self):
        self.assertIn("沒有找到", self.refuse("雷姆，我的冰箱在哪"))

    def test_an_actual_greeting_is_still_greeted(self):
        self.assertIn("一直都在這裡等您", self.refuse("你好"))


if __name__ == "__main__":
    unittest.main()
