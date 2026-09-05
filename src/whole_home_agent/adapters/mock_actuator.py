"""In-memory mock actuator for testing and zero-hardware offline development."""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from whole_home_agent.actuation.models import (
    ActionReceipt,
    ActionRequest,
    ActionStatus,
    ActionType,
    DeviceState,
    DeviceType,
)
from whole_home_agent.actuation.port import ActuatorPort


def default_mock_devices() -> Dict[str, DeviceState]:
    """Return default set of virtual household devices."""
    return {
        "living_room_ac": DeviceState(
            device_id="living_room_ac",
            device_type=DeviceType.CLIMATE,
            name="客廳冷氣",
            room="客廳",
            is_on=False,
            temperature=26.0,
            attributes={"target_temperature": 26.0, "mode": "cool"},
        ),
        "living_room_light": DeviceState(
            device_id="living_room_light",
            device_type=DeviceType.LIGHT,
            name="客廳大燈",
            room="客廳",
            is_on=False,
            attributes={"brightness": 100},
        ),
        "bedroom_light": DeviceState(
            device_id="bedroom_light",
            device_type=DeviceType.LIGHT,
            name="臥室電燈",
            room="臥室",
            is_on=False,
            attributes={"brightness": 80},
        ),
        "living_room_curtain": DeviceState(
            device_id="living_room_curtain",
            device_type=DeviceType.COVER,
            name="客廳窗簾",
            room="客廳",
            is_on=False,
            position=0,
            attributes={"open_percentage": 0},
        ),
    }


class MockActuator(ActuatorPort):
    """Zero-dependency in-memory device actuator implementing ActuatorPort."""

    def __init__(self, devices: Optional[Dict[str, DeviceState]] = None) -> None:
        self.devices = devices if devices is not None else default_mock_devices()

    def get_device_state(self, device_id: str) -> Optional[DeviceState]:
        return self.devices.get(device_id)

    def list_devices(self) -> List[DeviceState]:
        return list(self.devices.values())

    def execute(self, request: ActionRequest) -> ActionReceipt:
        device = self.devices.get(request.target_device_id)
        if device is None:
            return ActionReceipt(
                action_id=f"act-{uuid.uuid4().hex[:8]}",
                target_device_id=request.target_device_id,
                action_type=request.action_type,
                status=ActionStatus.FAILED,
                message=f"執行失敗：找不到設備 '{request.target_device_id}'",
                details={"error": "device_not_found"},
            )

        receipt_id = f"act-sim-{uuid.uuid4().hex[:8]}"

        if request.action_type == ActionType.TURN_ON:
            device.is_on = True
            if device.device_type == DeviceType.COVER:
                device.position = 100
            return ActionReceipt(
                action_id=receipt_id,
                target_device_id=device.device_id,
                action_type=request.action_type,
                status=ActionStatus.SIMULATED,
                message=f"已開啟 {device.name}。",
                details={"current_state": device.as_dict()},
            )

        elif request.action_type == ActionType.TURN_OFF:
            device.is_on = False
            if device.device_type == DeviceType.COVER:
                device.position = 0
            return ActionReceipt(
                action_id=receipt_id,
                target_device_id=device.device_id,
                action_type=request.action_type,
                status=ActionStatus.SIMULATED,
                message=f"已關閉 {device.name}。",
                details={"current_state": device.as_dict()},
            )

        elif request.action_type == ActionType.SET_TEMPERATURE:
            temp = float(request.parameters["temperature"])
            device.temperature = temp
            device.is_on = True
            device.attributes["target_temperature"] = temp
            return ActionReceipt(
                action_id=receipt_id,
                target_device_id=device.device_id,
                action_type=request.action_type,
                status=ActionStatus.SIMULATED,
                message=f"{device.name} 已啟動並設定溫度為 {temp}°C。",
                details={"target_temperature": temp, "current_state": device.as_dict()},
            )

        elif request.action_type == ActionType.SET_POSITION:
            pos = int(request.parameters.get("position", 100))
            device.position = pos
            device.is_on = pos > 0
            device.attributes["open_percentage"] = pos
            pos_desc = "拉開" if pos == 100 else ("關上" if pos == 0 else f"設定為 {pos}%")
            return ActionReceipt(
                action_id=receipt_id,
                target_device_id=device.device_id,
                action_type=request.action_type,
                status=ActionStatus.SIMULATED,
                message=f"{device.name} 已{pos_desc}。",
                details={"position": pos, "current_state": device.as_dict()},
            )

        return ActionReceipt(
            action_id=receipt_id,
            target_device_id=device.device_id,
            action_type=request.action_type,
            status=ActionStatus.FAILED,
            message=f"未知的動作操作：{request.action_type.value}",
        )
