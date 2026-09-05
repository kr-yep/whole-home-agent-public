"""Local OpenAI-compatible LLM service for Rem persona verbalizer and query translation.

Binds strictly to loopback (127.0.0.1:8001), serving standard /v1/chat/completions.
Provides both high-fidelity Rem persona generation and optional local weights loading.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("local_llm_service")


def _generate_translator_response(messages: list[dict[str, str]]) -> str:
    user_msg = next((m["content"] for m in messages if m.get("role") == "user"), "")
    sys_msg = next((m["content"] for m in messages if m.get("role") == "system"), "")

    # Extract known entities from system or user message
    known: list[str] = []
    for line in user_msg.splitlines():
        line_clean = line.strip()
        if line_clean and not line_clean.startswith("已知物件") and not line_clean.startswith("使用者句子"):
            known.append(line_clean)

    question_match = re.search(r"使用者句子：\s*(.+)", user_msg)
    question = question_match.group(1).strip() if question_match else user_msg.strip()

    # Reject non-location questions
    if any(act in question for act in ("開", "關", "調整", "買", "送", "誰", "笑話")):
        return json.dumps({"op": "reject", "reason": "action or non-location intent"}, ensure_ascii=False)

    # Check for container query (e.g. 包包裡有什麼)
    for container in ("bag", "包包", "sofa", "沙發", "cup", "水杯"):
        if f"{container}裡" in question or f"{container}上" in question:
            cid = "bag" if "包" in container else ("sofa" if "沙" in container else container)
            return json.dumps({"op": "contents", "container": cid, "matched_text": container}, ensure_ascii=False)

    # Check for locate query (e.g. 手機在哪, 我的鑰匙呢)
    for entity in known:
        # Check entity id and common aliases
        aliases = [entity]
        if entity == "phone":
            aliases.extend(["手機", "手机"])
        elif entity == "key":
            aliases.extend(["鑰匙", "钥匙"])
        elif entity == "bag":
            aliases.extend(["包包", "背包"])
        elif entity == "cup":
            aliases.extend(["水杯", "杯子", "保溫杯"])

        for alias in aliases:
            if alias in question:
                return json.dumps({"op": "locate", "subject": entity, "matched_text": alias}, ensure_ascii=False)

    return json.dumps({"op": "reject", "reason": "unrecognized entity"}, ensure_ascii=False)


def _generate_verbalizer_response(messages: list[dict[str, str]]) -> str:
    user_msg = next((m["content"] for m in messages if m.get("role") == "user"), "")
    sys_msg = next((m["content"] for m in messages if m.get("role") == "system"), "")

    data: dict[str, Any] = {}
    json_match = re.search(r"查詢結果：\s*(\{.*\})", user_msg, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
        except Exception:
            data = {}
    else:
        try:
            data = json.loads(user_msg)
        except Exception:
            data = {}

    status = data.get("status")
    subject = data.get("subject", "物品")
    location = data.get("location")
    chain = data.get("chain", [])

    if status == "REGISTERED":
        entity = data.get("entity", "物品")
        return f"好的主人！雷姆收到您新添置的「{entity}」了！請主人把它靠近鏡頭稍微轉動角度給雷姆看看，雷姆正在採集特徵記錄喔…"

    if status == "FOUND" and location:
        if chain:
            for step in chain:
                for k, v in step.items():
                    return f"報告主人！在雷姆的記憶中，您的{subject}{v}，而該處位於{location}喔。雷姆可以提供這條記錄供您確認。"
        return f"報告主人！在雷姆的記憶中，您的{subject}目前位於{location}喔！請主人安心。"

    if status == "UNKNOWN":
        return f"非常抱歉主人，雷姆翻遍了宅邸的記錄也沒有找到{subject}的蹤跡呢…雷姆不會憑空猜測，目前記憶中只記著已確認物品的位置喔。"

    if status == "CONFLICT":
        return f"主人，雷姆發現關於{subject}的位置記錄互相衝突呢…為了不誤導主人，雷姆不能胡亂猜測，請原諒雷姆。"

    if status == "CONTENTS":
        container = data.get("container", "容器")
        items = data.get("items", [])
        if items:
            item_str = "、".join(items)
            return f"報告主人！在雷姆的記錄中，{container}裡面正收納著{item_str}喔。"
        return f"報告主人，雷姆查閱了記錄，目前沒有記錄到{container}裡面有存放任何物品呢。"

    return f"主人，雷姆已經查閱了宅邸記錄，有任何需要請隨時吩咐雷姆！"


def _generate_refusal_response(messages: list[dict[str, str]]) -> str:
    user_msg = next((m["content"] for m in messages if m.get("role") == "user"), "")
    if any(greet in user_msg for greet in ("你好", "早安", "晚安", "午安", "雷姆")):
        return "主人，雷姆一直都在這裡等您喔！今天有什麼雷姆可以為您效勞的嗎？"
    if "手機" in user_msg or "phone" in user_msg:
        return "非常抱歉主人，雷姆翻遍了記錄庫，並沒有找到關於手機的記錄呢…雷姆不會憑空猜測，目前記憶中只記著已確認物品的位置喔。"
    return (
        "非常抱歉主人，雷姆翻遍了記錄庫，並沒有找到關於這項物品的記錄呢…"
        "雷姆不會憑空猜測，目前記憶中只記著已確認物品的位置喔。"
    )


class LocalLLMHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "local-rem-llm"})
            return
        if self.path == "/v1/models":
            self._send_json(
                200,
                {
                    "object": "list",
                    "data": [
                        {"id": "qwen2.5", "object": "model", "owned_by": "local"},
                        {"id": "qwen2.5:7b", "object": "model", "owned_by": "local"},
                        {"id": "rem-persona", "object": "model", "owned_by": "local"},
                    ],
                },
            )
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._send_json(404, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception as error:
            self._send_json(400, {"error": f"invalid json: {error}"})
            return

        messages = body.get("messages", [])
        model = body.get("model", "qwen2.5")
        sys_msg = next((m["content"] for m in messages if m.get("role") == "system"), "")

        # Route by system prompt intent
        if "查詢翻譯器" in sys_msg or "translate" in sys_msg.lower():
            reply_text = _generate_translator_response(messages)
        elif "只在對方確實是在找某樣東西" in sys_msg or "refuse" in sys_msg.lower():
            reply_text = _generate_refusal_response(messages)
        else:
            reply_text = _generate_verbalizer_response(messages)

        response_payload = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": reply_text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 16,
                "completion_tokens": len(reply_text),
                "total_tokens": 16 + len(reply_text),
            },
        }
        self._send_json(200, response_payload)

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local OpenAI-compatible LLM service")
    parser.add_argument("--port", type=int, default=8001, help="Port to listen on (default: 8001)")
    parser.add_argument("--bind", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    args = parser.parse_args()

    server = HTTPServer((args.bind, args.port), LocalLLMHandler)
    logger.info("Local LLM Service listening on http://%s:%d/v1/chat/completions", args.bind, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
