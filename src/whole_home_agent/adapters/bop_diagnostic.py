"""Pure annotation-only diagnosis for the frozen YCB-V M21 predicates."""

from __future__ import annotations

from dataclasses import dataclass

from whole_home_agent.adapters.bop_d1 import (
    BopFrame,
    BopFrameAnnotation,
    YCB_VIDEO_CLASS_NAMES,
)


CONFORMANCE_CONFLICT = "STOP_CONFORMANCE_CONFLICT_WITH_M21"
NO_SMALL_TARGET = "STOP_YCBV_NO_SMALL_TARGET_TERM"
NO_SAFE_NEGATIVE = "STOP_YCBV_NO_SAFE_NEGATIVE_TERM"
PAIRING_SCOPE = "STOP_YCBV_PAIRING_SCOPE_TERM"
SELECT_DUAL_AREA = "SELECT_DUAL_AREA_CROSS_SCENE_PAIR"
STOP_SMALL_BBOX_ORACLE = "STOP_YCBV_SMALL_BBOX_ORACLE"


@dataclass(frozen=True, slots=True)
class YcbvAnnotationDiagnostic:
    decision: str
    frame_count: int
    positive_frame_count: int
    negative_frame_count: int
    paired_object_scene_count: int
    object_rows: tuple[dict[str, object], ...]
    object_scene_rows: tuple[dict[str, object], ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "decision": self.decision,
            "frame_count": self.frame_count,
            "modeled_object_count": len(YCB_VIDEO_CLASS_NAMES),
            "positive_frame_count": self.positive_frame_count,
            "negative_frame_count": self.negative_frame_count,
            "paired_object_scene_count": self.paired_object_scene_count,
            "objects": list(self.object_rows),
            "object_scenes": list(self.object_scene_rows),
            "threshold_or_predicate_changed": False,
            "raw_annotations_emitted": False,
        }


@dataclass(frozen=True, slots=True)
class YcbvDualAreaDiagnostic:
    """Aggregate M25 suitability evidence without retaining annotation rows."""

    decision: str
    frame_count: int
    pixel_positive_frame_count: int
    bbox_positive_frame_count: int
    dual_positive_frame_count: int
    complete_absent_frame_count: int
    dual_positive_object_count: int
    distinct_scene_pair_object_count: int
    object_rows: tuple[dict[str, object], ...]
    selected_pair: dict[str, object] | None

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "decision": self.decision,
            "frame_count": self.frame_count,
            "modeled_object_count": len(YCB_VIDEO_CLASS_NAMES),
            "pixel_positive_frame_count": self.pixel_positive_frame_count,
            "bbox_positive_frame_count": self.bbox_positive_frame_count,
            "dual_positive_frame_count": self.dual_positive_frame_count,
            "complete_absent_frame_count": self.complete_absent_frame_count,
            "dual_positive_object_count": self.dual_positive_object_count,
            "distinct_scene_pair_object_count": self.distinct_scene_pair_object_count,
            "objects": list(self.object_rows),
            "selected_pair": self.selected_pair,
            "area_interval": {
                "minimum_inclusive": 0.001,
                "maximum_exclusive": 0.01,
                "visible_pixel_basis": "PX_COUNT_VISIB_DIV_307200",
                "bbox_basis": "BBOX_VISIB_WIDTH_TIMES_HEIGHT_DIV_307200",
            },
            "threshold_or_predicate_changed_after_observation": False,
            "raw_annotations_emitted": False,
        }


