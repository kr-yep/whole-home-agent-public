"""Home Assistant REST API actuator for physical smart home device integration."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

from whole_home_agent.actuation.models import (
    ActionReceipt,
    ActionRequest,
    ActionStatus,
    ActionType,
    DeviceState,
    DeviceType,
)
from whole_home_agent.actuation.port import ActuatorPort


# Default mapping from local device IDs to Home Assistant entity_ids
DEFAULT_ENTITY_MAPPING = {
    "living_room_ac": ("climate.living_room_ac", DeviceType.CLIMATE, "客廳冷氣", "客廳"),
    "living_room_light": ("light.living_room_light", DeviceType.LIGHT, "客廳大燈", "客廳"),
    "bedroom_light": ("light.bedroom_light", DeviceType.LIGHT, "臥室電燈", "臥室"),
    "living_room_curtain": ("cover.living_room_curtain", DeviceType.COVER, "客廳窗簾", "客廳"),
}


class HomeAssistantActuator(ActuatorPort):
    """Actuator adapter communicating with a real Home Assistant instance via REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        timeout: float = 3.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("HASS_URL", "http://homeassistant.local:8123")).rstrip("/")
        self.bearer_token = bearer_token or os.environ.get("HASS_TOKEN", "")
        self.timeout = timeout
        self._mapping = DEFAULT_ENTITY_MAPPING

    def _request(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> tuple[int, Any]:
        """Make an HTTP request to Home Assistant REST API."""
        if not self.bearer_token:
            return 401, {"error": "HASS_TOKEN is not configured"}

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }
        payload = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=payload, headers=headers)
        if data is None:
            req.method = "GET"

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                body = json.loads(resp.read().decode("utf-8"))
                return status, body
        except urllib.error.HTTPError as e:
            return e.code, {"error": str(e)}
        except Exception as e:
            return 0, {"error": str(e)}

    def get_device_state(self, device_id: str) -> Optional[DeviceState]:
        info = self._mapping.get(device_id)
        if not info:
            return None
        entity_id, dev_type, name, room = info
        status_code, body = self._request(f"/api/states/{entity_id}")
        if status_code != 200:
            return DeviceState(
                device_id=device_id,
                device_type=dev_type,
                name=name,
                room=room,
                is_on=False,
                attributes={"connection_status": "disconnected"},
            )

        state_str = body.get("state", "off")
        attrs = body.get("attributes", {})
        is_on = state_str not in ("off", "closed", "unavailable")

        temp = attrs.get("temperature") or attrs.get("current_temperature")
        pos = attrs.get("current_position")

        return DeviceState(
            device_id=device_id,
            device_type=dev_type,
            name=name,
            room=room,
            is_on=is_on,
            temperature=float(temp) if temp is not None else None,
            position=int(pos) if pos is not None else None,
            attributes=attrs,
        )

    def list_devices(self) -> List[DeviceState]:
        results = []
        for dev_id in self._mapping:
            st = self.get_device_state(dev_id)
            if st:
                results.append(st)
        return results

    def execute(self, request: ActionRequest) -> ActionReceipt:
        info = self._mapping.get(request.target_device_id)
        receipt_id = f"act-ha-{uuid.uuid4().hex[:8]}"

        if not info:
            return ActionReceipt(
                action_id=receipt_id,
                target_device_id=request.target_device_id,
                action_type=request.action_type,
                status=ActionStatus.FAILED,
                message=f"執行失敗：找不到 Home Assistant 對應實體 '{request.target_device_id}'",
                details={"error": "entity_unmapped"},
            )

        entity_id, dev_type, name, _ = info

        # If no access token is set, return a graceful failure receipt explaining how to configure it
        if not self.bearer_token:
            return ActionReceipt(
                action_id=receipt_id,
                target_device_id=request.target_device_id,
                action_type=request.action_type,
                status=ActionStatus.FAILED,
                message=(
                    f"無法控制實體設備 {name}：尚未設定 Home Assistant Access Token。\n"
                    "請在環境變數中提供 HASS_TOKEN 或改用 MockActuator。"
                ),
                details={"error": "missing_token"},
            )

        # Route action to Home Assistant service domain
        domain = entity_id.split(".")[0]
        service = ""
        service_data: Dict[str, Any] = {"entity_id": entity_id}

        if request.action_type == ActionType.TURN_ON:
            service = "turn_on" if domain != "cover" else "open_cover"
        elif request.action_type == ActionType.TURN_OFF:
            service = "turn_off" if domain != "cover" else "close_cover"
        elif request.action_type == ActionType.SET_TEMPERATURE:
            service = "set_temperature"
            service_data["temperature"] = float(request.parameters["temperature"])
        elif request.action_type == ActionType.SET_POSITION:
            pos = int(request.parameters.get("position", 100))
            if pos == 100:
                service = "open_cover"
            elif pos == 0:
                service = "close_cover"
            else:
                service = "set_cover_position"
                service_data["position"] = pos

        code, resp = self._request(f"/api/services/{domain}/{service}", service_data)
        if code == 200:
            return ActionReceipt(
                action_id=receipt_id,
                target_device_id=request.target_device_id,
                action_type=request.action_type,
                status=ActionStatus.EXECUTED,
                message=f"實體設備 {name} 操作成功（Home Assistant 服務 {domain}.{service} 已觸發）。",
                details={"response": resp},
            )
        else:
            return ActionReceipt(
                action_id=receipt_id,
                target_device_id=request.target_device_id,
                action_type=request.action_type,
                status=ActionStatus.FAILED,
                message=f"實體設備 {name} 操作失敗：HTTP {code} ({resp.get('error', 'unknown')})",
                details={"http_status": code, "error": resp},
            )
