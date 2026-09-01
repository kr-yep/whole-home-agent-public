"""Generate the tiny project-owned M18 vector D1 image/annotation substrate."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "configs" / "evaluation" / "m18-vector-d1-slice-v1.toml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(document: object) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _load_contract() -> dict[str, Any]:
    document = tomllib.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if document.get("status") != "FROZEN_BEFORE_IMAGE_GENERATION":
        raise ValueError("M18 contract is not frozen")
    shape = document["shape"]
    if (
        shape.get("width"),
        shape.get("height"),
        shape.get("source_group_count"),
        shape.get("frames_per_group"),
        shape.get("image_annotation_pair_count"),
    ) != (640, 360, 3, 6, 18):
        raise ValueError("M18 contract shape changed")
    splits = document["split_integrity"]["splits"]
    if splits != ["development", "validation", "test"]:
        raise ValueError("M18 split set changed")
    if list(document["scene_groups"]) != splits:
        raise ValueError("M18 group definitions do not match split order")
    return document


def _source_group(split: str, settings: dict[str, Any]) -> dict[str, object]:
    sequence = int(settings["source_sequence"])
    return {
        "source_sequence": sequence,
        "source_sequence_id": f"d1-vector-{split}-v1",
        "split": split,
        "participant_id": settings["participant_id"],
        "house_room_id": settings["scene_or_room_identity"],
        "session_id": settings["session_id"],
        "camera_time_group_id": settings["camera_time_group"],
        "synchronized_view_group_id": settings["synchronized_view_group"],
    }


def _manifest_group(split: str, settings: dict[str, Any]) -> dict[str, object]:
    return {
        "split": split,
        "source_sequence": int(settings["source_sequence"]),
        "source_sequence_id": f"d1-vector-{split}-v1",
        "asset_identity": settings["asset_identity"],
        "background_identity": settings["background_identity"],
        "layout_seed_family": settings["layout_seed_family"],
        "scene_or_room_identity": settings["scene_or_room_identity"],
        "camera_time_group": settings["camera_time_group"],
        "synchronized_view_group": settings["synchronized_view_group"],
        "seed": int(settings["seed"]),
    }


def _rgb(settings: dict[str, Any], key: str) -> tuple[int, int, int]:
    value = settings[key]
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(type(channel) is not int or not 0 <= channel <= 255 for channel in value)
    ):
        raise ValueError(f"invalid RGB setting: {key}")
    return tuple(value)


def _frame_geometry(
    settings: dict[str, Any], geometry: dict[str, Any]
) -> dict[str, list[int] | None]:
    seed = int(settings["seed"])
    x_shift = (seed % 5) * 12
    y_shift = (seed % 3) * 4
    key_width = int(geometry["key_width"])
    key_height = int(geometry["key_height"])
    partial_width = int(geometry["truncated_visible_width"])
    bag_width = int(geometry["bag_width"])
    bag_height = int(geometry["bag_height"])
    sofa_width = int(geometry["sofa_width"])
    sofa_height = int(geometry["sofa_height"])
    bag = [250 + x_shift, 212 + y_shift, 250 + x_shift + bag_width, 212 + y_shift + bag_height]
    sofa = [390 + x_shift, 170 + y_shift, 390 + x_shift + sofa_width, 170 + y_shift + sofa_height]
    return {
        "bag": bag,
        "sofa": sofa,
        "visible_source": [
            96 + x_shift,
            238 + y_shift,
            96 + x_shift + key_width,
            238 + y_shift + key_height,
        ],
        "truncated_near_container": [
            bag[0] + 7,
            bag[1] + 34,
            bag[0] + 7 + partial_width,
            bag[1] + 34 + key_height,
        ],
        "occluded_inside_container": None,
        "visible_destination": [
            sofa[0] + 34,
            sofa[1] + 42,
            sofa[0] + 34 + key_width,
            sofa[1] + 42 + key_height,
        ],
        "scored_negative": None,
        "unknown": None,
    }


def _draw_key(draw: Any, box: list[int]) -> None:
    left, top, right, bottom = box
    visible_width = right - left
    ring_diameter = min(12, visible_width)
    draw.ellipse(
        (left, top, left + ring_diameter, top + ring_diameter),
        outline=(126, 86, 0),
        width=3,
    )
    if visible_width > ring_diameter:
        draw.rectangle(
            (left + ring_diameter - 2, top + 4, right, min(bottom, top + 8)),
            fill=(231, 176, 24),
        )
        if visible_width >= 24:
            draw.rectangle(
                (right - 6, top + 7, right - 2, bottom),
                fill=(231, 176, 24),
            )


def _render_frame(
    *,
    split: str,
    frame_index: int,
    role: str,
    settings: dict[str, Any],
    geometry: dict[str, Any],
    width: int,
    height: int,
):
    from PIL import Image, ImageDraw

    boxes = _frame_geometry(settings, geometry)
    image = Image.new("RGB", (width, height), _rgb(settings, "background_rgb"))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 300, width, height), fill=_rgb(settings, "floor_rgb"))
    draw.rectangle((55, 208, 360, 276), fill=(166, 133, 92), outline=(95, 65, 35), width=4)
    sofa = boxes["sofa"]
    bag = boxes["bag"]
    assert sofa is not None and bag is not None
    sofa_color = _rgb(settings, "sofa_rgb")
    bag_color = _rgb(settings, "bag_rgb")
    draw.rounded_rectangle(sofa, radius=20, fill=sofa_color, outline=(45, 57, 72), width=5)
    draw.rectangle(
        (sofa[0] + 15, sofa[1] + 30, sofa[2] - 15, sofa[3] - 12),
        fill=tuple(min(255, channel + 22) for channel in sofa_color),
    )
    draw.rounded_rectangle(bag, radius=10, fill=bag_color, outline=(20, 52, 90), width=4)
    draw.arc(
        (bag[0] + 20, bag[1] - 25, bag[0] + 72, bag[1] + 30),
        180,
        360,
        fill=(20, 52, 90),
        width=5,
    )
    key_box = boxes[role]
    if key_box is not None:
        _draw_key(draw, key_box)
    draw.text(
        (18, 18),
        f"D1 vector | {split} | frame {frame_index:02d} | {role}",
        fill=(35, 35, 35),
    )
    return image, key_box, bag, sofa


def _relations(split: str, relation_state: str) -> list[dict[str, str]]:
    if relation_state == "INSIDE_BAG":
        return [
            {
                "subject_id": f"key-{split}",
                "predicate": "inside",
                "object_id": f"bag-{split}",
                "epistemic_status": "synthetic_reference",
            }
        ]
    if relation_state == "AT_SOFA":
        return [
            {
                "subject_id": f"key-{split}",
                "predicate": "at_zone",
                "object_id": f"sofa-{split}",
                "epistemic_status": "synthetic_reference",
            }
        ]
    return []


def generate(
    *,
    media_directory: Path | None = None,
    oracle_fixture_path: Path | None = None,
) -> dict[str, object]:
    """Write one deterministic slice and return its canonical manifest."""

    import PIL

    contract = _load_contract()
    shape = contract["shape"]
    width = int(shape["width"])
    height = int(shape["height"])
    frame_plan = contract["frame_plan"]
    roles = frame_plan["roles"]
    states = frame_plan["evaluation_states"]
    visibilities = frame_plan["visibility_states"]
    relation_states = frame_plan["relation_states"]
    if not (len(roles) == len(states) == len(visibilities) == len(relation_states) == 6):
        raise ValueError("M18 frame plan is inconsistent")

    canonical_media_root = Path(contract["output_directory"])
    canonical_fixture_path = Path(contract["oracle_fixture_path"])
    media_directory = media_directory or ROOT / canonical_media_root
    oracle_fixture_path = oracle_fixture_path or ROOT / canonical_fixture_path
    media_directory.mkdir(parents=True, exist_ok=True)
    oracle_fixture_path.parent.mkdir(parents=True, exist_ok=True)

    source_groups: list[dict[str, object]] = []
    manifest_groups: list[dict[str, object]] = []
    sequences: list[dict[str, object]] = []
    transitions: list[dict[str, object]] = []
    media_records: list[dict[str, object]] = []
    annotation_records: list[dict[str, object]] = []
    output_records: list[dict[str, object]] = []

    for split in contract["split_integrity"]["splits"]:
        settings = contract["scene_groups"][split]
        group = _source_group(split, settings)
        source_groups.append(group)
        manifest_groups.append(_manifest_group(split, settings))
        frames: list[dict[str, object]] = []
        for frame_index, (role, state, visibility, relation_state) in enumerate(
            zip(roles, states, visibilities, relation_states, strict=True)
        ):
            image_name = f"{split}_{frame_index:03d}.png"
            annotation_name = f"{split}_{frame_index:03d}.annotation.json"
            image_path = media_directory / image_name
            annotation_path = media_directory / annotation_name
            logical_image_path = (canonical_media_root / image_name).as_posix()
            logical_annotation_path = (canonical_media_root / annotation_name).as_posix()
            image, key_box, bag_box, sofa_box = _render_frame(
                split=split,
                frame_index=frame_index,
                role=role,
                settings=settings,
                geometry=contract["vector_geometry"],
                width=width,
                height=height,
            )
            image.save(image_path, format="PNG", optimize=False, compress_level=9)
            image_hash = _sha256(image_path)
            image_size = image_path.stat().st_size
            instance = {
                "instance_id": f"key-{split}",
                "label": "key",
                "visibility": visibility,
                "bbox": key_box,
            }
            frame_record = {
                "frame_index": frame_index,
                "state": state,
                "instances": [instance],
            }
            frames.append(frame_record)
            annotation_document = {
                "schema_version": 1,
                "dataset_id": contract["dataset_id"],
                "use_class": contract["use_class"],
                "source_sequence": group["source_sequence"],
                "source_sequence_id": group["source_sequence_id"],
                "split": split,
                "frame_index": frame_index,
                "frame_role": role,
                "evaluation_state": state,
                "coordinate_space": shape["coordinate_space"],
                "image": {
                    "path": logical_image_path,
                    "sha256": image_hash,
                    "width": width,
                    "height": height,
                },
                "instances": [instance],
                "reference_objects": [
                    {"instance_id": f"bag-{split}", "label": "bag", "bbox": bag_box},
                    {"instance_id": f"sofa-{split}", "label": "sofa", "bbox": sofa_box},
                ],
                "relation_state": relation_state,
                "relations": _relations(split, relation_state),
            }
            annotation_path.write_bytes(_canonical_json(annotation_document))
            annotation_hash = _sha256(annotation_path)
            annotation_size = annotation_path.stat().st_size
            media_records.append(
                {
                    "path": logical_image_path,
                    "sha256": image_hash,
                    "size_bytes": image_size,
                    "kind": "image",
                }
            )
            annotation_records.append(
                {
                    "path": logical_annotation_path,
                    "sha256": annotation_hash,
                    "size_bytes": annotation_size,
                    "kind": "frame_annotation",
                    "image_path": logical_image_path,
                    "image_sha256": image_hash,
                }
            )
            output_records.extend((media_records[-1], annotation_records[-1]))
        sequence = {"group": group, "frames": frames}
        sequences.append(sequence)
        sequence_index = int(group["source_sequence"])
        transitions.extend(
            (
                {
                    "episode_id": f"{split}-key-containment",
                    "source_sequence": sequence_index,
                    "instance_id": f"key-{split}",
                    "start_frame_index": 1,
                    "end_frame_index": 2,
                    "kind": "CONTAINMENT_CHANGE",
                },
                {
                    "episode_id": f"{split}-key-location",
                    "source_sequence": sequence_index,
                    "instance_id": f"key-{split}",
                    "start_frame_index": 2,
                    "end_frame_index": 3,
                    "kind": "LOCATION_CHANGE",
                },
            )
        )

    oracle_document = {
        "schema_version": 1,
        "fixture_id": "d1-vector-slice-v1",
        "use_class": contract["use_class"],
        "dataset": {
            "dataset_id": contract["dataset_id"],
            "width": width,
            "height": height,
            "sequences": sequences,
            "transitions": transitions,
        },
        "split_groups": source_groups,
        "prediction_cases": {"empty": []},
    }
    oracle_fixture_path.write_bytes(_canonical_json(oracle_document))
    oracle_output = {
        "path": canonical_fixture_path.as_posix(),
        "sha256": _sha256(oracle_fixture_path),
        "size_bytes": oracle_fixture_path.stat().st_size,
        "kind": "m16_oracle_fixture",
    }
    output_records.append(oracle_output)
    output_records.sort(key=lambda item: str(item["path"]))
    total_bytes = sum(int(item["size_bytes"]) for item in output_records)
    maximum_bytes = int(contract["reproducibility"]["maximum_total_non_manifest_output_bytes"])
    if total_bytes > maximum_bytes:
        raise ValueError("M18 output exceeds the frozen total byte bound")

    generator_path = Path(__file__).resolve()
    manifest = {
        "schema_version": 1,
        "dataset_id": contract["dataset_id"],
        "use_class": contract["use_class"],
        "license": contract["license"],
        "coordinate_space": shape["coordinate_space"],
        "width": width,
        "height": height,
        "image_annotation_pair_count": len(media_records),
        "source_groups": manifest_groups,
        "provenance": {
            "kind": "project_generated_synthetic",
            "generator_path": contract["generator_path"],
            "generator_sha256": _sha256(generator_path),
            "config_path": CONTRACT_PATH.relative_to(ROOT).as_posix(),
            "config_sha256": _sha256(CONTRACT_PATH),
            "license": contract["license"],
            "use_class": contract["use_class"],
            "pillow_version": PIL.__version__,
        },
        "media": media_records,
        "annotations": annotation_records,
        "oracle_fixture": oracle_output,
        "outputs": output_records,
        "total_non_manifest_output_bytes": total_bytes,
        "manifest_self_hash": None,
    }
    (media_directory / "manifest.json").write_bytes(_canonical_json(manifest))
    return manifest


if __name__ == "__main__":
    generate()