def diagnose_ycbv_dual_area(
    frames: tuple[BopFrame, ...],
) -> YcbvDualAreaDiagnostic:
    """Apply the frozen M25 pixel-and-bbox predicate and source-order rule."""

    ordered_frames = tuple(sorted(frames, key=lambda frame: (frame.scene_id, frame.image_id)))
    if not ordered_frames:
        raise ValueError("diagnostic requires at least one complete frame")
    identities = [(frame.scene_id, frame.image_id) for frame in ordered_frames]
    if len(set(identities)) != len(identities):
        raise ValueError("diagnostic frame identities must be unique")

    per_object_pixel: dict[int, list[tuple[BopFrame, BopFrameAnnotation]]] = {}
    per_object_bbox: dict[int, list[tuple[BopFrame, BopFrameAnnotation]]] = {}
    per_object_dual: dict[int, list[tuple[BopFrame, BopFrameAnnotation]]] = {}
    per_object_absent: dict[int, list[BopFrame]] = {}
    for frame in ordered_frames:
        object_ids = [annotation.object_id for annotation in frame.annotations]
        if len(set(object_ids)) != len(object_ids):
            raise ValueError("diagnostic modeled object ids must be unique within a frame")
        if any(object_id not in range(1, len(YCB_VIDEO_CLASS_NAMES) + 1) for object_id in object_ids):
            raise ValueError("diagnostic contains an unmodeled object id")
        present = set(object_ids)
        for object_id in range(1, len(YCB_VIDEO_CLASS_NAMES) + 1):
            if object_id not in present:
                per_object_absent.setdefault(object_id, []).append(frame)
        for annotation in frame.annotations:
            x, y, width, height = annotation.bbox_visible_xywh
            valid_bbox = (
                x >= 0
                and y >= 0
                and width > 0
                and height > 0
                and x + width <= 640
                and y + height <= 480
            )
            if not valid_bbox or annotation.visible_fraction < 0.10:
                continue
            pixel_small = 0.001 <= annotation.area_fraction < 0.01
            bbox_area_fraction = width * height / (640 * 480)
            bbox_small = 0.001 <= bbox_area_fraction < 0.01
            row = (frame, annotation)
            if pixel_small:
                per_object_pixel.setdefault(annotation.object_id, []).append(row)
            if bbox_small:
                per_object_bbox.setdefault(annotation.object_id, []).append(row)
            if pixel_small and bbox_small:
                per_object_dual.setdefault(annotation.object_id, []).append(row)

    selected_pair: dict[str, object] | None = None
    object_rows: list[dict[str, object]] = []
    pair_object_count = 0
    for object_id, label in enumerate(YCB_VIDEO_CLASS_NAMES, start=1):
        dual_rows = per_object_dual.get(object_id, [])
        absent_rows = per_object_absent.get(object_id, [])
        object_pair: tuple[BopFrame, BopFrameAnnotation, BopFrame] | None = None
        for positive_frame, annotation in dual_rows:
            negative_frame = next(
                (
                    frame
                    for frame in absent_rows
                    if frame.scene_id != positive_frame.scene_id
                ),
                None,
            )
            if negative_frame is not None:
                object_pair = (positive_frame, annotation, negative_frame)
                break
        if object_pair is not None:
            pair_object_count += 1
            if selected_pair is None:
                positive_frame, annotation, negative_frame = object_pair
                x, y, width, height = annotation.bbox_visible_xywh
                selected_pair = {
                    "object_id": object_id,
                    "label": label,
                    "positive": {
                        "scene_id": positive_frame.scene_id,
                        "image_id": positive_frame.image_id,
                        "bbox_visible_xywh": [x, y, width, height],
                        "visible_pixel_area_fraction": annotation.area_fraction,
                        "bbox_area_fraction": width * height / (640 * 480),
                        "visible_fraction": annotation.visible_fraction,
                    },
                    "negative": {
                        "scene_id": negative_frame.scene_id,
                        "image_id": negative_frame.image_id,
                    },
                }
        first_dual: dict[str, object] | None = None
        if dual_rows:
            frame, annotation = dual_rows[0]
            _, _, width, height = annotation.bbox_visible_xywh
            first_dual = {
                "scene_id": frame.scene_id,
                "image_id": frame.image_id,
                "visible_pixel_area_fraction": annotation.area_fraction,
                "bbox_area_fraction": width * height / (640 * 480),
                "visible_fraction": annotation.visible_fraction,
            }
        object_rows.append(
            {
                "object_id": object_id,
                "label": label,
                "pixel_positive_frame_count": len(per_object_pixel.get(object_id, ())),
                "bbox_positive_frame_count": len(per_object_bbox.get(object_id, ())),
                "dual_positive_frame_count": len(dual_rows),
                "dual_positive_scene_count": len({frame.scene_id for frame, _ in dual_rows}),
                "complete_absent_frame_count": len(absent_rows),
                "complete_absent_scene_count": len({frame.scene_id for frame in absent_rows}),
                "distinct_scene_pair_available": object_pair is not None,
                "first_dual_positive": first_dual,
            }
        )

    return YcbvDualAreaDiagnostic(
        decision=SELECT_DUAL_AREA if selected_pair is not None else STOP_SMALL_BBOX_ORACLE,
        frame_count=len(ordered_frames),
        pixel_positive_frame_count=sum(len(rows) for rows in per_object_pixel.values()),
        bbox_positive_frame_count=sum(len(rows) for rows in per_object_bbox.values()),
        dual_positive_frame_count=sum(len(rows) for rows in per_object_dual.values()),
        complete_absent_frame_count=sum(len(rows) for rows in per_object_absent.values()),
        dual_positive_object_count=len(per_object_dual),
        distinct_scene_pair_object_count=pair_object_count,
        object_rows=tuple(object_rows),
        selected_pair=selected_pair,
    )


