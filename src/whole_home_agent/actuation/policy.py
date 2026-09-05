"""Action safety policy implementing the R4 bounded comfort actuation requirements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set

from .models import ActionRequest, ActionStatus, ActionReceipt, ActionType


DEFAULT_ALLOWED_DEVICES: Set[str] = {
    "living_room_ac",
    "living_room_light",
    "bedroom_light",
    "living_room_curtain",
}

DEFAULT_MIN_TEMPERATURE = 18.0
DEFAULT_MAX_TEMPERATURE = 30.0


@dataclass
class ActionPolicy:
    """Enforces safety bounds, allowlists, and parameter constraints before actuation."""

    allowed_devices: Set[str] = field(default_factory=lambda: set(DEFAULT_ALLOWED_DEVICES))
    min_temperature: float = DEFAULT_MIN_TEMPERATURE
    max_temperature: float = DEFAULT_MAX_TEMPERATURE

    def evaluate(self, request: ActionRequest) -> ActionReceipt | None:
        """Evaluate request against policy.

        Returns None if request is approved.
        Returns an ActionReceipt with status DENIED if rejected.
        """
        # 1. Device allowlist check
        if request.target_device_id not in self.allowed_devices:
            return ActionReceipt(
                action_id=f"denied-unregistered-{request.target_device_id}",
                target_device_id=request.target_device_id,
                action_type=request.action_type,
                status=ActionStatus.DENIED,
                message=f"拒絕操作：設備 '{request.target_device_id}' 未在家庭安全允許名單中。",
                details={"reason": "device_not_in_allowlist"},
            )

        # 2. Temperature boundary check
        supported = {
            "living_room_ac": {ActionType.TURN_ON, ActionType.TURN_OFF, ActionType.SET_TEMPERATURE},
            "living_room_light": {ActionType.TURN_ON, ActionType.TURN_OFF},
            "bedroom_light": {ActionType.TURN_ON, ActionType.TURN_OFF},
            "living_room_curtain": {ActionType.TURN_ON, ActionType.TURN_OFF, ActionType.SET_POSITION},
        }
        if request.action_type not in supported.get(request.target_device_id, set()):
            return ActionReceipt("denied-action", request.target_device_id, request.action_type,
                                 ActionStatus.DENIED, "不支援此設備操作。")
        if request.action_type == ActionType.SET_TEMPERATURE:
            temp = request.parameters.get("temperature")
            if temp is None:
                return ActionReceipt(
                    action_id=f"denied-missing-temp-{request.target_device_id}",
                    target_device_id=request.target_device_id,
                    action_type=request.action_type,
                    status=ActionStatus.DENIED,
                    message="拒絕操作：調節溫度指令缺少目標溫度數值。",
                    details={"reason": "missing_temperature"},
                )
            try:
                temp_val = float(temp)
            except (ValueError, TypeError):
                return ActionReceipt(
                    action_id=f"denied-invalid-temp-{request.target_device_id}",
                    target_device_id=request.target_device_id,
                    action_type=request.action_type,
                    status=ActionStatus.DENIED,
                    message=f"拒絕操作：無效的溫度數值 '{temp}'。",
                    details={"reason": "invalid_temperature_type"},
                )

            if not (self.min_temperature <= temp_val <= self.max_temperature):
                return ActionReceipt(
                    action_id=f"denied-temp-out-of-bounds-{request.target_device_id}",
                    target_device_id=request.target_device_id,
                    action_type=request.action_type,
                    status=ActionStatus.DENIED,
                    message=(
                        f"拒絕操作：設定溫度 {temp_val}°C 超出安全範圍 "
                        f"({self.min_temperature}°C ~ {self.max_temperature}°C)。"
                    ),
                    details={
                        "reason": "temperature_out_of_bounds",
                        "requested": temp_val,
                        "min": self.min_temperature,
                        "max": self.max_temperature,
                    },
                )

        # 3. Position boundary check (cover/curtain)
        if request.action_type == ActionType.SET_POSITION:
            pos = request.parameters.get("position")
            if type(pos) is not int:
                return ActionReceipt("denied-position", request.target_device_id, request.action_type,
                                     ActionStatus.DENIED, "窗簾開合度必須為 0 到 100 的整數。")
            if pos is not None:
                try:
                    pos_val = int(pos)
                    if not (0 <= pos_val <= 100):
                        return ActionReceipt(
                            action_id=f"denied-pos-bounds-{request.target_device_id}",
                            target_device_id=request.target_device_id,
                            action_type=request.action_type,
                            status=ActionStatus.DENIED,
                            message=f"拒絕操作：窗簾位置 {pos_val}% 超出範圍 (0% ~ 100%)。",
                            details={"reason": "position_out_of_bounds"},
                        )
                except (ValueError, TypeError):
                    return ActionReceipt(
                        action_id=f"denied-pos-invalid-{request.target_device_id}",
                        target_device_id=request.target_device_id,
                        action_type=request.action_type,
                        status=ActionStatus.DENIED,
                        message=f"拒絕操作：無效的窗簾開合度數值 '{pos}'。",
                        details={"reason": "invalid_position_type"},
                    )

        return None
