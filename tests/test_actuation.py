"""Unit tests for smart device actuation models, parser, policy, dispatcher, and adapters."""

from __future__ import annotations

import unittest

from whole_home_agent.actuation.dispatcher import CommandDispatcher
from whole_home_agent.actuation.models import (
    ActionReceipt,
    ActionRequest,
    ActionStatus,
    ActionType,
    DeviceType,
)
from whole_home_agent.actuation.parser import parse_action_command
from whole_home_agent.actuation.policy import ActionPolicy
from whole_home_agent.adapters.home_assistant_actuator import HomeAssistantActuator
from whole_home_agent.adapters.mock_actuator import MockActuator


class TestActuationParser(unittest.TestCase):
    def test_parse_climate_commands(self):
        req_on = parse_action_command("幫我開冷氣")
        self.assertIsNotNone(req_on)
        self.assertEqual(req_on.target_device_id, "living_room_ac")
        self.assertEqual(req_on.action_type, ActionType.TURN_ON)

        req_off = parse_action_command("把冷氣關掉")
        self.assertIsNotNone(req_off)
        self.assertEqual(req_off.target_device_id, "living_room_ac")
        self.assertEqual(req_off.action_type, ActionType.TURN_OFF)

        req_temp = parse_action_command("冷氣設為26度")
        self.assertIsNotNone(req_temp)
        self.assertEqual(req_temp.target_device_id, "living_room_ac")
        self.assertEqual(req_temp.action_type, ActionType.SET_TEMPERATURE)
        self.assertEqual(req_temp.parameters["temperature"], 26.0)

        req_temp2 = parse_action_command("把客廳冷氣調到 24.5°C")
        self.assertIsNotNone(req_temp2)
        self.assertEqual(req_temp2.parameters["temperature"], 24.5)

    def test_parse_light_commands(self):
        req_living = parse_action_command("開客廳燈")
        self.assertIsNotNone(req_living)
        self.assertEqual(req_living.target_device_id, "living_room_light")
        self.assertEqual(req_living.action_type, ActionType.TURN_ON)

        req_bedroom = parse_action_command("關掉臥室燈")
        self.assertIsNotNone(req_bedroom)
        self.assertEqual(req_bedroom.target_device_id, "bedroom_light")
        self.assertEqual(req_bedroom.action_type, ActionType.TURN_OFF)

    def test_parse_curtain_commands(self):
        req_open = parse_action_command("拉開窗簾")
        self.assertIsNotNone(req_open)
        self.assertEqual(req_open.target_device_id, "living_room_curtain")
        self.assertEqual(req_open.action_type, ActionType.SET_POSITION)
        self.assertEqual(req_open.parameters["position"], 100)

        req_close = parse_action_command("把窗簾關上")
        self.assertIsNotNone(req_close)
        self.assertEqual(req_close.parameters["position"], 0)

        req_pct = parse_action_command("窗簾開到 60%")
        self.assertIsNotNone(req_pct)
        self.assertEqual(req_pct.parameters["position"], 60)

    def test_location_queries_not_parsed_as_actions(self):
        self.assertIsNone(parse_action_command("鑰匙在哪裡？"))
        self.assertIsNone(parse_action_command("包包在沙發上嗎？"))
        self.assertIsNone(parse_action_command("沙發上有什麼？"))
        self.assertIsNone(parse_action_command("where is the key"))


class TestActionPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = ActionPolicy()

    def test_allowlist_enforcement(self):
        req_invalid = ActionRequest(
            target_device_id="secret_vault_door",
            action_type=ActionType.TURN_ON,
        )
        denial = self.policy.evaluate(req_invalid)
        self.assertIsNotNone(denial)
        self.assertEqual(denial.status, ActionStatus.DENIED)
        self.assertIn("未在家庭安全允許名單中", denial.message)

    def test_temperature_boundary(self):
        # 26°C within 18~30: Pass
        req_valid = ActionRequest(
            target_device_id="living_room_ac",
            action_type=ActionType.SET_TEMPERATURE,
            parameters={"temperature": 26.0},
        )
        self.assertIsNone(self.policy.evaluate(req_valid))

        # 10°C too low: Denied
        req_too_low = ActionRequest(
            target_device_id="living_room_ac",
            action_type=ActionType.SET_TEMPERATURE,
            parameters={"temperature": 10.0},
        )
        denial_low = self.policy.evaluate(req_too_low)
        self.assertIsNotNone(denial_low)
        self.assertEqual(denial_low.status, ActionStatus.DENIED)

        # 45°C too high: Denied
        req_too_high = ActionRequest(
            target_device_id="living_room_ac",
            action_type=ActionType.SET_TEMPERATURE,
            parameters={"temperature": 45.0},
        )
        denial_high = self.policy.evaluate(req_too_high)
        self.assertIsNotNone(denial_high)
        self.assertEqual(denial_high.status, ActionStatus.DENIED)


class TestMockActuator(unittest.TestCase):
    def setUp(self):
        self.actuator = MockActuator()

    def test_initial_devices(self):
        devices = self.actuator.list_devices()
        self.assertEqual(len(devices), 4)
        ac = self.actuator.get_device_state("living_room_ac")
        self.assertIsNotNone(ac)
        self.assertFalse(ac.is_on)

    def test_turn_on_and_off(self):
        req_on = ActionRequest(
            target_device_id="living_room_light",
            action_type=ActionType.TURN_ON,
        )
        receipt_on = self.actuator.execute(req_on)
        self.assertEqual(receipt_on.status, ActionStatus.SIMULATED)
        state_on = self.actuator.get_device_state("living_room_light")
        self.assertTrue(state_on.is_on)

        req_off = ActionRequest(
            target_device_id="living_room_light",
            action_type=ActionType.TURN_OFF,
        )
        receipt_off = self.actuator.execute(req_off)
        self.assertEqual(receipt_off.status, ActionStatus.SIMULATED)
        state_off = self.actuator.get_device_state("living_room_light")
        self.assertFalse(state_off.is_on)

    def test_set_temperature(self):
        req = ActionRequest(
            target_device_id="living_room_ac",
            action_type=ActionType.SET_TEMPERATURE,
            parameters={"temperature": 25.0},
        )
        receipt = self.actuator.execute(req)
        self.assertEqual(receipt.status, ActionStatus.SIMULATED)
        ac = self.actuator.get_device_state("living_room_ac")
        self.assertTrue(ac.is_on)
        self.assertEqual(ac.temperature, 25.0)

    def test_set_curtain_position(self):
        req = ActionRequest(
            target_device_id="living_room_curtain",
            action_type=ActionType.SET_POSITION,
            parameters={"position": 75},
        )
        receipt = self.actuator.execute(req)
        self.assertEqual(receipt.status, ActionStatus.SIMULATED)
        curtain = self.actuator.get_device_state("living_room_curtain")
        self.assertEqual(curtain.position, 75)
        self.assertTrue(curtain.is_on)


class TestCommandDispatcher(unittest.TestCase):
    def setUp(self):
        self.actuator = MockActuator()
        self.dispatcher = CommandDispatcher(self.actuator)

    def test_dispatch_valid_action(self):
        receipt = self.dispatcher.dispatch("把客廳冷氣開到26度")
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.status, ActionStatus.SIMULATED)
        self.assertIn("26", receipt.message)

    def test_dispatch_denied_action(self):
        receipt = self.dispatcher.dispatch("冷氣設為 50 度")
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.status, ActionStatus.DENIED)

    def test_dispatch_passthrough_query(self):
        receipt = self.dispatcher.dispatch("鑰匙在沙發上嗎？")
        self.assertIsNone(receipt)


class TestHomeAssistantActuator(unittest.TestCase):
    def test_unconfigured_token_fails_gracefully(self):
        ha = HomeAssistantActuator(bearer_token="")
        req = ActionRequest(
            target_device_id="living_room_ac",
            action_type=ActionType.TURN_ON,
        )
        receipt = ha.execute(req)
        self.assertEqual(receipt.status, ActionStatus.FAILED)
        self.assertIn("HASS_TOKEN", receipt.message)


if __name__ == "__main__":
    unittest.main()
