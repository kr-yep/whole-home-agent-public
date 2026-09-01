"""Deterministic sliced-inference wrapper for finite offline detector evaluation."""

from __future__ import annotations

import hashlib
import json
import math
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..model import ProducerRef
from ..perception import BoundingBox, Detection, Detector, VideoFrame


@dataclass(frozen=True, slots=True)
class SlicedDetectorConfig:
    tile_width: int
    tile_height: int
    overlap_fraction: float
    max_tiles: int
    nms_iou_threshold: float
    include_full_frame: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.tile_width) is not int
            or type(self.tile_height) is not int
            or self.tile_width <= 0
            or self.tile_height <= 0
            or type(self.max_tiles) is not int
            or self.max_tiles <= 0
        ):
            raise ValueError("slice dimensions and max_tiles must be positive integers")
        if (
            not math.isfinite(self.overlap_fraction)
            or not 0 <= self.overlap_fraction < 0.5
        ):
            raise ValueError("slice overlap must be in [0, 0.5)")
        if (
            not math.isfinite(self.nms_iou_threshold)
            or not 0 < self.nms_iou_threshold <= 1
        ):
            raise ValueError("slice NMS threshold must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class SlicedValidationGate:
    base_model_id: str
    selection_split: str
    min_validation_overall_recall_gain: float
    min_validation_small_recall_gain: float
    max_detector_p95_ms: float
    max_peak_vram_bytes: int
    detector: SlicedDetectorConfig
    config_hash: str


def load_sliced_validation_gate(path: str | Path) -> SlicedValidationGate:
    config_path = Path(path).resolve()
    raw = config_path.read_bytes()
    document = tomllib.loads(raw.decode("utf-8"))
    expected = {
        "schema_version",
        "status",
        "base_model_id",
        "selection_split",
        "test_evaluation_allowed",
        "tile_width",
        "tile_height",
        "overlap_fraction",
        "max_tiles",
        "nms_iou_threshold",
        "include_full_frame",
        "min_validation_overall_recall_gain",
        "min_validation_small_recall_gain",
        "max_detector_p95_ms",
        "max_peak_vram_bytes",
    }
    if set(document) != expected or document.get("schema_version") != 1:
        raise ValueError("sliced validation config schema is invalid")
    if (
        document.get("status") != "CANDIDATE_VALIDATION_ONLY"
        or document.get("selection_split") != "validation"
        or document.get("test_evaluation_allowed") is not False
    ):
        raise ValueError("sliced candidate must remain validation-only")
    gains = (
        document["min_validation_overall_recall_gain"],
        document["min_validation_small_recall_gain"],
    )
    if any(type(value) not in {int, float} or not 0 <= value <= 1 for value in gains):
        raise ValueError("sliced validation gain threshold is invalid")
    max_p95 = document["max_detector_p95_ms"]
    max_vram = document["max_peak_vram_bytes"]
    if (
        type(max_p95) not in {int, float}
        or max_p95 <= 0
        or type(max_vram) is not int
        or max_vram <= 0
    ):
        raise ValueError("sliced validation cost gate is invalid")
    detector = SlicedDetectorConfig(
        tile_width=document["tile_width"],
        tile_height=document["tile_height"],
        overlap_fraction=float(document["overlap_fraction"]),
        max_tiles=document["max_tiles"],
        nms_iou_threshold=float(document["nms_iou_threshold"]),
        include_full_frame=document["include_full_frame"],
    )
    return SlicedValidationGate(
        base_model_id=document["base_model_id"],
        selection_split=document["selection_split"],
        min_validation_overall_recall_gain=float(gains[0]),
        min_validation_small_recall_gain=float(gains[1]),
        max_detector_p95_ms=float(max_p95),
        max_peak_vram_bytes=max_vram,
        detector=detector,
        config_hash=hashlib.sha256(raw).hexdigest(),
    )


def _positions(length: int, tile: int, overlap_fraction: float) -> tuple[int, ...]:
    if length <= tile:
        return (0,)
    stride = max(1, int(round(tile * (1 - overlap_fraction))))
    result = [0]
    while result[-1] + tile < length:
        next_position = min(result[-1] + stride, length - tile)
        if next_position <= result[-1]:
            break
        result.append(next_position)
    return tuple(result)


def _label_nms(
    detections: list[Detection],
    *,
    iou_threshold: float,
) -> tuple[Detection, ...]:
    ranked = sorted(
        detections,
        key=lambda item: (-item.confidence, item.label, item.bbox.as_xyxy()),
    )
    kept: list[Detection] = []
    for candidate in ranked:
        if any(
            existing.label == candidate.label
            and existing.bbox.iou(candidate.bbox) >= iou_threshold
            for existing in kept
        ):
            continue
        kept.append(candidate)
    return tuple(
        sorted(
            kept,
            key=lambda item: (item.label, -item.confidence, item.bbox.as_xyxy()),
        )
    )


class SlicedDetector:
    """Apply a base detector to bounded overlapping tiles, then translate and NMS."""

    def __init__(self, base: Detector, config: SlicedDetectorConfig):
        self._base = base
        self._config = config
        base_ref = base.producer_ref
        payload = {
            "base": base_ref.identity_payload(),
            "slice": asdict(config),
        }
        self._producer_ref = ProducerRef(
            component=f"sliced-{base_ref.component}",
            version="sliced-detector/1",
            artifact_hash=base_ref.artifact_hash,
            config_hash=hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )

    @property
    def producer_ref(self) -> ProducerRef:
        return self._producer_ref

    @property
    def device(self) -> str:
        return self._base.device

    def detect(self, frame: VideoFrame) -> tuple[Detection, ...]:
        try:
            import numpy as np
        except ImportError as error:  # pragma: no cover - supplied by video extra.
            raise RuntimeError("sliced detector requires NumPy") from error
        image = np.asarray(frame.rgb)
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("sliced detector requires one RGB frame")
        height, width = image.shape[:2]
        x_positions = _positions(width, self._config.tile_width, self._config.overlap_fraction)
        y_positions = _positions(height, self._config.tile_height, self._config.overlap_fraction)
        tiles = tuple((x, y) for y in y_positions for x in x_positions)
        if len(tiles) > self._config.max_tiles:
            raise ValueError("resolved tile count exceeds max_tiles")
        translated: list[Detection] = []
        if self._config.include_full_frame:
            for detection in self._base.detect(frame):
                translated.append(
                    Detection(
                        label=detection.label,
                        confidence=detection.confidence,
                        bbox=detection.bbox,
                        position=frame.position,
                        producer_ref=self._producer_ref,
                    )
                )
        for x_min, y_min in tiles:
            x_max = min(width, x_min + self._config.tile_width)
            y_max = min(height, y_min + self._config.tile_height)
            crop = image[y_min:y_max, x_min:x_max].copy()
            crop_frame = VideoFrame(position=frame.position, rgb=crop)
            for detection in self._base.detect(crop_frame):
                translated.append(
                    Detection(
                        label=detection.label,
                        confidence=detection.confidence,
                        bbox=BoundingBox(
                            detection.bbox.x_min + x_min,
                            detection.bbox.y_min + y_min,
                            detection.bbox.x_max + x_min,
                            detection.bbox.y_max + y_min,
                        ),
                        position=frame.position,
                        producer_ref=self._producer_ref,
                    )
                )
        if any(not item.bbox.within(width=width, height=height) for item in translated):
            raise ValueError("base detector returned a crop box outside its tile")
        return _label_nms(
            translated,
            iou_threshold=self._config.nms_iou_threshold,
        )

    def peak_vram_bytes(self) -> int | None:
        return self._base.peak_vram_bytes()

    def runtime_metadata(self) -> dict[str, Any]:
        return {
            "base": self._base.runtime_metadata(),
            "slicing": asdict(self._config),
        }
