"""Rem character persona verbalization for both offline and online responses.

Provides authentic maid voice (devoted, gentle, third-person '雷姆', calling user '主人')
while strictly adhering to the repository constitution: zero hallucination, evidence-bound
facts, and truthful abstention.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Optional

from .actuation.models import ActionReceipt, ActionStatus, ActionType
from .presentation import (
    LocationPresenter,
    _display_name,
    _parse_context,
)

REM_PRESENTER_ID = "rem-persona-location/1"


class RemLocationPresenter(LocationPresenter):
    """Presents location contexts with Rem's devoted maid persona."""

    presenter_id = REM_PRESENTER_ID

    def present(self, context: Mapping[str, object]) -> str:
        parsed = _parse_context(context)
        subject = _display_name(parsed.subject_id)

        if parsed.status != "FOUND":
            if parsed.status == "UNKNOWN":
                return (
                    f"非常抱歉主人，雷姆翻遍了宅邸的記錄也沒有找到{subject}的蹤跡呢…"
                    f"這次沒能幫上您的忙，真的對不起。"
                )
            elif parsed.status == "CONFLICT":
                return (
                    f"主人，雷姆發現關於{subject}的位置記錄互相衝突呢…"
                    f"為了不誤導主人，雷姆不能胡亂猜測，請原諒雷姆。"
                )
            elif parsed.status == "FRONTIER_MISMATCH":
                return (
                    f"主人問的時間點超出了雷姆記錄的範圍呢，"
                    f"雷姆沒辦法告訴您那時候{subject}在哪裡。"
                )
            else:
                return (
                    f"主人，這個問題超出了雷姆目前所掌管的範圍，"
                    f"雷姆沒辦法回答您呢。"
                )

        assert parsed.location_id is not None
        location = _display_name(parsed.location_id)

        # Check relation facts for chain
        for inside in parsed.relation_facts:
            if inside.subject_id != parsed.subject_id or inside.predicate != "inside":
                continue
            for at_zone in parsed.relation_facts:
                if (
                    at_zone.subject_id == inside.object_id
                    and at_zone.predicate == "at_zone"
                    and at_zone.object_id == parsed.location_id
                ):
                    container = _display_name(inside.object_id)
                    return (
                        f"請交給雷姆吧！雷姆記得很清楚喔，主人的{subject}收在{container}裡面，"
                        f"而{container}現在正放在{location}上呢。請主人放心！"
                    )

        return f"報告主人！在雷姆的記憶中，您的{subject}目前位於{location}喔。"


def rem_voice_contents(contents: Mapping[str, object]) -> str:
    """Format container contents in Rem's voice."""
    container_id = str(contents.get("container") or contents.get("container_id", "容器"))
    container = _display_name(container_id)
    items = contents.get("items") or contents.get("contained_entity_ids") or []
    prep = "上" if ("沙發" in container or container_id == "sofa") else "裡面"
    action = "放著" if prep == "上" else "收納著"
    if items:
        item_names = "、".join(_display_name(str(i)) for i in items)
        return f"報告主人！在雷姆的記錄中，{container}{prep}正{action}{item_names}喔。"
    return f"報告主人，雷姆翻查了記錄，目前沒有記錄到{container}{prep}有存放任何物品呢。"


def rem_voice_verification(verification: Mapping[str, object], answer: Mapping[str, object]) -> str:
    """Format yes/no verification result in Rem's voice."""
    verdict = verification.get("verdict")
    subject_id = str(verification.get("subject_id", "物品"))
    subject = _display_name(subject_id)
    target_id = verification.get("target_id")
    target = _display_name(str(target_id)) if target_id else ""

    # Look up location chain from answer
    location_id = answer.get("location_id")
    location = _display_name(str(location_id)) if location_id else ""
    container = None
    for step in answer.get("relation_path") or []:
        if step.get("subject_id") == subject_id and step.get("predicate") == "inside":
            container = _display_name(str(step.get("object_id")))

    where = f"在{container}裡，且位於{location}" if container else f"位於{location}"

    if verdict == "YES":
        return f"是的，主人！雷姆可以確定，{subject}確實{where}喔。"
    elif verdict == "NO":
        return f"不對喔主人，在雷姆的記錄中，{subject}並不在{target}那裡，而是{where}呢。"
    elif verdict == "TARGET_UNKNOWN":
        target_str = f"您提到的「{target}」" if target else "您提到的那個位置"
        return f"報告主人，雷姆的記錄庫裡沒有記錄{target_str}，所以沒辦法確認呢。不過在雷姆的記錄中，{subject}{where}喔。"
    else:
        return f"非常抱歉主人，雷姆沒辦法判斷呢…因為記錄裡沒有足夠的有效證據可以定位{subject}。"


