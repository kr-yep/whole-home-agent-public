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
