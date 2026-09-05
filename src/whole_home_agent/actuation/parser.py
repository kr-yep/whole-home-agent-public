"""Deterministic natural language parser for smart device actuation commands."""

from __future__ import annotations

import re
from typing import Optional

from .models import ActionRequest, ActionType


# Regex patterns for Chinese & English command recognition
_RE_AC_TEMP = re.compile(
    r"(?:冷氣|空調|ac|air\s*conditioner).*?(?:設為|調到|設至|調成|到|為|set\s*(?:ac|temperature)?\s*to)?\s*((?<![\d.])[+-]?\d+(?:\.\d+)?)(?![\d.])\s*(?:度|°c|°|c)?",
    re.IGNORECASE,
)
_RE_COVER_POS = re.compile(
    r"(?:窗簾|curtain|blind).*?(?:設為|開到|拉到|至|set\s*(?:curtain)?\s*to)?\s*(\d{1,3})\s*%",
    re.IGNORECASE,
)


def parse_action_command(text: str) -> Optional[ActionRequest]:
    """Parse natural language command text into an ActionRequest.

    Returns ActionRequest if text is recognized as an action command, or None if not.
    """
    raw = text.strip()
    lower = raw.lower()

    # Questions, negation, and multi-command sentences must never become actions.
    if any(word in lower for word in (
        "不要", "別", "不想", "不能", "別再", "是否", "嗎", "？", "?",
        "don't", "do not", "never", "not ", "is ", "why ", "how ",
        "然後", "同時", "以及", " and ",
    )):
        return None

    # 1. Check Temperature adjustment for Climate
    match_temp = _RE_AC_TEMP.search(lower)
    if match_temp and ("設" in raw or "調" in raw or "度" in raw or "to" in lower or "°" in raw):
        try:
            temp_val = float(match_temp.group(1))
            return ActionRequest(
                target_device_id="living_room_ac",
                action_type=ActionType.SET_TEMPERATURE,
                parameters={"temperature": temp_val},
            )
        except ValueError:
            pass

    # 2. Check Curtain Position percentage
    match_pos = _RE_COVER_POS.search(lower)
    if match_pos and "%" in raw:
        try:
            pos_val = int(match_pos.group(1))
            return ActionRequest(
                target_device_id="living_room_curtain",
                action_type=ActionType.SET_POSITION,
                parameters={"position": pos_val},
            )
        except ValueError:
            pass

    # 3. Check Climate ON/OFF
    if any(kw in lower for kw in ("冷氣", "空調", "air conditioner")) or (
        "ac" in lower and any(act in lower for act in ("turn", "switch", "open", "close", "on", "off"))
    ):
        if any(act in lower for act in ("開", "打開", "啟動", "turn on", "switch on")):
            return ActionRequest(
                target_device_id="living_room_ac",
                action_type=ActionType.TURN_ON,
            )
        if any(act in lower for act in ("關", "關掉", "關閉", "熄", "turn off", "switch off")):
            return ActionRequest(
                target_device_id="living_room_ac",
                action_type=ActionType.TURN_OFF,
            )

    # 4. Check Lights ON/OFF
    if any(kw in lower for kw in ("燈", "照明", "light")):
        # Check specific room
        target_light = "living_room_light"
        if any(room in lower for room in ("臥室", "房間", "bedroom")):
            target_light = "bedroom_light"

        if any(act in lower for act in ("開", "打開", "點亮", "turn on", "switch on")):
            return ActionRequest(
                target_device_id=target_light,
                action_type=ActionType.TURN_ON,
            )
        if any(act in lower for act in ("關", "關掉", "關閉", "熄", "turn off", "switch off")):
            return ActionRequest(
                target_device_id=target_light,
                action_type=ActionType.TURN_OFF,
            )

    # 5. Check Curtains OPEN/CLOSE
    if any(kw in lower for kw in ("窗簾", "curtain", "blind")):
        if any(act in lower for act in ("開", "打開", "拉開", "開啟", "open")):
            return ActionRequest(
                target_device_id="living_room_curtain",
                action_type=ActionType.SET_POSITION,
                parameters={"position": 100},
            )
        if any(act in lower for act in ("關", "拉上", "闔上", "關閉", "close")):
            return ActionRequest(
                target_device_id="living_room_curtain",
                action_type=ActionType.SET_POSITION,
                parameters={"position": 0},
            )

    return None
