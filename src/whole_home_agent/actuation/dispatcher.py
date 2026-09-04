"""Command dispatcher that routes user input to either action execution or passes through."""

from __future__ import annotations

from typing import Optional

from .models import ActionReceipt, ActionRequest
from .parser import parse_action_command
from .policy import ActionPolicy
from .port import ActuatorPort


class CommandDispatcher:
    """Dispatches natural language commands to smart device actuation if applicable."""

    def __init__(
        self,
        actuator: ActuatorPort,
        policy: ActionPolicy | None = None,
    ) -> None:
        self.actuator = actuator
        self.policy = policy or ActionPolicy()

    def dispatch(self, text: str) -> Optional[ActionReceipt]:
        """Attempt to parse and execute a device action command.

        Returns ActionReceipt if text was recognized as an actuation command.
        Returns None if text is not an actuation command (so caller can route to memory query).
        """
        request = parse_action_command(text)
        if request is None:
            return None

        # 1. Evaluate safety policy
        denial = self.policy.evaluate(request)
        if denial is not None:
            return denial

        # 2. Execute on actuator port
        return self.actuator.execute(request)
