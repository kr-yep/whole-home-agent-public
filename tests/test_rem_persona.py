"""Unit tests for Rem character persona presentation and voicing."""

from __future__ import annotations

import unittest

from whole_home_agent.actuation.models import (
    ActionReceipt,
    ActionRequest,
    ActionStatus,
    ActionType,
)
from whole_home_agent.presentation import present_location_context
from whole_home_agent.rem_persona import (
    REM_PRESENTER_ID,
    RemLocationPresenter,
    rem_voice_actuation,
    rem_voice_contents,
    rem_voice_refusal,
    rem_voice_verification,
)


class RemPersonaTests(unittest.TestCase):
    def test_rem_presenter_found_with_chain(self):
        context = {
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
        presenter = RemLocationPresenter()
        result = present_location_context(context, presenter)
        self.assertEqual(result.presenter_id, REM_PRESENTER_ID)
        self.assertIn("雷姆", result.text)
        self.assertIn("鑰匙", result.text)
        self.assertIn("包包", result.text)
        self.assertIn("沙發", result.text)
        self.assertNotIn("系統估計", result.text)
        self.assertNotIn("在這段固定重播中", result.text)

    def test_rem_presenter_unknown_abstains_truthfully(self):
        context = {
            "schema": "whole-home-agent.location-context.v1",
            "purpose": "verbalize_location_answer",
            "answer": {
                "subject_id": "key",
                "status": "UNKNOWN",
                "location_id": None,
                "epistemic_status": "unknown",
            },
            "relation_facts": [],
        }
        presenter = RemLocationPresenter()
        result = present_location_context(context, presenter)
        self.assertIn("抱歉", result.text)
        self.assertIn("雷姆", result.text)
        self.assertIn("鑰匙", result.text)
        # Truthful abstention: must not hallucinate places
        for place in ("沙發", "包包", "抽屜", "客廳", "臥室", "書桌"):
            self.assertNotIn(place, result.text)

    def test_rem_voice_contents(self):
        contents = {"container": "包包", "items": ["鑰匙"]}
        text = rem_voice_contents(contents)
        self.assertIn("包包", text)
        self.assertIn("鑰匙", text)
        self.assertIn("雷姆", text)

    def test_rem_voice_verification_yes_and_no(self):
        answer = {
            "subject_id": "key",
            "location_id": "sofa",
            "relation_path": [
                {"subject_id": "key", "predicate": "inside", "object_id": "bag"},
                {"subject_id": "bag", "predicate": "at_zone", "object_id": "sofa"},
            ],
        }
        yes_res = rem_voice_verification(
            {"verdict": "YES", "subject_id": "key", "target_id": "sofa"},
            answer,
        )
        self.assertIn("是的，主人", yes_res)
        self.assertIn("包包", yes_res)

        no_res = rem_voice_verification(
            {"verdict": "NO", "subject_id": "key", "target_id": "desk"},
            answer,
        )
        self.assertIn("不對喔主人", no_res)

        unknown_target = rem_voice_verification(
            {"verdict": "TARGET_UNKNOWN", "subject_id": "key", "target_id": None},
            answer,
        )
        self.assertIn("您提到的那個位置", unknown_target)
        self.assertIn("鑰匙在包包裡", unknown_target)

    def test_rem_voice_actuation_success_and_denied(self):
        receipt_ac = ActionReceipt(
            action_id="act-1",
            target_device_id="living_room_ac",
            action_type=ActionType.SET_TEMPERATURE,
            status=ActionStatus.SIMULATED,
            message="客廳冷氣 已啟動並設定溫度為 26.0°C。",
            details={"current_state": {"temperature": 26.0}},
        )
        text_ac = rem_voice_actuation(receipt_ac)
        self.assertIn("客廳冷氣", text_ac)
        self.assertIn("26.0°C", text_ac)
        self.assertIn("主人", text_ac)

        receipt_denied = ActionReceipt(
            action_id="act-2",
            target_device_id="living_room_ac",
            action_type=ActionType.SET_TEMPERATURE,
            status=ActionStatus.DENIED,
            message="安全拒絕：冷氣溫度設定 16.0°C 超出安全舒適範圍 (18°C ~ 30°C)",
        )
        text_denied = rem_voice_actuation(receipt_denied)
        self.assertIn("原諒雷姆", text_denied)
        self.assertIn("18°C 到 30°C", text_denied)

    def test_rem_voice_refusal_persona_questions(self):
        who = rem_voice_refusal("妳是誰")
        self.assertIn("專屬女僕", who)
        self.assertIn("冷氣", who)

        what = rem_voice_refusal("妳會做什麼")
        self.assertIn("記住", what)
        self.assertIn("電燈", what)

    def test_rem_voice_refusal_unknown_object(self):
        unknown = rem_voice_refusal(
            "雨傘在哪裡",
            reason="question must name exactly one known object",
            details={"matched_entity_count": 0},
        )
        self.assertIn("沒有找到關於這項物品的記錄", unknown)
        self.assertIn("不會憑空猜測", unknown)


if __name__ == "__main__":
    unittest.main()
