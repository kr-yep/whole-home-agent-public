"""Abstract port interface for smart home device actuators."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import ActionReceipt, ActionRequest, DeviceState


@runtime_checkable
class ActuatorPort(Protocol):
    """Port defining the interaction boundary with device execution backends.

    Any implementation (Mock, Home Assistant, SwitchBot, Matter) must implement
    these three methods. The domain orchestrator interacts only through this protocol.
    """

    def execute(self, request: ActionRequest) -> ActionReceipt:
        """Execute or simulate an action request and return a verifiable receipt."""
        ...

    def get_device_state(self, device_id: str) -> DeviceState | None:
        """Return the current known state of a device by ID, or None if unknown."""
        ...

    def list_devices(self) -> list[DeviceState]:
        """Return states for all registered and controllable devices."""
        ...
