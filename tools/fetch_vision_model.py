"""Fetch the detector weights the camera needs but the repository does not carry.

`*.onnx` and `*.pt` are ignored repository-wide, the same way the character art is,
so a fresh clone has the whole camera path and nothing to run in it. The other way
to get weights is to let Ultralytics download them, which means installing PyTorch,
and PyTorch publishes one macOS wheel per release -- `macosx_14_0_arm64`. On an Intel
Mac, or on anything older than Sonoma, there is no wheel and the install does not
finish, so that route is closed before it starts.

This one is not. It downloads Ultralytics' own ONNX export over plain HTTPS, checks
it against a recorded digest, and leaves a file that `onnxruntime` can open. Same
weights and same COCO classes as the `.pt`; only the runtime differs.

    python tools/fetch_vision_model.py                 fetch the default (yolov8n, 13 MB)
    python tools/fetch_vision_model.py --model yolov8s  a larger, slower, better one
    python tools/fetch_vision_model.py --check          report only; download nothing

Standard library only, matching the rest of the package.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
TIMEOUT = 120

# Pinned to one release rather than tracking the newest, because a digest is only
# worth recording if the bytes behind the URL do not move. v8.4.0 is the first
# assets release to carry the v8 ONNX exports; earlier tags have the .pt files only.
RELEASE = "https://github.com/ultralytics/assets/releases/download/v8.4.0"

# Recorded from two machines on separate networks, so a mismatch means the file
# changed or the download broke, not that one connection was having a bad day.
WEIGHTS: dict[str, tuple[int, str]] = {
    "yolov8n": (12851049, "b2bc52f40e8e1c532427d5bde3575a5d5b571b739fab2c6df443733ed1589cbd"),
    "yolov8s": (44869837, "111b9b7df6f1256ec4fa9c9258f10bd824a48da75f7bc575d2f2634c2171ebf7"),
    "yolov8m": (103809542, "3aa21a2bbcb5e374a5802c05c0a68795470dbe67caf6eec15b1802e236692407"),
}

# The smallest one. On a laptop CPU the larger models cost more per frame than the
# camera's own interval, so the detector falls behind the thing it is watching; the
# demo is objects on a desk, which n finds.
DEFAULT_MODEL = "yolov8n"


def model_path(name: str) -> Path:
    return MODELS / f"{name}.onnx"


def _verify(path: Path, expected_size: int, expected_digest: str) -> str:
    """Empty string when the file is the one we meant to get, else the reason."""

    actual_size = path.stat().st_size
    if actual_size != expected_size:
        return f"{actual_size} bytes, expected {expected_size}"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != expected_digest:
        # Every character this script prints is ASCII on purpose. A Windows
        # console still runs on a legacy code page, and a stray ellipsis in an
        # error message would raise UnicodeEncodeError over the top of whatever
        # the message was trying to report.
        return f"sha256 {digest.hexdigest()[:16]}..., expected {expected_digest[:16]}..."
    return ""


def fetch(name: str) -> int:
    expected_size, expected_digest = WEIGHTS[name]
    target = model_path(name)
    # Written beside the target and renamed once it checks out, so an interrupted
    # download leaves nothing that a later run would mistake for a finished model.
    partial = target.with_suffix(".onnx.part")
    MODELS.mkdir(parents=True, exist_ok=True)

    url = f"{RELEASE}/{name}.onnx"
    print(f"  downloading {name}.onnx ({expected_size // (1 << 20)} MB) from {url}")
    written = 0
    milestone = 0
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response, partial.open("wb") as handle:
            for block in iter(lambda: response.read(1 << 18), b""):
                handle.write(block)
                written += len(block)
                if written * 4 // expected_size > milestone:
                    milestone = written * 4 // expected_size
                    print(f"    {written * 100 // expected_size:3d}%")
                    sys.stdout.flush()
    except Exception as error:
        partial.unlink(missing_ok=True)
        print(f"  download failed: {error}")
        return 1

    complaint = _verify(partial, expected_size, expected_digest)
    if complaint:
        partial.unlink(missing_ok=True)
        print(f"  what arrived is not the file we asked for: {complaint}")
        return 1

    partial.replace(target)
    print(f"  saved {target.relative_to(ROOT)}")
    return 0


def verify(name: str) -> str:
    """Empty string when the model on disk is the one we meant, else the reason.

    The public form of the check, because setup_demo, start.py and
    check_portable_detector all have to agree on what "present" means. Existing is
    not enough: a download cut off by a closed laptop leaves a file of the right
    name that no runtime will open.
    """

    target = model_path(name)
    if not target.exists():
        return "not here"
    return _verify(target, *WEIGHTS[name])


def report(name: str, *, advise: bool = True) -> int:
    """Zero when the model is present and intact; one otherwise.

    `advise` is off when the caller is about to fix the problem itself, so that a
    plain `fetch_vision_model.py` does not tell the reader to run the command they
    are already running.
    """

    target = model_path(name)
    complaint = verify(name)
    if complaint == "not here":
        print(f"  MISSING  {target.relative_to(ROOT)}")
        if advise:
            print("           run this script without --check to fetch it")
        return 1
    if complaint:
        print(f"  DAMAGED  {target.relative_to(ROOT)}: {complaint}")
        if advise:
            print("           run this script without --check to replace it")
        return 1
    print(f"  present  {target.relative_to(ROOT)}")
    return 0


def ensure(name: str = DEFAULT_MODEL) -> bool:
    """Fetch if absent or damaged, and say whether a usable model is on disk after.

    Called by tools/setup_demo.py and start.py, so that the two entry points and
    this script cannot disagree about where the weights live or what a usable one is.
    """

    if not verify(name):
        return True
    model_path(name).unlink(missing_ok=True)
    return fetch(name) == 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="fetch-vision-model")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=sorted(WEIGHTS),
        help=f"which detector to fetch (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report what is present or missing without downloading anything",
    )
    arguments = parser.parse_args()

    if arguments.check:
        return report(arguments.model)

    if report(arguments.model, advise=False) == 0:
        print("  leaving it alone")
    elif not ensure(arguments.model):
        return 1

    print(
        f"\nThe camera uses this automatically once it is here. To pick it explicitly:"
        f"\n  WHA_YOLO_MODEL={model_path(arguments.model).relative_to(ROOT)}"
        "\n\nThe weights are Ultralytics' YOLOv8, AGPL-3.0; the model file says so in"
        "\nits own metadata. See docs/third-party-notices.md."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
