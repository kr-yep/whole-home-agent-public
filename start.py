"""One-command launcher for Whole-Home Visual Memory Agent.

Usage:
    python start.py

Automates:
1. Verifying Python version (>= 3.11).
2. Auto-initializing demo SQLite visual memory if missing.
3. Pre-warming/downloading YOLO and MobileNetV3 weights if vision dependencies exist.
4. Starting local LLM persona service (port 8001).
5. Starting Web application (port 8600).
6. Opening browser to the Camera Vision page.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Safeguard Windows CP950/locale terminal output encoding
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / ".whole-home-agent" / "demo-memory.sqlite3"


def _check_python() -> None:
    if sys.version_info < (3, 11):
        print(f"[ERROR] Python >= 3.11 is required. Current: {sys.version.split()[0]}", file=sys.stderr)
        sys.exit(1)


def _init_demo_database() -> None:
    if not DEFAULT_DB.exists():
        print("[1/4] [*] 初始化展示記憶資料庫 (Initializing Demo Memory SQLite)...")
        DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)
        try:
            from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
            from whole_home_agent.public_demo import run_public_demo

            run_public_demo(
                replay_run_id="web-demo-001",
                include_frames=False,
                archive=SQLiteReplayArchive(DEFAULT_DB),
            )
            print(f"      [OK] 資料庫已建立: {DEFAULT_DB}")
        except Exception as err:
            print(f"      [WARN] 資料庫初始化失敗: {err}")
    else:
        print(f"[1/4] [OK] 展示記憶資料庫就緒: {DEFAULT_DB}")


def _prewarm_models() -> None:
    print("[2/4] [*] 檢查視覺模型與特徵擷取器 (Checking Models)...")
    try:
        from ultralytics import YOLO

        model_name = os.environ.get("WHA_YOLO_MODEL", "yolov8m.pt")
        model_file = ROOT / model_name
        if not model_file.exists():
            print(f"      [*] 正在自動下載 YOLO 偵測模型權重 ({model_name})...")
        _yolo = YOLO(model_name)
        print(f"      [OK] YOLO 偵測模型就緒 ({model_name})")
    except ImportError:
        print("      [INFO] 未安裝 ultralytics；若需實體鏡頭 YOLO 偵測，可執行: pip install -r requirements-vision.txt")
    except Exception as err:
        print(f"      [WARN] YOLO 模型載入提示: {err}")

    try:
        import torch
        import torchvision.models as models

        print("      [*] 檢查 MobileNetV3 特徵擷取模型...")
        _m = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
        print("      [OK] MobileNetV3 特徵擷取器就緒 (支援即時樣本學習)")
    except ImportError:
        print("      [INFO] 未安裝 torchvision；系統將自動啟用 512 維色彩空間紋理特徵備援。")
    except Exception as err:
        print(f"      [WARN] MobileNetV3 提示 (將自動使用色彩紋理備援): {err}")


def _is_port_open(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _start_llm_service() -> subprocess.Popen | None:
    print("[3/4] [*] 啟動本地 LLM 角色服務 (Local LLM Service)...")
    if _is_port_open(8001):
        print("      [OK] 本地 LLM 服務已在埠 8001 運行")
        return None
    if _is_port_open(11434):
        print("      [OK] 偵測到 Ollama 服務已在埠 11434 運行")
        return None

    llm_script = ROOT / "tools" / "local_llm_service.py"
    if llm_script.exists():
        proc = subprocess.Popen(
            [sys.executable, str(llm_script), "--port", "8001"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.8)
        print(f"      [OK] 本地 LLM 服務已啟動 (PID: {proc.pid}, Port: 8001)")
        return proc
    print("      [INFO] 未找到 local_llm_service.py，將使用內建角色規則備援")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Whole-Home Visual Memory Agent Launcher")
    parser.add_argument("--port", type=int, default=8600, help="Web UI port (default: 8600)")
    parser.add_argument("--bind", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    arguments = parser.parse_args()

    print("=" * 65)
    print("   Whole-Home Visual Memory Agent 一鍵啟動精靈")
    print("=" * 65)

    _check_python()
    _init_demo_database()
    _prewarm_models()
    llm_proc = _start_llm_service()

    print(f"[4/4] [*] 啟動 Web 伺服器 (http://{arguments.bind}:{arguments.port})...")
    app_url = f"http://{arguments.bind}:{arguments.port}/camera.html"
    chat_url = f"http://{arguments.bind}:{arguments.port}/"

    print("\n" + "=" * 65)
    print(f"   [SUCCESS] 系統已成功就緒！請存取以下網址：")
    print(f"   [相機辨識與物件註冊] {app_url}")
    print(f"   [蕾姆 (Rem) 對話主頁] {chat_url}")
    print("   (按 Ctrl+C 可停止伺服器)")
    print("=" * 65 + "\n")

    if not arguments.no_browser:
        time.sleep(0.5)
        webbrowser.open(app_url)

    try:
        from whole_home_agent.web_app import main as web_main

        sys.argv = [sys.argv[0], "--bind", arguments.bind, "--port", str(arguments.port)]
        web_main()
    except KeyboardInterrupt:
        print("\n伺服器已正常停止。")
    finally:
        if llm_proc is not None:
            llm_proc.terminate()


if __name__ == "__main__":
    main()