def diagnose_ycbv_m21_predicates(
    frames: tuple[BopFrame, ...],
) -> YcbvAnnotationDiagnostic:
    """Count the two unchanged M21 predicate terms independently."""

    ordered_frames = tuple(sorted(frames, key=lambda frame: (frame.scene_id, frame.image_id)))
    if not ordered_frames:
        raise ValueError("diagnostic requires at least one complete frame")
    identities = [(frame.scene_id, frame.image_id) for frame in ordered_frames]
    if len(set(identities)) != len(identities):
        raise ValueError("diagnostic frame identities must be unique")

    positives: dict[tuple[int, int], list[tuple[BopFrame, BopFrameAnnotation]]] = {}
    negatives: dict[tuple[int, int], list[BopFrame]] = {}
    scene_ids = sorted({frame.scene_id for frame in ordered_frames})
    for frame in ordered_frames:
        present = {annotation.object_id for annotation in frame.annotations}
        for object_id in range(1, len(YCB_VIDEO_CLASS_NAMES) + 1):
            if object_id not in present:
                negatives.setdefault((object_id, frame.scene_id), []).append(frame)
        for annotation in frame.annotations:
            width = annotation.bbox_visible_xywh[2]
            height = annotation.bbox_visible_xywh[3]
            if (
                annotation.visible_fraction >= 0.10
                and 0.001 <= annotation.area_fraction <= 0.01
                and width > 0
                and height > 0
            ):
                positives.setdefault((annotation.object_id, frame.scene_id), []).append(
                    (frame, annotation)
                )

    paired_keys = sorted(set(positives) & set(negatives))
    positive_frame_count = sum(len(rows) for rows in positives.values())
    negative_frame_count = sum(len(rows) for rows in negatives.values())
    if paired_keys:
        decision = CONFORMANCE_CONFLICT
    elif positive_frame_count == 0:
        decision = NO_SMALL_TARGET
    elif negative_frame_count == 0:
        decision = NO_SAFE_NEGATIVE
    else:
        decision = PAIRING_SCOPE

    object_rows: list[dict[str, object]] = []
    object_scene_rows: list[dict[str, object]] = []
    for object_id, label in enumerate(YCB_VIDEO_CLASS_NAMES, start=1):
        object_positive_rows = [
            item
            for scene_id in scene_ids
            for item in positives.get((object_id, scene_id), ())
        ]
        object_negative_rows = [
            frame
            for scene_id in scene_ids
            for frame in negatives.get((object_id, scene_id), ())
        ]
        first_positive: dict[str, object] | None = None
        if object_positive_rows:
            frame, annotation = object_positive_rows[0]
            first_positive = {
                "scene_id": frame.scene_id,
                "image_id": frame.image_id,
                "visible_area_fraction": annotation.area_fraction,
                "visible_fraction": annotation.visible_fraction,
            }
        first_negative: dict[str, int] | None = None
        if object_negative_rows:
            frame = object_negative_rows[0]
            first_negative = {"scene_id": frame.scene_id, "image_id": frame.image_id}
        object_rows.append(
            {
                "object_id": object_id,
                "label": label,
                "positive_frame_count": len(object_positive_rows),
                "positive_scene_count": sum(
                    bool(positives.get((object_id, scene_id))) for scene_id in scene_ids
                ),
                "negative_frame_count": len(object_negative_rows),
                "negative_scene_count": sum(
                    bool(negatives.get((object_id, scene_id))) for scene_id in scene_ids
                ),
                "paired_scene_count": sum(
                    (object_id, scene_id) in paired_keys for scene_id in scene_ids
                ),
                "first_positive": first_positive,
                "first_negative": first_negative,
            }
        )
        for scene_id in scene_ids:
            positive_count = len(positives.get((object_id, scene_id), ()))
            negative_count = len(negatives.get((object_id, scene_id), ()))
            object_scene_rows.append(
                {
                    "object_id": object_id,
                    "scene_id": scene_id,
                    "positive_frame_count": positive_count,
                    "negative_frame_count": negative_count,
                    "paired": positive_count > 0 and negative_count > 0,
                }
            )

    return YcbvAnnotationDiagnostic(
        decision=decision,
        frame_count=len(ordered_frames),
        positive_frame_count=positive_frame_count,
        negative_frame_count=negative_frame_count,
        paired_object_scene_count=len(paired_keys),
        object_rows=tuple(object_rows),
        object_scene_rows=tuple(object_scene_rows),
    )
