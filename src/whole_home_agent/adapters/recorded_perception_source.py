"""Offline prerecorded perception adapter that emits canonical B1 candidates."""

from __future__ import annotations

from dataclasses import dataclass

from ..binding import BoundFrame, ManifestEntityBinder
from ..errors import ErrorCode, SourceError
from ..model import ClaimCandidate, SourceDescriptor
from ..perception import Detection, Detector, TrackObservation, Tracker
from ..relation_inference import (
    InferenceAbstention,
    RelationRuleConfig,
    TemporalRelationEngine,
)
from ..video_manifest import VideoSourceManifest
from .motion import MotionPeriodicScheduler
from .recorded_video import iter_decoded_frames


@dataclass(frozen=True, slots=True)
class PerceptionFrameTrace:
    frame_index: int
    pts: int
    detections: tuple[Detection, ...]
    tracks: tuple[TrackObservation, ...]
    binding: BoundFrame
    emitted_claim_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PerceptionSourceDiagnostics:
    decoded_frames: int
    selected_frames: int
    emitted_candidate_count: int
    abstentions: tuple[InferenceAbstention, ...]
    completed: bool


class RecordedPerceptionCandidateSource:
    """Compose decode → detect → track → bind → infer for one finite replay."""

    def __init__(
        self,
        manifest: VideoSourceManifest,
        detector: Detector,
        tracker: Tracker,
        relation_config: RelationRuleConfig,
        *,
        scheduler: MotionPeriodicScheduler | None = None,
    ) -> None:
        self._manifest = manifest
        self._detector = detector
        self._tracker = tracker
        self._scheduler = scheduler
        self._binder = ManifestEntityBinder(manifest)
        self._engine = TemporalRelationEngine(
            relation_config,
            source_id=manifest.descriptor.source_id,
            detector_producer=detector.producer_ref,
            entity_map=self._binder.entity_map,
        )
        self._closed = False
        self._completed = False
        self._decoded_frames = 0
        self._selected_frames = 0
        self._trace: list[PerceptionFrameTrace] = []

    @property
    def descriptor(self) -> SourceDescriptor:
        return self._manifest.descriptor

    @property
    def trace(self) -> tuple[PerceptionFrameTrace, ...]:
        return tuple(self._trace)

    @property
    def diagnostics(self) -> PerceptionSourceDiagnostics:
        return PerceptionSourceDiagnostics(
            decoded_frames=self._decoded_frames,
            selected_frames=self._selected_frames,
            emitted_candidate_count=len(self._engine.emitted_candidates),
            abstentions=self._engine.abstentions,
            completed=self._completed,
        )

    def __iter__(self):
        if self._closed:
            raise SourceError(
                "recorded perception source is already closed",
                error_code=ErrorCode.SOURCE_FAILURE,
            )
        self._tracker.reset()
        try:
            for frame in iter_decoded_frames(self._manifest):
                self._decoded_frames += 1
                if self._scheduler is not None:
                    selection = self._scheduler.evaluate(frame)
                    if not selection.selected:
                        continue
                self._selected_frames += 1
                detections = self._detector.detect(frame)
                if any(
                    item.position != frame.position
                    or item.producer_ref != self._detector.producer_ref
                    or not item.bbox.within(
                        width=self._manifest.width, height=self._manifest.height
                    )
                    for item in detections
                ):
                    raise SourceError(
                        "detector violated the canonical B1 output contract",
                        error_code=ErrorCode.INVALID_SOURCE,
                    )
                tracks = self._tracker.update(frame.position, detections)
                bound = self._binder.bind(frame.position, tracks)
                candidates = self._engine.observe(bound)
                frame_index = frame.position.frame_index
                pts = frame.position.pts
                if frame_index is None or pts is None:
                    raise SourceError(
                        "recorded perception frame lost its media position",
                        error_code=ErrorCode.INVALID_SOURCE,
                    )
                self._trace.append(
                    PerceptionFrameTrace(
                        frame_index=frame_index,
                        pts=pts,
                        detections=detections,
                        tracks=tracks,
                        binding=bound,
                        emitted_claim_ids=tuple(item.claim_id for item in candidates),
                    )
                )
                yield from candidates
            self._completed = True
        except SourceError:
            raise
        except Exception as error:
            raise SourceError(
                "recorded perception candidate production failed",
                error_code=ErrorCode.SOURCE_FAILURE,
                details={
                    "decoded_frames": self._decoded_frames,
                    "selected_frames": self._selected_frames,
                },
            ) from error

    def close(self) -> None:
        self._closed = True
