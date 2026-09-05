"""Typed data models and enums for home device actuation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class DeviceType(str, Enum):
    """Supported smart home device categories."""

    CLIMATE = "climate"  # 冷氣/空調
    LIGHT = "light"  # 電燈/照明
    COVER = "cover"  # 窗簾/捲簾
    SWITCH = "switch"  # 開關/插座


class ActionType(str, Enum):
    """Normalized action operations that can be performed on devices."""

    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    TOGGLE = "toggle"
    SET_TEMPERATURE = "set_temperature"
    SET_POSITION = "set_position"


class ActionStatus(str, Enum):
    """Execution verdict for an actuation request."""

    EXECUTED = "executed"  # Successfully executed on physical hardware
    SIMULATED = "simulated"  # Successfully executed in memory/mock
    DENIED = "denied"  # Rejected by safety policy or permissions
    FAILED = "failed"  # Failed due to hardware/network error


@dataclass(frozen=True)
class ActionRequest:
    """Immutable request to perform an action on a target device."""

    target_device_id: str
    action_type: ActionType
    parameters: Mapping[str, Any] = field(default_factory=dict)
    requester: str = "user"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(frozen=True)
class ActionReceipt:
    """Verifiable execution receipt returned by the actuator port."""

    action_id: str
    target_device_id: str
    action_type: ActionType
    status: ActionStatus
    message: str
    executed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    details: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return {
            "action_id": self.action_id,
            "target_device_id": self.target_device_id,
            "action_type": self.action_type.value,
            "status": self.status.value,
            "message": self.message,
            "executed_at": self.executed_at,
            "details": dict(self.details),
        }


@dataclass
class DeviceState:
    """Current observable state of a device."""

    device_id: str
    device_type: DeviceType
    name: str
    room: str
    is_on: bool = False
    temperature: float | None = None  # Applicable for CLIMATE
    position: int | None = None  # Applicable for COVER (0 = closed, 100 = fully open)
    attributes: dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "name": self.name,
            "room": self.room,
            "is_on": self.is_on,
            "temperature": self.temperature,
            "position": self.position,
            "attributes": self.attributes,
            "updated_at": self.updated_at,
        }
