"""Deterministic motion-plus-periodic frame scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..errors import ErrorCode, SourceError
from .recorded_video import DecodedVideoFrame


class SelectionReason(str, Enum):
    FIRST = "first"
    MOTION = "motion"
    PERIODIC_ANCHOR = "periodic_anchor"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class MotionScheduleConfig:
    motion_threshold: float = 0.03
    min_gap_frames: int = 2
    anchor_interval_frames: int = 10
    sample_stride: int = 8

    def __post_init__(self) -> None:
        if (
            type(self.motion_threshold) is not float
            or self.motion_threshold < 0.0
            or self.motion_threshold > 1.0
            or type(self.min_gap_frames) is not int
            or self.min_gap_frames <= 0
            or type(self.anchor_interval_frames) is not int
            or self.anchor_interval_frames <= 0
            or type(self.sample_stride) is not int
            or self.sample_stride <= 0
        ):
            raise ValueError("invalid motion schedule configuration")


@dataclass(frozen=True, slots=True)
class FrameSelection:
    frame_index: int
    pts: int
    selected: bool
    reason: SelectionReason
    motion_score: float | None


class MotionPeriodicScheduler:
    """Use motion as a compute hint while periodic anchors preserve coverage."""

    def __init__(self, config: MotionScheduleConfig) -> None:
        self._config = config
        self._previous_sample = None
        self._last_selected_index: int | None = None

    def resolved_config(self) -> dict[str, object]:
        return {
            "anchor_interval_frames": self._config.anchor_interval_frames,
            "min_gap_frames": self._config.min_gap_frames,
            "motion_threshold": self._config.motion_threshold,
            "sample_stride": self._config.sample_stride,
            "scheduler": "motion-periodic/1",
        }

    def evaluate(self, frame: DecodedVideoFrame) -> FrameSelection:
        try:
            import numpy as np
        except ImportError as error:  # pragma: no cover - video extra supplies it.
            raise SourceError(
                "motion scheduling requires the 'video' optional dependency",
                error_code=ErrorCode.SOURCE_FAILURE,
            ) from error

        array = np.asarray(frame.rgb)
        if array.ndim != 3 or array.shape[2] != 3:
            raise SourceError(
                "motion scheduler requires an RGB frame",
                error_code=ErrorCode.INVALID_SOURCE,
            )
        sample = array[:: self._config.sample_stride, :: self._config.sample_stride]
        sample = sample.astype(np.float32).mean(axis=2) / 255.0
        frame_index = frame.position.frame_index
        pts = frame.position.pts
        if frame_index is None or pts is None:
            raise SourceError(
                "motion scheduler requires frame index and PTS",
                error_code=ErrorCode.INVALID_SOURCE,
            )

        if self._previous_sample is None:
            score = None
            selected = True
            reason = SelectionReason.FIRST
        else:
            if sample.shape != self._previous_sample.shape:
                raise SourceError(
                    "motion sample dimensions changed within one replay",
                    error_code=ErrorCode.INVALID_SOURCE,
                )
            score = float(np.abs(sample - self._previous_sample).mean())
            assert self._last_selected_index is not None
            gap = frame_index - self._last_selected_index
            if score >= self._config.motion_threshold and gap >= self._config.min_gap_frames:
                selected = True
                reason = SelectionReason.MOTION
            elif gap >= self._config.anchor_interval_frames:
                selected = True
                reason = SelectionReason.PERIODIC_ANCHOR
            else:
                selected = False
                reason = SelectionReason.SKIPPED

        self._previous_sample = sample
        if selected:
            self._last_selected_index = frame_index
        return FrameSelection(
            frame_index=frame_index,
            pts=pts,
            selected=selected,
            reason=reason,
            motion_score=score,
        )
