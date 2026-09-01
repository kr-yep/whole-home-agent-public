"""Conservative BOP YCB-V localization-to-D1 translation adapter."""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whole_home_agent.perception import BoundingBox
from whole_home_agent.target_oracle import (
    FrameEvaluationState,
    OracleFrame,
    OracleSequence,
    ReferenceInstance,
    SourceGroup,
    TargetOracleDataset,
    VisibilityState,
)


YCB_VIDEO_CLASS_NAMES = (
    "002_master_chef_can",
    "003_cracker_box",
    "004_sugar_box",
    "005_tomato_soup_can",
    "006_mustard_bottle",
    "007_tuna_fish_can",
    "008_pudding_box",
    "009_gelatin_box",
    "010_potted_meat_can",
    "011_banana",
    "019_pitcher_base",
    "021_bleach_cleanser",
    "024_bowl",
    "025_mug",
    "035_power_drill",
    "036_wood_block",
    "037_scissors",
    "040_large_marker",
    "051_large_clamp",
    "052_extra_large_clamp",
    "061_foam_brick",
)
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
FRAME_AREA = FRAME_WIDTH * FRAME_HEIGHT


class BopD1Error(ValueError):
    """Fail-closed BOP translation error with a stable diagnostic code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class BopFrameAnnotation:
    object_id: int
    bbox_visible_xywh: tuple[int, int, int, int]
    pixel_count_all: int
    pixel_count_visible: int
    visible_fraction: float

    @property
    def area_fraction(self) -> float:
        return self.pixel_count_visible / FRAME_AREA


@dataclass(frozen=True, slots=True)
class BopFrame:
    scene_id: int
    image_id: int
    annotations: tuple[BopFrameAnnotation, ...]


@dataclass(frozen=True, slots=True)
class BopD1Slice:
    dataset: TargetOracleDataset
    selected_object_id: int
    selected_label: str
    selected_scene_id: int
    source_frames: tuple[dict[str, object], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "dataset_id": self.dataset.dataset_id,
            "dimensions": [self.dataset.width, self.dataset.height],
            "project_split": "test",
            "selected_object_id": self.selected_object_id,
            "selected_label": self.selected_label,
            "selected_scene_id": self.selected_scene_id,
            "source_frames": list(self.source_frames),
            "reference_transition_count": len(self.dataset.transitions),
            "relation_truth_emitted": False,
        }


@dataclass(frozen=True, slots=True)
class BopCrossSceneD1Slice:
    """Two-frame detector oracle whose scenes remain separate source sequences."""

    dataset: TargetOracleDataset
    selected_object_id: int
    selected_label: str
    source_frames: tuple[dict[str, object], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "dataset_id": self.dataset.dataset_id,
            "dimensions": [self.dataset.width, self.dataset.height],
            "project_split": "test",
            "selected_object_id": self.selected_object_id,
            "selected_label": self.selected_label,
            "selected_scene_ids": [
                int(item["source_scene_id"]) for item in self.source_frames
            ],
            "source_frames": list(self.source_frames),
            "source_sequence_count": len(self.dataset.sequences),
            "reference_transition_count": len(self.dataset.transitions),
            "relation_truth_emitted": False,
        }


def load_and_translate_ycbv_bop19(dataset_root: str | Path) -> BopD1Slice:
    """Apply the frozen selection rule and verify only the selected RGB headers."""

    root = Path(dataset_root).resolve()
    result = select_ycbv_bop19_slice_from_metadata(root)
    for frame in result.source_frames:
        scene_id = int(frame["source_scene_id"])
        image_id = int(frame["source_image_id"])
        _verify_png_dimensions(
            root / "test" / f"{scene_id:06d}" / "rgb" / f"{image_id:06d}.png"
        )
    return result


def select_ycbv_bop19_slice_from_metadata(dataset_root: str | Path) -> BopD1Slice:
    """Select the frozen slice without reading image bytes or requiring RGB files."""

    root = Path(dataset_root).resolve()
    if not root.is_dir():
        raise BopD1Error("DATASET_ROOT_MISSING", "BOP YCB-V root is absent")
    targets = _load_json(root / "test_targets_bop19.json")
    if not isinstance(targets, list) or not targets:
        raise BopD1Error("TARGET_LIST_INVALID", "BOP'19 target list must be non-empty")

    target_frames = ycbv_bop19_target_frame_keys(targets)
    scene_documents: dict[int, tuple[object, object, object]] = {}
    for scene_id in sorted({scene_id for scene_id, _ in target_frames}):
        scene_root = root / "test" / f"{scene_id:06d}"
        scene_documents[scene_id] = (
            _load_json(scene_root / "scene_gt.json"),
            _load_json(scene_root / "scene_gt_info.json"),
            _load_json(scene_root / "scene_camera.json"),
        )
    return _select_and_translate(
        parse_ycbv_bop19_frames(targets, scene_documents)
    )


def ycbv_bop19_target_frame_keys(targets: object) -> tuple[tuple[int, int], ...]:
    if not isinstance(targets, list) or not targets:
        raise BopD1Error("TARGET_LIST_INVALID", "BOP'19 target list must be non-empty")
    target_frames: set[tuple[int, int]] = set()
    for item in targets:
        if not isinstance(item, dict):
            raise BopD1Error("TARGET_LIST_INVALID", "target entry must be an object")
        scene_id = _strict_int(item, "scene_id")
        image_id = _strict_int(item, "im_id")
        object_id = _strict_int(item, "obj_id")
        if object_id not in range(1, len(YCB_VIDEO_CLASS_NAMES) + 1):
            raise BopD1Error("OBJECT_ID_INVALID", "target object is outside YCB-V")
        target_frames.add((scene_id, image_id))
    return tuple(sorted(target_frames))


def parse_ycbv_bop19_frames(
    targets: object,
    scene_documents: dict[int, tuple[object, object, object]],
) -> tuple[BopFrame, ...]:
    """Validate parsed BOP documents with the exact selector input contract."""

    frames: list[BopFrame] = []
    for scene_id, image_id in ycbv_bop19_target_frame_keys(targets):
        documents = scene_documents.get(scene_id)
        if documents is None or len(documents) != 3:
            raise BopD1Error("SOURCE_FILE_MISSING", "target scene documents are absent")
        frames.append(_parse_frame(scene_id, image_id, *documents))
    return tuple(frames)


def select_cross_scene_ycbv_bop19_slice(
    frames: tuple[BopFrame, ...],
) -> BopCrossSceneD1Slice:
    """Select one source-ordered positive/absent pair without merging scene identity."""

    ordered = tuple(sorted(frames, key=lambda item: (item.scene_id, item.image_id)))
    if not ordered:
        raise BopD1Error("NO_TARGET_FRAMES", "cross-scene selection requires target frames")

    selected: tuple[int, BopFrame, BopFrameAnnotation, BopFrame] | None = None
    for object_id in range(1, len(YCB_VIDEO_CLASS_NAMES) + 1):
        positives: list[tuple[BopFrame, BopFrameAnnotation]] = []
        for frame in ordered:
            matches = [item for item in frame.annotations if item.object_id == object_id]
            if not matches:
                continue
            annotation = matches[0]
            if (
                annotation.visible_fraction >= 0.10
                and 0.001 <= annotation.area_fraction <= 0.01
                and annotation.bbox_visible_xywh[2] > 0
                and annotation.bbox_visible_xywh[3] > 0
            ):
                positives.append((frame, annotation))
        if not positives:
            continue
        positive_frame, positive_annotation = positives[0]
        negative_frame = next(
            (
                frame
                for frame in ordered
                if frame.scene_id != positive_frame.scene_id
                and all(item.object_id != object_id for item in frame.annotations)
            ),
            None,
        )
        if negative_frame is not None:
            selected = (
                object_id,
                positive_frame,
                positive_annotation,
                negative_frame,
            )
            break
    if selected is None:
        raise BopD1Error(
            "NO_CROSS_SCENE_SLICE",
            "no modeled class has a frozen positive and distinct-scene complete absence",
        )

    object_id, positive_frame, positive_annotation, negative_frame = selected
    label = YCB_VIDEO_CLASS_NAMES[object_id - 1]
    x, y, width, height = positive_annotation.bbox_visible_xywh
    bbox = BoundingBox(float(x), float(y), float(x + width), float(y + height))
    if not bbox.within(width=FRAME_WIDTH, height=FRAME_HEIGHT):
        raise BopD1Error("BOX_OUT_OF_BOUNDS", "selected visible box is invalid")
    touches_edge = (
        x == 0
        or y == 0
        or x + width == FRAME_WIDTH
        or y + height == FRAME_HEIGHT
    )
    visibility = VisibilityState.TRUNCATED if touches_edge else VisibilityState.VISIBLE

    source_frames = (
        {
            "d1_frame_index": 0,
            "local_frame_index": 0,
            "role": "POSITIVE",
            "source_scene_id": positive_frame.scene_id,
            "source_image_id": positive_frame.image_id,
            "selected_object_id": object_id,
            "selected_class_present": True,
            "visibility": visibility.value,
            "bbox_xyxy": list(bbox.as_xyxy()),
            "visible_area_fraction": positive_annotation.area_fraction,
            "visible_fraction": positive_annotation.visible_fraction,
        },
        {
            "d1_frame_index": 1,
            "local_frame_index": 0,
            "role": "COMPLETE_CLASS_ABSENT_NEGATIVE",
            "source_scene_id": negative_frame.scene_id,
            "source_image_id": negative_frame.image_id,
            "selected_object_id": object_id,
            "selected_class_present": False,
            "visibility": "ABSENT",
            "bbox_xyxy": None,
            "visible_area_fraction": None,
            "visible_fraction": None,
        },
    )
    sequences = (
        _cross_scene_sequence(
            frame=positive_frame,
            frame_instances=(
                ReferenceInstance(
                    instance_id=(
                        f"bop-ycbv-scene-{positive_frame.scene_id:06d}-"
                        f"obj-{object_id:06d}"
                    ),
                    label=label,
                    visibility=visibility,
                    bbox=bbox,
                ),
            ),
        ),
        _cross_scene_sequence(frame=negative_frame, frame_instances=()),
    )
    return BopCrossSceneD1Slice(
        dataset=TargetOracleDataset(
            dataset_id="bop-ycbv-bop19-cross-scene-test-oracle-v1",
            width=FRAME_WIDTH,
            height=FRAME_HEIGHT,
            sequences=sequences,
            transitions=(),
        ),
        selected_object_id=object_id,
        selected_label=label,
        source_frames=source_frames,
    )


def cross_scene_slice_oracle_document(
    result: BopCrossSceneD1Slice,
) -> dict[str, object]:
    """Serialize the bounded cross-scene slice into the exact M16 fixture schema."""

    groups: list[dict[str, object]] = []
    sequences: list[dict[str, object]] = []
    for sequence in result.dataset.sequences:
        group = {
            "source_sequence": sequence.group.source_sequence,
            "source_sequence_id": sequence.group.source_sequence_id,
            "split": sequence.group.split,
            "participant_id": sequence.group.participant_id,
            "house_room_id": sequence.group.house_room_id,
            "session_id": sequence.group.session_id,
            "camera_time_group_id": sequence.group.camera_time_group_id,
            "synchronized_view_group_id": sequence.group.synchronized_view_group_id,
        }
        groups.append(group)
        frames: list[dict[str, object]] = []
        for frame in sequence.frames:
            frames.append(
                {
                    "frame_index": frame.frame_index,
                    "state": frame.state.value,
                    "instances": [
                        {
                            "instance_id": item.instance_id,
                            "label": item.label,
                            "visibility": item.visibility.value,
                            "bbox": (
                                None if item.bbox is None else list(item.bbox.as_xyxy())
                            ),
                        }
                        for item in frame.instances
                    ],
                }
            )
        sequences.append({"group": group, "frames": frames})
    return {
        "schema_version": 1,
        "fixture_id": "ycbv-cross-scene-d1-v1",
        "use_class": "TEST_ONLY_MINIMAL_DETECTOR_TRANSFER_ORACLE",
        "dataset": {
            "dataset_id": result.dataset.dataset_id,
            "width": result.dataset.width,
            "height": result.dataset.height,
            "sequences": sequences,
            "transitions": [],
        },
        "split_groups": groups,
        "prediction_cases": {"empty": []},
    }


def _cross_scene_sequence(
    *, frame: BopFrame, frame_instances: tuple[ReferenceInstance, ...]
) -> OracleSequence:
    scene_id = frame.scene_id
    group = SourceGroup(
        source_sequence=scene_id,
        source_sequence_id=f"bop-ycbv-scene-{scene_id:06d}",
        split="test",
        participant_id="not_applicable:ycbv-public-dataset",
        house_room_id=f"bop-ycbv-arranged-indoor-scene-{scene_id:06d}",
        session_id=f"bop-ycbv-video-{scene_id:06d}",
        camera_time_group_id=f"bop-ycbv-uw-camera-{scene_id:06d}",
        synchronized_view_group_id=f"not_applicable:ycbv-single-view-{scene_id:06d}",
    )
    return OracleSequence(
        group=group,
        frames=(
            OracleFrame(
                frame_index=0,
                state=FrameEvaluationState.SCORED,
                instances=frame_instances,
            ),
        ),
    )


def _parse_frame(
    scene_id: int,
    image_id: int,
    ground_truth: object,
    ground_truth_info: object,
    scene_camera: object,
) -> BopFrame:
    for name, document in (
        ("scene_gt", ground_truth),
        ("scene_gt_info", ground_truth_info),
        ("scene_camera", scene_camera),
    ):
        if not isinstance(document, dict):
            raise BopD1Error("SOURCE_SCHEMA_INVALID", f"{name} must be an object")
    key = str(image_id)
    if key not in scene_camera:
        raise BopD1Error("FRAME_CAMERA_MISSING", "selected frame has no camera record")
    gt_rows = ground_truth.get(key)
    info_rows = ground_truth_info.get(key)
    if not isinstance(gt_rows, list) or not isinstance(info_rows, list):
        raise BopD1Error("FRAME_GROUND_TRUTH_MISSING", "selected frame lacks ground truth")
    if len(gt_rows) != len(info_rows):
        raise BopD1Error("GROUND_TRUTH_ALIGNMENT_ERROR", "pose/info row counts differ")
    annotations: list[BopFrameAnnotation] = []
    seen_objects: set[int] = set()
    for gt, info in zip(gt_rows, info_rows, strict=True):
        if not isinstance(gt, dict) or not isinstance(info, dict):
            raise BopD1Error("SOURCE_SCHEMA_INVALID", "ground-truth rows must be objects")
        object_id = _strict_int(gt, "obj_id")
        if object_id not in range(1, len(YCB_VIDEO_CLASS_NAMES) + 1):
            raise BopD1Error("OBJECT_ID_INVALID", "ground truth is outside YCB-V")
        if object_id in seen_objects:
            raise BopD1Error(
                "DUPLICATE_OBJECT_INSTANCE",
                "M20 requires one stable physical instance per YCB object ID",
            )
        seen_objects.add(object_id)
        _validate_pose(gt)
        bbox = _xywh(info.get("bbox_visib"))
        pixel_count_all = _nonnegative_int(info, "px_count_all")
        pixel_count_visible = _nonnegative_int(info, "px_count_visib")
        visible_fraction = _finite_number(info, "visib_fract")
        if pixel_count_all <= 0 or pixel_count_visible > pixel_count_all:
            raise BopD1Error("PIXEL_COUNT_INVALID", "visible/all pixel counts are invalid")
        if not 0.0 <= visible_fraction <= 1.0:
            raise BopD1Error("VISIBILITY_INVALID", "visible fraction is outside [0,1]")
        calculated = pixel_count_visible / pixel_count_all
        if not math.isclose(calculated, visible_fraction, rel_tol=0.0, abs_tol=1e-3):
            raise BopD1Error("VISIBILITY_INVALID", "visible fraction disagrees with counts")
        annotations.append(
            BopFrameAnnotation(
                object_id=object_id,
                bbox_visible_xywh=bbox,
                pixel_count_all=pixel_count_all,
                pixel_count_visible=pixel_count_visible,
                visible_fraction=visible_fraction,
            )
        )
    return BopFrame(
        scene_id=scene_id,
        image_id=image_id,
        annotations=tuple(annotations),
    )


def _select_and_translate(frames: tuple[BopFrame, ...]) -> BopD1Slice:
    grouped: dict[int, list[BopFrame]] = {}
    for frame in frames:
        grouped.setdefault(frame.scene_id, []).append(frame)
    selected: tuple[int, int, BopFrame, BopFrame, BopFrameAnnotation] | None = None
    for object_id in range(1, len(YCB_VIDEO_CLASS_NAMES) + 1):
        for scene_id in sorted(grouped):
            scene_frames = sorted(grouped[scene_id], key=lambda item: item.image_id)
            positive: tuple[BopFrame, BopFrameAnnotation] | None = None
            negative: BopFrame | None = None
            for frame in scene_frames:
                matches = [item for item in frame.annotations if item.object_id == object_id]
                if not matches:
                    if negative is None:
                        negative = frame
                    continue
                annotation = matches[0]
                if (
                    annotation.visible_fraction >= 0.10
                    and 0.001 <= annotation.area_fraction <= 0.01
                    and annotation.bbox_visible_xywh[2] > 0
                    and annotation.bbox_visible_xywh[3] > 0
                    and positive is None
                ):
                    positive = (frame, annotation)
            if positive is not None and negative is not None:
                selected = (object_id, scene_id, positive[0], negative, positive[1])
                break
        if selected is not None:
            break
    if selected is None:
        raise BopD1Error(
            "NO_FROZEN_SLICE",
            "no object/scene has both a 0.1-1% positive and a complete absent frame",
        )

    object_id, scene_id, positive_frame, negative_frame, positive_annotation = selected
    source_frames = sorted(
        ((positive_frame, positive_annotation), (negative_frame, None)),
        key=lambda item: item[0].image_id,
    )
    label = YCB_VIDEO_CLASS_NAMES[object_id - 1]
    instance_id = f"bop-ycbv-obj-{object_id:06d}"
    oracle_frames: list[OracleFrame] = []
    manifest_rows: list[dict[str, object]] = []
    for d1_index, (frame, annotation) in enumerate(source_frames):
        if annotation is None:
            visibility = VisibilityState.ABSENT
            bbox = None
            area_fraction: float | None = None
        else:
            x, y, width, height = annotation.bbox_visible_xywh
            bbox = BoundingBox(float(x), float(y), float(x + width), float(y + height))
            if not bbox.within(width=FRAME_WIDTH, height=FRAME_HEIGHT):
                raise BopD1Error("BOX_OUT_OF_BOUNDS", "selected visible box is invalid")
            touches_edge = x == 0 or y == 0 or x + width == FRAME_WIDTH or y + height == FRAME_HEIGHT
            visibility = VisibilityState.TRUNCATED if touches_edge else VisibilityState.VISIBLE
            area_fraction = annotation.area_fraction
        oracle_frames.append(
            OracleFrame(
                frame_index=d1_index,
                state=FrameEvaluationState.SCORED,
                instances=(
                    ReferenceInstance(
                        instance_id=instance_id,
                        label=label,
                        visibility=visibility,
                        bbox=bbox,
                    ),
                ),
            )
        )
        manifest_rows.append(
            {
                "d1_frame_index": d1_index,
                "source_scene_id": frame.scene_id,
                "source_image_id": frame.image_id,
                "selected_object_id": object_id,
                "visibility": visibility.value,
                "bbox_xyxy": None if bbox is None else list(bbox.as_xyxy()),
                "visible_area_fraction": area_fraction,
            }
        )

    group = SourceGroup(
        source_sequence=scene_id,
        source_sequence_id=f"bop-ycbv-scene-{scene_id:06d}",
        split="test",
        participant_id="not_applicable:ycbv-public-dataset",
        house_room_id=f"bop-ycbv-arranged-indoor-scene-{scene_id:06d}",
        session_id=f"bop-ycbv-video-{scene_id:06d}",
        camera_time_group_id=f"bop-ycbv-uw-camera-{scene_id:06d}",
        synchronized_view_group_id=f"not_applicable:ycbv-single-view-{scene_id:06d}",
    )
    dataset = TargetOracleDataset(
        dataset_id="bop-ycbv-bop19-local-slice",
        width=FRAME_WIDTH,
        height=FRAME_HEIGHT,
        sequences=(OracleSequence(group=group, frames=tuple(oracle_frames)),),
        transitions=(),
    )
    return BopD1Slice(
        dataset=dataset,
        selected_object_id=object_id,
        selected_label=label,
        selected_scene_id=scene_id,
        source_frames=tuple(manifest_rows),
    )


def _load_json(path: Path) -> object:
    if not path.is_file():
        raise BopD1Error("SOURCE_FILE_MISSING", f"required BOP file is absent: {path.name}")

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise BopD1Error("DUPLICATE_JSON_KEY", f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BopD1Error("SOURCE_JSON_INVALID", f"cannot parse {path.name}") from error


def _verify_png_dimensions(path: Path) -> None:
    try:
        header = path.read_bytes()[:24]
    except OSError as error:
        raise BopD1Error("RGB_FRAME_MISSING", "selected RGB frame is absent") from error
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise BopD1Error("RGB_FRAME_INVALID", "selected RGB frame is not a PNG")
    if struct.unpack(">II", header[16:24]) != (FRAME_WIDTH, FRAME_HEIGHT):
        raise BopD1Error("FRAME_DIMENSION_MISMATCH", "YCB-V frame is not 640x480")


def _validate_pose(document: dict[str, Any]) -> None:
    rotation = document.get("cam_R_m2c")
    translation = document.get("cam_t_m2c")
    if (
        not isinstance(rotation, list)
        or len(rotation) != 9
        or not isinstance(translation, list)
        or len(translation) != 3
        or any(type(value) not in {int, float} or not math.isfinite(value) for value in rotation + translation)
    ):
        raise BopD1Error("POSE_INVALID", "BOP pose fields are incomplete")


def _xywh(value: object) -> tuple[int, int, int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(type(item) is not int for item in value)
    ):
        raise BopD1Error("BOX_INVALID", "visible box must be four integers")
    return tuple(value)  # type: ignore[return-value]


def _strict_int(document: dict[str, Any], field: str) -> int:
    value = document.get(field)
    if type(value) is not int or value < 0:
        raise BopD1Error("SOURCE_SCHEMA_INVALID", f"{field} must be a non-negative integer")
    return value


def _nonnegative_int(document: dict[str, Any], field: str) -> int:
    return _strict_int(document, field)


def _finite_number(document: dict[str, Any], field: str) -> float:
    value = document.get(field)
    if type(value) not in {int, float} or not math.isfinite(value):
        raise BopD1Error("SOURCE_SCHEMA_INVALID", f"{field} must be finite")
    return float(value)
