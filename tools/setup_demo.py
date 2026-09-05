"""Get a fresh checkout from cloned to running, in one command.

A teammate cloned this and reported the character missing. The tooling was there
-- a fetcher, a page that says what it needs, two READMEs that mention it -- and
it still did not happen, which makes it a workflow problem rather than a
documentation one. Being told what to run next is worse than not needing to be.

So this does every step in order, says what it did, and is safe to run again. It
never overwrites artwork that is already present and never rebuilds a memory
archive that already exists, so running it twice costs a few seconds and changes
nothing.

    python tools/setup_demo.py            check, fetch what is missing, then report
    python tools/setup_demo.py --run      the same, then start the server
    python tools/setup_demo.py --check    report only; fetch nothing

Standard library only, matching the rest of the package.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_DATABASE = ROOT / ".whole-home-agent" / "demo-memory.sqlite3"
REM_MARKER = ROOT / "web" / "live2d" / "rem" / "REM.model3.json"
NAILONG_IMAGE = ROOT / "web" / "characters" / "nailong" / "idle.png"

OK = "  ok    "
DO = "  doing "
GAP = "  note  "


def _has(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def check_package() -> bool:
    """Is the package importable from wherever this interpreter is looking?"""

    if _has("whole_home_agent"):
        print(f"{OK}package is importable")
        return True
    print(f"{GAP}package is not installed for {sys.executable}")
    print("        install it first, for example:")
    print("          uv pip install -e '.[demo,video]'")
    print("        or:")
    print("          python -m pip install -e '.[demo,video]'")
    return False


def check_optional() -> None:
    """The extras change what works, so say which are present rather than assume."""

    for module, what in (
        ("av", "video decoding (the recorded replay)"),
        ("PIL", "image encoding (camera frames in tests)"),
        ("numpy", "array handling"),
        ("onnxruntime", "the portable detector (camera recognition without PyTorch)"),
        ("ultralytics", "the PyTorch detector (GPU where there is one)"),
        ("streamlit", "the Streamlit page (the web page does not need it)"),
    ):
        mark = OK if _has(module) else GAP
        state = "present" if _has(module) else "absent"
        print(f"{mark}{module:<12} {state:<8} {what}")


def ensure_memory(fetch: bool) -> bool:
    """The demo answers from a generated replay; without it there is nothing to ask."""

    if DEMO_DATABASE.exists():
        print(f"{OK}demo memory present ({DEMO_DATABASE.stat().st_size // 1024} KB)")
        return True
    if not fetch:
        print(f"{GAP}demo memory missing; run without --check to build it")
        return False
    print(f"{DO}building the demo memory from the included synthetic replay")
    from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
    from whole_home_agent.public_demo import run_public_demo

    DEMO_DATABASE.parent.mkdir(parents=True, exist_ok=True)
    result = run_public_demo(
        replay_run_id="setup-demo-001",
        include_frames=False,
        archive=SQLiteReplayArchive(DEMO_DATABASE),
    )
    print(f"{OK}demo memory built ({result['archive']['status']})")
    return True


def ensure_vision_model(fetch: bool) -> None:
    """Recognition needs weights, and which weights depends on what will install.

    Where Ultralytics is present it fetches its own and there is nothing to do.
    Often it cannot be present: it needs PyTorch, and PyTorch publishes one macOS
    wheel per release, for arm64 on Sonoma or newer, so an Intel Mac has no wheel
    to install and the build from source does not finish. On those machines the
    ONNX export of the same model runs under onnxruntime, whose wheels reach back
    to macOS 11 -- see tools/fetch_vision_model.py.
    """

    if _has("ultralytics") and _has("torch"):
        print(f"{OK}PyTorch detector available; Ultralytics fetches its own weights")
        return

    import fetch_vision_model

    name = fetch_vision_model.DEFAULT_MODEL
    target = fetch_vision_model.model_path(name)
    megabytes = fetch_vision_model.WEIGHTS[name][0] // (1 << 20)

    if not _has("onnxruntime"):
        print(f"{GAP}no detector runtime installed, so the camera page shows the")
        print("        picture and recognises nothing in it. To fix that:")
        print("          uv pip install -r requirements-vision.txt")
        return
    if target.exists():
        print(f"{OK}portable detector weights present ({name}.onnx)")
        return
    if not fetch:
        print(f"{GAP}detector weights missing; run without --check to fetch them")
        return

    print(f"{DO}fetching the portable detector weights ({name}.onnx, {megabytes} MB)")
    sys.stdout.flush()
    if fetch_vision_model.ensure(name):
        print(f"{OK}portable detector ready ({target.relative_to(ROOT)})")
    else:
        print(f"{GAP}could not fetch the weights; the camera runs without recognition")


def ensure_artwork(fetch: bool) -> None:
    """Characters are optional. The page runs without them and says what is missing."""

    if REM_MARKER.exists():
        files = sum(1 for f in REM_MARKER.parent.rglob("*") if f.is_file())
        print(f"{OK}Rem's Live2D model present ({files} files)")
    elif not fetch:
        print(f"{GAP}Rem's model missing; run without --check to fetch it")
    else:
        print(f"{DO}fetching Rem's Live2D model (about 12 MB)")
        # The child writes straight to the terminal while this process's prints
        # are still buffered, so without a flush its output lands above the
        # heading that explains it.
        sys.stdout.flush()
        code = subprocess.call(
            [sys.executable, str(ROOT / "tools" / "fetch_character_assets.py")],
            cwd=ROOT,
        )
        if code == 0 and REM_MARKER.exists():
            print(f"{OK}Rem's model fetched")
        else:
            print(f"{GAP}could not fetch Rem's model; the page still runs without her")

    if NAILONG_IMAGE.exists():
        print(f"{OK}Nailong's illustration present (committed, not fetched)")
    else:
        # This one ships with the repository, so its absence means it was deleted
        # rather than never obtained. Nothing can fetch it back.
        print(f"{GAP}Nailong's illustration is missing from a checkout that carries it")
        print(f"        restore it with: git checkout -- {NAILONG_IMAGE.relative_to(ROOT)}")
        print(f"        The page runs without her; she simply does not appear.")


def report_ready() -> None:
    print()
    print("  Ready. Start the server with:")
    print("    python -m whole_home_agent.web_app --port 8600")
    print()
    print("    http://127.0.0.1:8600          the agent")
    print("    http://127.0.0.1:8600/camera   the camera")
    print()
    print("  A private model does the talking when WHA_LLM_ENDPOINT and")
    print("  WHA_LLM_MODEL are set; without them the answers are deterministic.")


def main() -> int:
    parser = argparse.ArgumentParser(prog="setup-demo")
    parser.add_argument(
        "--check", action="store_true", help="report what is present; fetch nothing"
    )
    parser.add_argument(
        "--run", action="store_true", help="start the server once everything is ready"
    )
    parser.add_argument("--port", type=int, default=8600)
    arguments = parser.parse_args()
    fetch = not arguments.check

    print(f"  Whole Home Agent setup — {ROOT}")
    print()
    if not check_package():
        return 1
    check_optional()
    print()
    if not ensure_memory(fetch):
        return 1
    ensure_vision_model(fetch)
    ensure_artwork(fetch)

    if arguments.run:
        print()
        print(f"  starting on http://127.0.0.1:{arguments.port}")
        sys.stdout.flush()
        return subprocess.call(
            [sys.executable, "-m", "whole_home_agent.web_app", "--port", str(arguments.port)],
            cwd=ROOT,
        )
    report_ready()
    return 0


if __name__ == "__main__":
    sys.exit(main())
