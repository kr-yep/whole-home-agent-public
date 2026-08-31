"""Generate the tiny public D0 key/bag/sofa replay and exact annotations."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path


WIDTH = 640
HEIGHT = 360
FPS = 10
FRAME_COUNT = 80


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frame_state(index: int) -> dict[str, object]:
    sofa = [400, 185, 610, 310]
    bag_start = (260, 220)
    bag_end = (455, 215)
    if index < 45:
        bag_x, bag_y = bag_start
    elif index <= 65:
        ratio = (index - 45) / 20
        bag_x = round(bag_start[0] + (bag_end[0] - bag_start[0]) * ratio)
        bag_y = round(bag_start[1] + (bag_end[1] - bag_start[1]) * ratio)
    else:
        bag_x, bag_y = bag_end
    bag = [bag_x, bag_y, bag_x + 92, bag_y + 72]

    key_visible = index < 35
    if index < 20:
        key_x, key_y = 120, 245
    else:
        ratio = min(1.0, (index - 20) / 14)
        key_x = round(120 + (bag_start[0] + 32 - 120) * ratio)
        key_y = round(245 + (bag_start[1] + 28 - 245) * ratio)
    key = [key_x, key_y, key_x + 28, key_y + 12] if key_visible else None
    return {"bag": bag, "key": key, "sofa": sofa}


def _draw_frame(index: int):
    from PIL import Image, ImageDraw

    state = _frame_state(index)
    image = Image.new("RGB", (WIDTH, HEIGHT), (224, 216, 197))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 300, WIDTH, HEIGHT), fill=(145, 117, 88))
    draw.rectangle((60, 210, 360, 275), fill=(166, 133, 92), outline=(95, 65, 35), width=4)
    sofa = state["sofa"]
    draw.rounded_rectangle(sofa, radius=20, fill=(95, 111, 132), outline=(45, 57, 72), width=5)
    draw.rectangle((sofa[0] + 15, sofa[1] + 30, sofa[2] - 15, sofa[3] - 12), fill=(117, 137, 160))
    bag = state["bag"]
    draw.rounded_rectangle(bag, radius=10, fill=(45, 112, 170), outline=(20, 52, 90), width=4)
    draw.arc((bag[0] + 20, bag[1] - 25, bag[0] + 72, bag[1] + 30), 180, 360, fill=(20, 52, 90), width=5)
    key = state["key"]
    if key is not None:
        draw.ellipse((key[0], key[1], key[0] + 12, key[1] + 12), outline=(126, 86, 0), width=4)
        draw.rectangle((key[0] + 10, key[1] + 4, key[2], key[1] + 8), fill=(231, 176, 24))
        draw.rectangle((key[2] - 6, key[1] + 7, key[2] - 2, key[3]), fill=(231, 176, 24))
    draw.text((18, 18), f"D0 synthetic replay | frame {index:02d}", fill=(35, 35, 35))
    return image, state


def generate(output_dir: Path) -> None:
    import av

    output_dir.mkdir(parents=True, exist_ok=True)
    media_path = output_dir / "key_bag_sofa_v1.mp4"
    annotation_path = output_dir / "key_bag_sofa_v1.annotations.json"
    manifest_path = output_dir / "key_bag_sofa_v1.manifest.json"

    annotations: list[dict[str, object]] = []
    with av.open(str(media_path), mode="w", format="mp4") as container:
        stream = container.add_stream("mpeg4", rate=FPS)
        stream.width = WIDTH
        stream.height = HEIGHT
        stream.pix_fmt = "yuv420p"
        stream.options = {"threads": "1"}
        for index in range(FRAME_COUNT):
            image, state = _draw_frame(index)
            frame = av.VideoFrame.from_image(image)
            frame.pts = index
            frame.time_base = Fraction(1, FPS)
            for packet in stream.encode(frame):
                container.mux(packet)
            annotations.append({"frame_index": index, "objects": state})
        for packet in stream.encode():
            container.mux(packet)

    annotation_document = {
        "schema_version": 1,
        "coordinate_space": "pixel_xyxy_exclusive",
        "width": WIDTH,
        "height": HEIGHT,
        "frames": annotations,
    }
    annotation_path.write_text(
        json.dumps(annotation_document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    script_path = Path(__file__).resolve()
    manifest = {
        "schema_version": 1,
        "source_id": "b1-key-bag-sofa",
        "source_revision": "1",
        "source_kind": "recorded_video",
        "timestamp_basis": "media_pts",
        "use_class": "D0_SYNTHETIC",
        "path": media_path.name,
        "sha256": _sha256(media_path),
        "license": "CC0-1.0",
        "provenance": {
            "kind": "project_generated_synthetic",
            "generator": "tools/generate_synthetic_replay.py",
            "generator_sha256": _sha256(script_path),
        },
        "frame_count": FRAME_COUNT,
        "width": WIDTH,
        "height": HEIGHT,
        "fps": {"numerator": FPS, "denominator": 1},
        "annotations": {
            "path": annotation_path.name,
            "sha256": _sha256(annotation_path),
        },
        "entities": [
            {"entity_id": "key", "label": "key", "instance_count": 1},
            {"entity_id": "bag", "label": "bag", "instance_count": 1},
            {"entity_id": "sofa", "label": "sofa", "instance_count": 1},
        ],
        "events": [
            {
                "event_id": "key-inside-bag",
                "frame_index": 35,
                "operation": "assert",
                "subject_id": "key",
                "predicate": "inside",
                "object_id": "bag",
            },
            {
                "event_id": "bag-at-sofa",
                "frame_index": 65,
                "operation": "assert",
                "subject_id": "bag",
                "predicate": "at_zone",
                "object_id": "sofa",
            },
        ],
        "split": "demo",
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1] / "examples" / "media" / "generated")
