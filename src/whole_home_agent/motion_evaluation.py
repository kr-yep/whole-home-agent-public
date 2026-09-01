"""Evidence-bounded evaluation for motion-gated prerecorded perception."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import math
import time
from pathlib import Path
from typing import Iterator, Protocol

from .adapters.motion import MotionPeriodicScheduler
from .adapters.vost import MotionGateCriteria
from .evaluation import RunEnvironment, collect_run_environment
from .model import SourceDescriptor
from .perception import Detector, VideoFrame


MOTION_EVALUATOR_VERSION = "motion-screen-evaluator/1"


class MotionEvaluationSource(Protocol):
    descriptor: SourceDescriptor
    split: str
    annotation_hash: str
    width: int
    height: int
    fps_numerator: int
    fps_denominator: int
    mask_change_frames: frozenset[int]
    coverage_window_frames: int
    ground_truth: dict[int, tuple[object, ...]]

    @property
    def frame_count(self) -> int: ...

    @property
    def source_diagnostics(self) -> dict[str, object]: ...

    def iter_frames(self) -> Iterator[VideoFrame]: ...


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(quantile * len(ordered)))
    return ordered[rank - 1]


@dataclass(frozen=True, slots=True)
class MaskChangeCoverage:
    event_count: int
    exact_covered_count: int
    exact_recall: float
    same_or_following_covered_count: int
    same_or_following_recall: float
    coverage_window_frames: int


@dataclass(frozen=True, slots=True)
class TargetDetectionCoverage:
    event_count: int
    exact_covered_count: int
    exact_recall: float
    same_or_following_covered_count: int
    same_or_following_recall: float
    coverage_window_frames: int
    match_iou_threshold: float


@dataclass(frozen=True, slots=True)
class MotionScreenCost:
    decoded_frames: int
    detector_calls: int
    avoided_detector_calls: int
    avoided_detector_fraction: float
    detector_latency_p50_ms: float
    detector_latency_p95_ms: float
    detector_fps: float
    scheduler_latency_p50_ms: float | None
    scheduler_latency_p95_ms: float | None
    pipeline_fps: float
    real_time_factor: float
    peak_vram_bytes: int | None
    device: str


@dataclass(frozen=True, slots=True)
class MotionScreenReport:
    source_id: str
    source_revision: str
    source_content_hash: str
    annotation_hash: str
    evaluator_version: str
    split: str
    mode: str
    producer_ref: dict[str, str]
    scheduler: dict[str, object] | None
    selection_reasons: dict[str, int]
    coverage: MaskChangeCoverage
    target_detection_coverage: TargetDetectionCoverage | None
    cost: MotionScreenCost
    detections_total: int
    detected_label_counts: dict[str, int]
    source_diagnostics: dict[str, object]
    environment: RunEnvironment
    evidence_limit: str

    def as_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["environment"] = self.environment.as_dict()
        return value


@dataclass(frozen=True, slots=True)
class MotionGateDecision:
    decision: str
    validation_source_id: str
    checks: dict[str, dict[str, object]]
    evidence_limit: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SchedulerSelectionReport:
    source_id: str
    split: str
    scheduler: dict[str, object]
    selection_reasons: dict[str, int]
    coverage: MaskChangeCoverage
    decoded_frames: int
    selected_frames: int
    avoided_detector_fraction: float
    scheduler_latency_p50_ms: float
    scheduler_latency_p95_ms: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_scheduler_selection(
    source: MotionEvaluationSource,
    scheduler: MotionPeriodicScheduler,
) -> SchedulerSelectionReport:
    """Screen scheduler settings without invoking a detector or test source."""

    selected: set[int] = set()
    reasons: Counter[str] = Counter()
    latencies_ms: list[float] = []
    decoded = 0
    for frame in source.iter_frames():
        if frame.position.frame_index != decoded:
            raise ValueError("scheduler screen requires consecutive local frame indexes")
        started = time.perf_counter()
        decision = scheduler.evaluate(frame)
        latencies_ms.append((time.perf_counter() - started) * 1000.0)
        reasons[decision.reason.value] += 1
        if decision.selected:
            selected.add(decoded)
        decoded += 1
    if decoded != source.frame_count or not selected:
        raise ValueError("scheduler screen did not cover the declared frame sequence")
    events = source.mask_change_frames
    exact = sum(frame in selected for frame in events)
    covered = sum(
        any(
            candidate in selected
            for candidate in range(
                frame,
                min(source.frame_count, frame + source.coverage_window_frames + 1),
            )
        )
        for frame in events
    )
    event_count = len(events)
    return SchedulerSelectionReport(
        source_id=source.descriptor.source_id,
        split=source.split,
        scheduler=scheduler.resolved_config(),
        selection_reasons=dict(sorted(reasons.items())),
        coverage=MaskChangeCoverage(
            event_count=event_count,
            exact_covered_count=exact,
            exact_recall=exact / event_count if event_count else 1.0,
            same_or_following_covered_count=covered,
            same_or_following_recall=covered / event_count if event_count else 1.0,
            coverage_window_frames=source.coverage_window_frames,
        ),
        decoded_frames=decoded,
        selected_frames=len(selected),
        avoided_detector_fraction=1.0 - len(selected) / decoded,
        scheduler_latency_p50_ms=_percentile(latencies_ms, 0.50),
        scheduler_latency_p95_ms=_percentile(latencies_ms, 0.95),
    )


def evaluate_motion_screen(
    source: MotionEvaluationSource,
    detector: Detector,
    *,
    scheduler: MotionPeriodicScheduler | None,
    warmup_frames: int = 1,
    repository_root: str | Path | None = None,
    code_revision: str | None = None,
    dirty_worktree: bool | None = None,
) -> MotionScreenReport:
    """Measure detector-call savings and mask-change coverage on one replay."""

    if warmup_frames < 0:
        raise ValueError("warmup_frames cannot be negative")
    selected: set[int] = set()
    reasons: Counter[str] = Counter()
    labels: Counter[str] = Counter()
    scheduler_latencies_ms: list[float] = []
    detector_latencies_ms: list[float] = []
    detector_seconds = 0.0
    detection_count = 0
    target_matched_frames: set[int] = set()
    decoded_count = 0
    warmed = 0
    pipeline_start = time.perf_counter()
    for frame in source.iter_frames():
        frame_index = frame.position.frame_index
        if frame_index != decoded_count:
            raise ValueError("motion evaluation requires consecutive local frame indexes")
        decoded_count += 1
        if scheduler is None:
            is_selected = True
            reason = "full_frame"
        else:
            schedule_start = time.perf_counter()
            decision = scheduler.evaluate(frame)
            scheduler_latencies_ms.append(
                (time.perf_counter() - schedule_start) * 1000.0
            )
            is_selected = decision.selected
            reason = decision.reason.value
        reasons[reason] += 1
        if not is_selected:
            continue
        selected.add(frame_index)
        if warmed < warmup_frames:
            detector.detect(frame)
            warmed += 1
        detector_start = time.perf_counter()
        detections = detector.detect(frame)
        latency_ms = (time.perf_counter() - detector_start) * 1000.0
        detector_latencies_ms.append(latency_ms)
        detector_seconds += latency_ms / 1000.0
        if any(
            item.position != frame.position
            or item.producer_ref != detector.producer_ref
            or not item.bbox.within(width=source.width, height=source.height)
            for item in detections
        ):
            raise ValueError("detector violated the canonical output contract")
        detection_count += len(detections)
        labels.update(item.label for item in detections)
        targets = source.ground_truth.get(frame_index, ())
        if any(
            getattr(target, "label", None) == detection.label
            and getattr(target, "bbox", None) is not None
            and target.bbox.iou(detection.bbox) >= 0.5
            for target in targets
            for detection in detections
        ):
            target_matched_frames.add(frame_index)
    pipeline_seconds = time.perf_counter() - pipeline_start
    if decoded_count != source.frame_count or not selected:
        raise ValueError("motion evaluation did not cover the declared frame sequence")

    events = source.mask_change_frames
    exact_covered = sum(frame_index in selected for frame_index in events)
    window_covered = sum(
        any(
            candidate in selected
            for candidate in range(
                frame_index,
                min(source.frame_count, frame_index + source.coverage_window_frames + 1),
            )
        )
        for frame_index in events
    )
    event_count = len(events)
    selected_count = len(selected)
    has_target_ground_truth = any(source.ground_truth.values())
    target_exact_covered = sum(
        frame_index in target_matched_frames for frame_index in events
    )
    target_window_covered = sum(
        any(
            candidate in target_matched_frames
            for candidate in range(
                frame_index,
                min(source.frame_count, frame_index + source.coverage_window_frames + 1),
            )
        )
        for frame_index in events
    )
    duration_seconds = (
        source.frame_count * source.fps_denominator / source.fps_numerator
    )
    producer = detector.producer_ref
    return MotionScreenReport(
        source_id=source.descriptor.source_id,
        source_revision=source.descriptor.source_revision,
        source_content_hash=source.descriptor.content_hash,
        annotation_hash=source.annotation_hash,
        evaluator_version=MOTION_EVALUATOR_VERSION,
        split=source.split,
        mode="full_frame" if scheduler is None else "motion_plus_periodic",
        producer_ref={
            "artifact_hash": producer.artifact_hash,
            "component": producer.component,
            "config_hash": producer.config_hash,
            "version": producer.version,
        },
        scheduler=None if scheduler is None else scheduler.resolved_config(),
        selection_reasons=dict(sorted(reasons.items())),
        coverage=MaskChangeCoverage(
            event_count=event_count,
            exact_covered_count=exact_covered,
            exact_recall=exact_covered / event_count if event_count else 1.0,
            same_or_following_covered_count=window_covered,
            same_or_following_recall=window_covered / event_count if event_count else 1.0,
            coverage_window_frames=source.coverage_window_frames,
        ),
        target_detection_coverage=(
            TargetDetectionCoverage(
                event_count=event_count,
                exact_covered_count=target_exact_covered,
                exact_recall=(
                    target_exact_covered / event_count if event_count else 1.0
                ),
                same_or_following_covered_count=target_window_covered,
                same_or_following_recall=(
                    target_window_covered / event_count if event_count else 1.0
                ),
                coverage_window_frames=source.coverage_window_frames,
                match_iou_threshold=0.5,
            )
            if has_target_ground_truth
            else None
        ),
        cost=MotionScreenCost(
            decoded_frames=decoded_count,
            detector_calls=selected_count,
            avoided_detector_calls=decoded_count - selected_count,
            avoided_detector_fraction=1.0 - selected_count / decoded_count,
            detector_latency_p50_ms=_percentile(detector_latencies_ms, 0.50),
            detector_latency_p95_ms=_percentile(detector_latencies_ms, 0.95),
            detector_fps=(selected_count / detector_seconds if detector_seconds else 0.0),
            scheduler_latency_p50_ms=(
                _percentile(scheduler_latencies_ms, 0.50)
                if scheduler_latencies_ms
                else None
            ),
            scheduler_latency_p95_ms=(
                _percentile(scheduler_latencies_ms, 0.95)
                if scheduler_latencies_ms
                else None
            ),
            pipeline_fps=decoded_count / pipeline_seconds if pipeline_seconds else 0.0,
            real_time_factor=pipeline_seconds / duration_seconds,
            peak_vram_bytes=detector.peak_vram_bytes(),
            device=detector.device,
        ),
        detections_total=detection_count,
        detected_label_counts=dict(sorted(labels.items())),
        source_diagnostics=dict(source.source_diagnostics),
        environment=collect_run_environment(
            detector,
            repository_root,
            code_revision=code_revision,
            dirty_worktree=dirty_worktree,
        ),
        evidence_limit=(
            "Mask-change coverage measures scheduler selection, not successful target "
            "detection or semantic movement understanding. Target-detection coverage, "
            "when present, only tests the explicit mask-to-label mapping and IoU match. "
            "Results apply only to these "
            "hash-pinned 5 fps egocentric VOST sequences, this model/configuration, "
            "interpreter, and machine; they do not establish fixed-camera, household, "
            "live-stream, 24/7, privacy, or operational readiness."
        ),
    )


def decide_motion_gate(
    criteria: MotionGateCriteria,
    validation_report: MotionScreenReport,
) -> MotionGateDecision:
    if validation_report.split != "validation" or validation_report.mode != "motion_plus_periodic":
        raise ValueError("motion gate requires the scheduled validation report")
    coverage = validation_report.coverage.same_or_following_recall
    avoided = validation_report.cost.avoided_detector_fraction
    p95 = validation_report.cost.detector_latency_p95_ms
    vram = validation_report.cost.peak_vram_bytes
    checks = {
        "mask_change_coverage": {
            "actual": coverage,
            "operator": ">=",
            "threshold": criteria.minimum_validation_mask_change_coverage,
            "passed": coverage >= criteria.minimum_validation_mask_change_coverage,
        },
        "avoided_detector_fraction": {
            "actual": avoided,
            "operator": ">=",
            "threshold": criteria.minimum_validation_avoided_detector_fraction,
            "passed": avoided >= criteria.minimum_validation_avoided_detector_fraction,
        },
        "detector_p95_ms": {
            "actual": p95,
            "operator": "<=",
            "threshold": criteria.maximum_detector_p95_ms,
            "passed": p95 <= criteria.maximum_detector_p95_ms,
        },
        "peak_vram_bytes": {
            "actual": vram,
            "operator": "<=",
            "threshold": criteria.maximum_peak_vram_bytes,
            "passed": vram is not None and vram <= criteria.maximum_peak_vram_bytes,
        },
    }
    passed = all(bool(item["passed"]) for item in checks.values())
    return MotionGateDecision(
        decision="CONTINUE_BOUNDED" if passed else "REJECT_CANDIDATE",
        validation_source_id=validation_report.source_id,
        checks=checks,
        evidence_limit=(
            "This decision advances or stops only the prerecorded motion-gate candidate; "
            "it does not enable OPERATE or authorize a camera, stream, or household data."
        ),
    )
