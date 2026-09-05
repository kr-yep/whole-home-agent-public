"""One-command launcher for the Whole-Home Visual Memory Agent.

    python start.py

Does, in order:

1. Check the Python version and that the package is actually installed.
2. Build the demo memory archive if it is missing.
3. Fetch the character artwork, which is deliberately outside version control.
4. Download the vision model weights, if the vision extras are installed.
5. Start the local LLM persona service, then the web application.

Steps 1 to 3 are the same ones tools/setup_demo.py performs, imported from there
rather than written twice, so the two entry points cannot drift apart.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
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

# The server resolves its database from a relative path, so it looks in whatever
# directory it was started from. Without this, launching from elsewhere builds the
# archive here and then looks for it there, and the second one is empty.
os.chdir(ROOT)

sys.path.insert(0, str(ROOT / "tools"))
import setup_demo  # noqa: E402  (needs the path entry above)

LLM_PORT = 8001
OLLAMA_PORT = 11434


def _check_python() -> None:
    if sys.version_info < (3, 11):
        print(f"[ERROR] Python >= 3.11 is required. Current: {sys.version.split()[0]}", file=sys.stderr)
        sys.exit(1)


def _prepare_repository() -> None:
    """Everything the pages need before a server is worth starting."""

    print("[1/4] [*] 檢查安裝與素材 (Checking install and assets)...")
    if not setup_demo.check_package():
        # Carrying on from here would print a success banner, open a browser and
        # then fail on the first import of the package. Stop where the problem is.
        print()
        # stderr is unbuffered and stdout is not when this is piped, so without
        # a flush the error lands above the instructions it refers to.
        sys.stdout.flush()
        print("      [ERROR] 尚未安裝本套件，無法啟動。請先執行上方任一指令後重試。", file=sys.stderr)
        sys.exit(1)
    setup_demo.ensure_memory(fetch=True)
    setup_demo.ensure_artwork(fetch=True)


def _prewarm_models() -> None:
    print("[2/4] [*] 檢查視覺模型與特徵擷取器 (Checking Models)...")
    try:
        from ultralytics import YOLO

        model_name = os.environ.get("WHA_YOLO_MODEL", "yolov8m.pt")
        if not Path(model_name).exists():
            print(f"      [*] 正在自動下載 YOLO 偵測模型權重 ({model_name}，約 50 MB)...")
        YOLO(model_name)
        print(f"      [OK] YOLO 偵測模型就緒 ({model_name})")
    except ImportError:
        print("      [INFO] 未安裝 ultralytics；若需即時物件偵測，可執行: pip install -r requirements-vision.txt")
    except Exception as err:
        print(f"      [WARN] YOLO 模型載入提示: {err}")

    try:
        import torchvision.models as models

        print("      [*] 檢查 MobileNetV3 特徵擷取模型...")
        models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
        print("      [OK] MobileNetV3 特徵擷取器就緒 (支援即時樣本學習)")
    except ImportError:
        print("      [INFO] 未安裝 torchvision；系統將自動啟用 512 維色彩空間紋理特徵備援。")
    except Exception as err:
        print(f"      [WARN] MobileNetV3 提示 (將自動使用色彩紋理備援): {err}")


def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_port(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _is_port_open(port):
            return True
        time.sleep(0.1)
    return False


def _start_llm_service() -> subprocess.Popen | None:
    print("[3/4] [*] 啟動本地 LLM 角色服務 (Local LLM Service)...")
    if _is_port_open(LLM_PORT):
        print(f"      [OK] 本地 LLM 服務已在埠 {LLM_PORT} 運行")
        return None
    if _is_port_open(OLLAMA_PORT):
        print(f"      [OK] 偵測到 Ollama 服務已在埠 {OLLAMA_PORT} 運行")
        return None

    script = ROOT / "tools" / "local_llm_service.py"
    if not script.exists():
        print("      [INFO] 未找到 local_llm_service.py，將使用內建角色規則備援")
        return None

    # Its output is kept rather than discarded: a service that dies on startup is
    # the case worth reporting, and with stderr sent to DEVNULL it looks exactly
    # like one that came up.
    process = subprocess.Popen(
        [sys.executable, str(script), "--port", str(LLM_PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if _wait_for_port(LLM_PORT, timeout=8.0):
        print(f"      [OK] 本地 LLM 服務已啟動 (PID: {process.pid}, Port: {LLM_PORT})")
        return process

    process.terminate()
    try:
        _, complaint = process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        complaint = b""
    print(f"      [WARN] 本地 LLM 服務未能在埠 {LLM_PORT} 上就緒，改用內建角色規則備援")
    for line in complaint.decode("utf-8", "replace").strip().splitlines()[-3:]:
        print(f"             {line}")
    return None


def _open_when_ready(url: str, port: int) -> None:
    """The server blocks once started, so the browser is opened from beside it."""

    if _wait_for_port(port, timeout=15.0):
        webbrowser.open(url)


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
    _prepare_repository()
    _prewarm_models()
    llm_process = _start_llm_service()

    camera_url = f"http://{arguments.bind}:{arguments.port}/camera"
    chat_url = f"http://{arguments.bind}:{arguments.port}/"

    print(f"[4/4] [*] 啟動 Web 伺服器 (http://{arguments.bind}:{arguments.port})...")
    print()
    print("=" * 65)
    print("   [相機辨識與物件註冊] " + camera_url)
    print("   [雷姆 (Rem) 對話主頁] " + chat_url)
    print("   (按 Ctrl+C 可停止伺服器)")
    print("=" * 65)
    print()

    if not arguments.no_browser:
        threading.Thread(
            target=_open_when_ready, args=(camera_url, arguments.port), daemon=True
        ).start()

    try:
        from whole_home_agent.web_app import main as web_main

        sys.argv = [sys.argv[0], "--bind", arguments.bind, "--port", str(arguments.port)]
        web_main()
    except KeyboardInterrupt:
        print("\n伺服器已正常停止。")
    finally:
        if llm_process is not None:
            llm_process.terminate()


if __name__ == "__main__":
    main()
