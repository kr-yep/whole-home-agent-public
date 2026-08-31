"""Technology-neutral frame-level perception contracts for offline B1 replay."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

from .adapters.recorded_video import DecodedVideoFrame
from .model import ProducerRef, SourcePosition


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """An original-frame ``xyxy`` box with an exclusive maximum corner."""

    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        values = (self.x_min, self.y_min, self.x_max, self.y_max)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("bounding-box coordinates must be finite")
        if self.x_min < 0 or self.y_min < 0:
            raise ValueError("bounding-box minimum coordinates cannot be negative")
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError("bounding box must have positive width and height")

    @property
    def area(self) -> float:
        return (self.x_max - self.x_min) * (self.y_max - self.y_min)

    def within(self, *, width: int, height: int) -> bool:
        return self.x_max <= width and self.y_max <= height

    def iou(self, other: BoundingBox) -> float:
        left = max(self.x_min, other.x_min)
        top = max(self.y_min, other.y_min)
        right = min(self.x_max, other.x_max)
        bottom = min(self.y_max, other.y_max)
        intersection = max(0.0, right - left) * max(0.0, bottom - top)
        union = self.area + other.area - intersection
        return 0.0 if union <= 0 else intersection / union

    def as_xyxy(self) -> tuple[float, float, float, float]:
        return (self.x_min, self.y_min, self.x_max, self.y_max)


@dataclass(frozen=True, slots=True)
class Detection:
    """One detector report; it is an estimate, never a committed world fact."""

    label: str
    confidence: float
    bbox: BoundingBox
    position: SourcePosition
    producer_ref: ProducerRef

    def __post_init__(self) -> None:
        if not self.label or self.label != self.label.strip():
            raise ValueError("detection label must be a non-empty trimmed string")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("detection confidence must be between zero and one")


@dataclass(frozen=True, slots=True)
class TrackObservation:
    """A clip-local association; ``track_id`` is not a household entity ID."""

    track_id: str
    detection: Detection
    track_age: int


class Detector(Protocol):
    """Narrow adapter boundary; SDK-native result types cannot cross it."""

    @property
    def producer_ref(self) -> ProducerRef: ...

    @property
    def device(self) -> str: ...

    def detect(self, frame: DecodedVideoFrame) -> tuple[Detection, ...]: ...

    def peak_vram_bytes(self) -> int | None: ...

    def runtime_metadata(self) -> dict[str, Any]: ...


class Tracker(Protocol):
    """Clip-local association boundary used only inside prerecorded replay."""

    def update(
        self,
        position: SourcePosition,
        detections: tuple[Detection, ...],
    ) -> tuple[TrackObservation, ...]: ...

    def reset(self) -> None: ...

    def resolved_config(self) -> dict[str, object]: ...
