"""Prove the portable detector works on this machine, and say so in one screen.

The whole point of the ONNX path is that it runs where PyTorch will not install,
which means it runs on machines nobody here can log into. So this reports the facts
someone would otherwise have to ask for: which runtime, which wheel, whether the
weights are the right bytes, whether inference actually executes, and how long a
frame costs.

    python tools/check_portable_detector.py
    python tools/check_portable_detector.py --image some/photo.jpg

Without an image it checks the structure -- the session opens, the class table is
there, one frame goes through and comes back well formed. With one it also prints
what was found in it, which is what you want when the answer is "the camera sees
nothing" and the question is whether that is the model or the room.

Exits non-zero on the first thing that is wrong, so CI can run it as a gate.
"""

from __future__ import annotations

import argparse
import io
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import fetch_vision_model  # noqa: E402  (needs the path entry above)

OK = "  ok    "
BAD = "  FAIL  "


def _fail(message: str) -> int:
    print(f"{BAD}{message}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="check-portable-detector")
    parser.add_argument("--image", type=Path, help="a photo to run the detector over")
    parser.add_argument(
        "--model",
        default=fetch_vision_model.DEFAULT_MODEL,
        choices=sorted(fetch_vision_model.WEIGHTS),
    )
    parser.add_argument(
        "--expect",
        action="append",
        default=[],
        help="a COCO label the image must contain; repeatable, and a gate for CI",
    )
    arguments = parser.parse_args()

    print(f"  {platform.system()} {platform.machine()}, Python {platform.python_version()}")

    try:
        import numpy
        import onnxruntime
        from PIL import Image
    except ImportError as error:
        return _fail(f"{error}. Install with: pip install -r requirements-vision.txt")
    print(f"{OK}onnxruntime {onnxruntime.__version__}, numpy {numpy.__version__}")
    print(f"{OK}providers: {', '.join(onnxruntime.get_available_providers())}")

    target = fetch_vision_model.model_path(arguments.model)
    if not target.exists():
        return _fail(
            f"{target.relative_to(ROOT)} is not here."
            f" Fetch it with: python tools/fetch_vision_model.py --model {arguments.model}"
        )
    complaint = fetch_vision_model._verify(target, *fetch_vision_model.WEIGHTS[arguments.model])
    if complaint:
        return _fail(f"{target.relative_to(ROOT)} is not the file we meant: {complaint}")
    print(f"{OK}{target.relative_to(ROOT)} matches its recorded digest")

    from whole_home_agent.adapters.onnx_detector import OnnxDetector

    detector = OnnxDetector(target)
    if not detector.is_available:
        return _fail("the session would not open; run with logging to see why")
    if len(detector._names) != 80:
        return _fail(f"the model carries {len(detector._names)} class names, expected 80")
    print(f"{OK}session open at {detector._side}x{detector._side}, 80 COCO classes")

    if arguments.image:
        if not arguments.image.is_file():
            return _fail(f"{arguments.image} is not a file")
        image = Image.open(arguments.image).convert("RGB")
    else:
        # Nothing is in it, which is the point: this pass proves the runtime runs
        # rather than that the model is any good, and the decoding itself is
        # pinned by tests/test_onnx_detector.py on every platform.
        image = Image.new("RGB", (1280, 720), (90, 90, 90))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    frame = buffer.getvalue()

    detector(frame, *image.size)  # warm; the first call pays for allocation
    started = time.perf_counter()
    found = detector(frame, *image.size)
    elapsed = (time.perf_counter() - started) * 1000

    for detection in found:
        if set(detection) != {"box", "label", "raw_label", "confidence"}:
            return _fail(f"a detection came back malformed: {detection}")
    source = arguments.image.name if arguments.image else "a blank frame"
    print(f"{OK}inference ran over {source} in {elapsed:.0f} ms, {len(found)} detections")
    for detection in sorted(found, key=lambda d: -d["confidence"]):
        print(f"          {detection['raw_label']:<16} {detection['confidence']:.2f}  {detection['box']}")

    labels = {detection["raw_label"] for detection in found}
    missing = [label for label in arguments.expect if label not in labels]
    if missing:
        return _fail(f"expected {missing} in this image and did not find them")
    if arguments.expect:
        print(f"{OK}found every expected label: {', '.join(arguments.expect)}")

    print("\n  The camera will use this. Start the server with: python start.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
