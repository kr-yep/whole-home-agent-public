"""Small deterministic IoU tracker for clip-local B1 association."""

from __future__ import annotations

from dataclasses import dataclass

from ..model import SourcePosition
from ..perception import Detection, TrackObservation


@dataclass(frozen=True, slots=True)
class IoUTrackerConfig:
    match_iou_threshold: float = 0.25
    max_missed_updates: int = 2

    def __post_init__(self) -> None:
        if not 0.0 <= self.match_iou_threshold <= 1.0:
            raise ValueError("tracker IoU threshold must be between zero and one")
        if self.max_missed_updates < 0:
            raise ValueError("max_missed_updates cannot be negative")


@dataclass(slots=True)
class _TrackState:
    track_id: str
    detection: Detection
    age: int
    missed_updates: int


class IoUTracker:
    """Greedy label-aware association with deterministic tie breaking."""

    def __init__(self, config: IoUTrackerConfig = IoUTrackerConfig()) -> None:
        self._config = config
        self.reset()

    def reset(self) -> None:
        self._active: dict[str, _TrackState] = {}
        self._next_serial = 1

    def resolved_config(self) -> dict[str, object]:
        return {
            "match_iou_threshold": self._config.match_iou_threshold,
            "max_missed_updates": self._config.max_missed_updates,
            "tracker": "label-aware-greedy-iou/1",
        }

    def update(
        self,
        position: SourcePosition,
        detections: tuple[Detection, ...],
    ) -> tuple[TrackObservation, ...]:
        if any(item.position != position for item in detections):
            raise ValueError("all detections must belong to the tracker update position")
        for state in self._active.values():
            state.missed_updates += 1

        candidates: list[tuple[float, str, int]] = []
        for track_id, state in self._active.items():
            for detection_index, detection in enumerate(detections):
                if state.detection.label != detection.label:
                    continue
                overlap = state.detection.bbox.iou(detection.bbox)
                if overlap >= self._config.match_iou_threshold:
                    candidates.append((-overlap, track_id, detection_index))
        candidates.sort()
        used_tracks: set[str] = set()
        used_detections: set[int] = set()
        assignments: dict[int, _TrackState] = {}
        for _, track_id, detection_index in candidates:
            if track_id in used_tracks or detection_index in used_detections:
                continue
            state = self._active[track_id]
            state.detection = detections[detection_index]
            state.age += 1
            state.missed_updates = 0
            used_tracks.add(track_id)
            used_detections.add(detection_index)
            assignments[detection_index] = state

        for detection_index, detection in enumerate(detections):
            if detection_index in used_detections:
                continue
            track_id = f"clip-track-{self._next_serial:04d}"
            self._next_serial += 1
            state = _TrackState(
                track_id=track_id,
                detection=detection,
                age=1,
                missed_updates=0,
            )
            self._active[track_id] = state
            assignments[detection_index] = state

        self._active = {
            track_id: state
            for track_id, state in self._active.items()
            if state.missed_updates <= self._config.max_missed_updates
        }
        return tuple(
            TrackObservation(
                track_id=assignments[index].track_id,
                detection=detection,
                track_age=assignments[index].age,
            )
            for index, detection in enumerate(detections)
        )