def rem_voice_actuation(receipt: ActionReceipt) -> str:
    """Format device action execution or denial into Rem's devoted maid voice."""
    target = receipt.target_device_id
    device_names = {
        "living_room_ac": "客廳冷氣",
        "living_room_light": "客廳大燈",
        "bedroom_light": "臥室電燈",
        "living_room_curtain": "客廳窗簾",
    }
    device_name = device_names.get(target, target)

    if receipt.status == ActionStatus.DENIED:
        reason = receipt.message
        if "超出安全" in reason or "temperature_out_of_bounds" in str(receipt.details.get("reason")):
            return (
                f"主人，請原諒雷姆…因為安全與舒適考量，冷氣溫度需要保持在 18°C 到 30°C 之間喔。"
                f"雷姆不能設定這個溫度，請主人多注意身體不要著涼了。"
            )
        elif "不支援" in reason or "不在允許清單" in reason:
            return f"主人，雷姆目前還沒辦法操控這項設備呢…請原諒雷姆。"
        return f"主人，請原諒雷姆…因為安全防護規範，{reason}，雷姆不能執行這個操作呢。"

    if receipt.status == ActionStatus.FAILED:
        return f"主人，非常抱歉，雷姆在操作{device_name}時遇到了問題：{receipt.message}"

    if receipt.action_type == ActionType.TURN_ON:
        if "ac" in target or "冷氣" in device_name:
            return f"好的，主人！{device_name} 已經為您開啟了，雷姆隨時為您調節舒適的室內溫度喔。"
        elif "curtain" in target or "窗簾" in device_name:
            return f"遵命！{device_name} 已經為您全部拉開了，讓明媚的陽光照進房間吧。"
        elif "light" in target or "燈" in device_name:
            return f"好的，主人！{device_name} 已經為您點亮了，光線隨時守護著您。"
        return f"好的，主人！{device_name} 已經為您開啟了喔。"

    elif receipt.action_type == ActionType.TURN_OFF:
        if "light" in target or "燈" in device_name:
            return f"{device_name} 已經為您關閉了，主人請好好放鬆休息，雷姆會隨時守護在您身邊的。"
        elif "curtain" in target or "窗簾" in device_name:
            return f"好的，主人！{device_name} 已經為您闔上了，請享受安靜的私人時光。"
        elif "ac" in target or "冷氣" in device_name:
            return f"{device_name} 已經為您關閉了喔，主人如果有需要請隨時吩咐雷姆。"
        return f"{device_name} 已經為您關閉了喔。"

    elif receipt.action_type == ActionType.SET_TEMPERATURE:
        temp = receipt.details.get("current_state", {}).get("temperature")
        if temp is None:
            m = re.search(r"(\d+(?:\.\d+)?)", receipt.message)
            temp = m.group(1) if m else "26.0"
        return f"遵命！{device_name} 已為您啟動並設定溫度為 {temp}°C，請主人好好享受舒適的溫度吧。"

    elif receipt.action_type == ActionType.SET_POSITION:
        pos = receipt.details.get("current_state", {}).get("position", "")
        return f"遵命！{device_name} 已經為您調整開合度至 {pos}% 了喔。"

    elif receipt.action_type == ActionType.SET_BRIGHTNESS:
        b = receipt.details.get("current_state", {}).get("attributes", {}).get("brightness", "")
        return f"遵命！{device_name} 已經為您調整亮度至 {b}% 了喔。"

    return f"好的，主人！{receipt.message}"


def rem_voice_refusal(question: str, reason: str = "", details: Optional[Mapping[str, object]] = None) -> str:
    """Format query refusals and errors into Rem's devoted maid voice."""
    q = question.strip().lower()

    if any(k in q for k in ("你是誰", "妳是誰", "自我介紹", "名字")):
        return (
            "雷姆是侍奉主人的專屬女僕喔！"
            "雷姆負責幫主人牢牢記住家中物品的位置，還能幫主人調整冷氣、開關燈光與拉開窗簾喔。"
            "有任何需要，請隨時吩咐雷姆！"
        )
    if any(k in q for k in ("妳會做什麼", "你會做什麼", "有什麼功能", "能做什麼", "你可以幹嘛", "妳可以幹嘛")):
        return (
            "雷姆會牢牢記住主人放在家裡的每樣東西！"
            "您可以詢問雷姆某個東西在哪裡、或者某個包包裡裝了什麼；"
            "雷姆也能幫您開關電燈、調整冷氣溫度與開關窗簾喔！"
        )
    if any(k in q for k in ("你好", "早安", "晚安", "午安", "雷姆")):
        return "主人，雷姆一直都在這裡等您喔！今天有什麼雷姆可以為您效勞的嗎？"

    if (details and details.get("matched_entity_count") == 0) or "must name exactly one known object" in reason:
        return (
            "非常抱歉主人，雷姆翻遍了記錄庫，並沒有找到關於這項物品的記錄呢…"
            "雷姆不會憑空猜測，目前記憶中只記著鑰匙、包包與沙發的位置喔。"
        )
    if details and details.get("matched_entity_count", 0) > 1:
        return (
            "主人，雷姆一次只能專心為您尋找一樣物品呢！"
            "請您一樣一樣分開詢問雷姆好嗎？"
        )
    if "only bounded object-location questions are supported" in reason or "unsupported_question" in reason:
        return (
            "主人，時間或天氣等外面的事情雷姆目前幫不上忙呢…"
            "但如果是找家裡的物品（如鑰匙、包包）或打理冷氣與電燈，請儘管交給雷姆吧！"
        )

    return (
        "非常抱歉主人，雷姆沒能完全理解您的意思…"
        "您可以詢問雷姆物品的位置，或是吩咐雷姆操作家電喔。"
    )
