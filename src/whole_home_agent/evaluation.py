"""Fixed offline quality/cost evaluation for B1 detector and tracker candidates."""

from __future__ import annotations

import json
import hashlib
import importlib.metadata
import math
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters.motion import MotionPeriodicScheduler
from .adapters.recorded_video import iter_decoded_frames
from .perception import BoundingBox, Detection, Detector, TrackObservation, Tracker
from .video_manifest import VideoSourceManifest


EVALUATOR_VERSION = "b1-perception-evaluator/1"
IOU_THRESHOLDS = tuple(round(0.5 + index * 0.05, 2) for index in range(10))


@dataclass(frozen=True, slots=True)
class GroundTruthObject:
    entity_id: str
    label: str
    bbox: BoundingBox


@dataclass(frozen=True, slots=True)
class DetectionQuality:
    ap50: float
    map50_95: float
    recall50: float
    key_recall50: float | None
    false_positives50: int
    per_label_ap50: tuple[tuple[str, float], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ap50": self.ap50,
            "false_positives50": self.false_positives50,
            "key_recall50": self.key_recall50,
            "map50_95": self.map50_95,
            "per_label_ap50": dict(self.per_label_ap50),
            "recall50": self.recall50,
        }


@dataclass(frozen=True, slots=True)
class TrackingQuality:
    matched_observations50: int
    id_switches: int
    fragmentations: int

    def as_dict(self) -> dict[str, int]:
        return {
            "fragmentations": self.fragmentations,
            "id_switches": self.id_switches,
            "matched_observations50": self.matched_observations50,
        }


@dataclass(frozen=True, slots=True)
class CostMetrics:
    decoded_frames: int
    selected_frames: int
    dropped_frames: int
    detector_latency_p50_ms: float
    detector_latency_p95_ms: float
    detector_fps: float
    pipeline_fps: float
    real_time_factor: float
    peak_vram_bytes: int | None
    device: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "decoded_frames": self.decoded_frames,
            "detector_fps": self.detector_fps,
            "detector_latency_p50_ms": self.detector_latency_p50_ms,
            "detector_latency_p95_ms": self.detector_latency_p95_ms,
            "device": self.device,
            "dropped_frames": self.dropped_frames,
            "peak_vram_bytes": self.peak_vram_bytes,
            "pipeline_fps": self.pipeline_fps,
            "real_time_factor": self.real_time_factor,
            "selected_frames": self.selected_frames,
        }


@dataclass(frozen=True, slots=True)
class RunEnvironment:
    python_version: str
    platform: str
    dependency_versions: tuple[tuple[str, str | None], ...]
    dependency_lock_hash: str | None
    code_revision: str | None
    dirty_worktree: bool | None
    seeds: tuple[tuple[str, str], ...]
    model_runtime: dict[str, Any]
    measurement_method: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "code_revision": self.code_revision,
            "dependency_lock_hash": self.dependency_lock_hash,
            "dependency_versions": dict(self.dependency_versions),
            "dirty_worktree": self.dirty_worktree,
            "measurement_method": self.measurement_method,
            "model_runtime": dict(self.model_runtime),
            "platform": self.platform,
            "python_version": self.python_version,
            "seeds": dict(self.seeds),
        }


@dataclass(frozen=True, slots=True)
class PerceptionEvaluationReport:
    source_id: str
    source_revision: str
    source_content_hash: str
    annotation_hash: str
    evaluator_version: str
    producer_ref: dict[str, str]
    control: dict[str, Any]
    quality: DetectionQuality
    tracking: TrackingQuality | None
    cost: CostMetrics
    environment: RunEnvironment
    evidence_limit: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "annotation_hash": self.annotation_hash,
            "control": dict(self.control),
            "cost": self.cost.as_dict(),
            "evaluator_version": self.evaluator_version,
            "evidence_limit": self.evidence_limit,
            "environment": self.environment.as_dict(),
            "producer_ref": dict(self.producer_ref),
            "quality": self.quality.as_dict(),
            "source_content_hash": self.source_content_hash,
            "source_id": self.source_id,
            "source_revision": self.source_revision,
            "tracking": None if self.tracking is None else self.tracking.as_dict(),
        }


def _dependency_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def collect_run_environment(
    detector: Detector,
    repository_root: str | Path | None,
    *,
    code_revision: str | None,
    dirty_worktree: bool | None,
) -> RunEnvironment:
    root = Path(repository_root).resolve() if repository_root is not None else None
    lock_path = root / "uv.lock" if root is not None else None
    lock_hash = (
        hashlib.sha256(lock_path.read_bytes()).hexdigest()
        if lock_path is not None and lock_path.is_file()
        else None
    )
    distributions = ("av", "numpy", "Pillow", "rfdetr", "torch", "torchvision")
    return RunEnvironment(
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        dependency_versions=tuple(
            (name, _dependency_version(name)) for name in distributions
        ),
        dependency_lock_hash=lock_hash,
        code_revision=code_revision,
        dirty_worktree=dirty_worktree,
        seeds=(("randomness", "not_used_by_this_deterministic_adapter"),),
        model_runtime=detector.runtime_metadata(),
        measurement_method=(
            "one excluded detector call on each of the first warmup_frames selected frames; "
            "wall-clock perf_counter around canonical detect calls; nearest-rank p50/p95; "
            "full decode-to-result wall time for pipeline FPS and real-time factor"
        ),
    )


def load_ground_truth(
    manifest: VideoSourceManifest,
) -> dict[int, tuple[GroundTruthObject, ...]]:
    document = json.loads(manifest.annotation_path.read_text(encoding="utf-8"))
    if (
        document.get("schema_version") != 1
        or document.get("coordinate_space") != "pixel_xyxy_exclusive"
        or document.get("width") != manifest.width
        or document.get("height") != manifest.height
    ):
        raise ValueError("ground-truth annotations disagree with the manifest")
    entity_labels = {
        item["entity_id"]: item["label"]
        for item in manifest.entities
        if set(item) == {"entity_id", "instance_count", "label"}
        and item.get("instance_count") == 1
    }
    if len(entity_labels) != len(manifest.entities):
        raise ValueError("evaluation requires one declared instance per entity")
    records = document.get("frames")
    if not isinstance(records, list) or len(records) != manifest.frame_count:
        raise ValueError("ground-truth frame list is invalid")
    result: dict[int, tuple[GroundTruthObject, ...]] = {}
    for expected_index, record in enumerate(records):
        if not isinstance(record, dict) or record.get("frame_index") != expected_index:
            raise ValueError("ground-truth frames must be complete and ordered")
        objects = record.get("objects")
        if not isinstance(objects, dict) or set(objects) != set(entity_labels):
            raise ValueError("ground-truth objects disagree with manifest entities")
        parsed: list[GroundTruthObject] = []
        for entity_id, coordinates in sorted(objects.items()):
            if coordinates is None:
                continue
            if (
                not isinstance(coordinates, list)
                or len(coordinates) != 4
                or any(type(value) not in {int, float} for value in coordinates)
            ):
                raise ValueError("ground-truth box is invalid")
            box = BoundingBox(*(float(value) for value in coordinates))
            if not box.within(width=manifest.width, height=manifest.height):
                raise ValueError("ground-truth box exceeds frame bounds")
            parsed.append(
                GroundTruthObject(
                    entity_id=entity_id,
                    label=entity_labels[entity_id],
                    bbox=box,
                )
            )
        result[expected_index] = tuple(parsed)
    return result


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _label_metrics(
    label: str,
    threshold: float,
    ground_truth: dict[int, tuple[GroundTruthObject, ...]],
    predictions: dict[int, tuple[Detection, ...]],
) -> tuple[float, int, int, int]:
    targets = {
        frame_index: tuple(item for item in items if item.label == label)
        for frame_index, items in ground_truth.items()
    }
    target_count = sum(len(items) for items in targets.values())
    ranked = sorted(
        (
            (detection.confidence, frame_index, prediction_index, detection)
            for frame_index, items in predictions.items()
            for prediction_index, detection in enumerate(items)
            if detection.label == label
        ),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    matched: dict[int, set[int]] = {}
    true_positives: list[int] = []
    false_positives: list[int] = []
    for _, frame_index, _, detection in ranked:
        available = targets.get(frame_index, ())
        already = matched.setdefault(frame_index, set())
        candidates = sorted(
            (
                (-detection.bbox.iou(target.bbox), target_index)
                for target_index, target in enumerate(available)
                if target_index not in already
                and detection.bbox.iou(target.bbox) >= threshold
            )
        )
        if candidates:
            target_index = candidates[0][1]
            already.add(target_index)
            true_positives.append(1)
            false_positives.append(0)
        else:
            true_positives.append(0)
            false_positives.append(1)
    cumulative_tp: list[int] = []
    cumulative_fp: list[int] = []
    for tp, fp in zip(true_positives, false_positives):
        cumulative_tp.append(tp + (cumulative_tp[-1] if cumulative_tp else 0))
        cumulative_fp.append(fp + (cumulative_fp[-1] if cumulative_fp else 0))
    if target_count == 0:
        return 0.0, 0, sum(false_positives), 0
    recalls = [value / target_count for value in cumulative_tp]
    precisions = [
        tp / max(1, tp + fp) for tp, fp in zip(cumulative_tp, cumulative_fp)
    ]
    interpolated = []
    for index in range(101):
        recall_threshold = index / 100
        eligible = [
            precision
            for recall, precision in zip(recalls, precisions)
            if recall >= recall_threshold
        ]
        interpolated.append(max(eligible, default=0.0))
    return (
        sum(interpolated) / len(interpolated),
        cumulative_tp[-1] if cumulative_tp else 0,
        cumulative_fp[-1] if cumulative_fp else 0,
        target_count,
    )


def evaluate_detection_quality(
    ground_truth: dict[int, tuple[GroundTruthObject, ...]],
    predictions: dict[int, tuple[Detection, ...]],
) -> DetectionQuality:
    labels = sorted(
        {item.label for items in ground_truth.values() for item in items}
        | {item.label for items in predictions.values() for item in items}
    )
    if not labels:
        raise ValueError("evaluation requires at least one label")
    ap_by_threshold: dict[float, list[float]] = {threshold: [] for threshold in IOU_THRESHOLDS}
    per_label_ap50: list[tuple[str, float]] = []
    total_tp50 = total_fp50 = total_gt = 0
    key_tp = key_gt = 0
    for label in labels:
        for threshold in IOU_THRESHOLDS:
            ap, tp, fp, target_count = _label_metrics(
                label, threshold, ground_truth, predictions
            )
            if target_count:
                ap_by_threshold[threshold].append(ap)
            if threshold == 0.5:
                per_label_ap50.append((label, ap))
                total_tp50 += tp
                total_fp50 += fp
                total_gt += target_count
                if label == "key":
                    key_tp = tp
                    key_gt = target_count
    threshold_means = [
        sum(values) / len(values) if values else 0.0
        for values in ap_by_threshold.values()
    ]
    return DetectionQuality(
        ap50=threshold_means[0],
        map50_95=sum(threshold_means) / len(threshold_means),
        recall50=total_tp50 / total_gt if total_gt else 0.0,
        key_recall50=key_tp / key_gt if key_gt else None,
        false_positives50=total_fp50,
        per_label_ap50=tuple(per_label_ap50),
    )


def evaluate_tracking_quality(
    ground_truth: dict[int, tuple[GroundTruthObject, ...]],
    observations: dict[int, tuple[TrackObservation, ...]],
) -> TrackingQuality:
    last_track: dict[str, str] = {}
    was_matched: dict[str, bool] = {}
    ever_matched: set[str] = set()
    id_switches = fragmentations = matched_count = 0
    for frame_index in sorted(ground_truth):
        frame_observations = observations.get(frame_index, ())
        used: set[int] = set()
        for target in ground_truth[frame_index]:
            candidates = sorted(
                (
                    (-target.bbox.iou(item.detection.bbox), index, item)
                    for index, item in enumerate(frame_observations)
                    if index not in used
                    and item.detection.label == target.label
                    and target.bbox.iou(item.detection.bbox) >= 0.5
                )
            )
            if not candidates:
                was_matched[target.entity_id] = False
                continue
            _, index, observation = candidates[0]
            used.add(index)
            matched_count += 1
            previous = last_track.get(target.entity_id)
            if previous is not None and previous != observation.track_id:
                id_switches += 1
            if target.entity_id in ever_matched and not was_matched.get(
                target.entity_id, False
            ):
                fragmentations += 1
            last_track[target.entity_id] = observation.track_id
            was_matched[target.entity_id] = True
            ever_matched.add(target.entity_id)
    return TrackingQuality(
        matched_observations50=matched_count,
        id_switches=id_switches,
        fragmentations=fragmentations,
    )


def evaluate_perception(
    manifest: VideoSourceManifest,
    detector: Detector,
    *,
    tracker: Tracker | None = None,
    scheduler: MotionPeriodicScheduler | None = None,
    warmup_frames: int = 1,
    repository_root: str | Path | None = None,
    code_revision: str | None = None,
    dirty_worktree: bool | None = None,
) -> PerceptionEvaluationReport:
    """Run one pinned source and return comparable quality/cost evidence."""

    if warmup_frames < 0:
        raise ValueError("warmup_frames cannot be negative")
    ground_truth = load_ground_truth(manifest)
    predictions: dict[int, tuple[Detection, ...]] = {}
    observations: dict[int, tuple[TrackObservation, ...]] = {}
    latencies_ms: list[float] = []
    decoded_count = selected_count = 0
    warmed = 0
    if tracker is not None:
        tracker.reset()
    pipeline_start = time.perf_counter()
    for frame in iter_decoded_frames(manifest):
        decoded_count += 1
        decision = scheduler.evaluate(frame) if scheduler is not None else None
        if decision is not None and not decision.selected:
            continue
        selected_count += 1
        if warmed < warmup_frames:
            detector.detect(frame)
            warmed += 1
        started = time.perf_counter()
        detections = detector.detect(frame)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        latencies_ms.append(elapsed_ms)
        if any(
            item.position != frame.position
            or not item.bbox.within(width=manifest.width, height=manifest.height)
            or item.producer_ref != detector.producer_ref
            for item in detections
        ):
            raise ValueError("detector violated the canonical output contract")
        frame_index = frame.position.frame_index
        if frame_index is None:
            raise ValueError("recorded-video evaluation requires frame indexes")
        predictions[frame_index] = detections
        if tracker is not None:
            observations[frame_index] = tracker.update(frame.position, detections)
    pipeline_elapsed = time.perf_counter() - pipeline_start
    if decoded_count != manifest.frame_count or selected_count == 0:
        raise ValueError("perception evaluation did not cover the declared replay")
    detector_seconds = sum(latencies_ms) / 1000.0
    duration_seconds = (
        manifest.frame_count * manifest.fps_denominator / manifest.fps_numerator
    )
    producer = detector.producer_ref
    return PerceptionEvaluationReport(
        source_id=manifest.descriptor.source_id,
        source_revision=manifest.descriptor.source_revision,
        source_content_hash=manifest.descriptor.content_hash,
        annotation_hash=manifest.annotation_hash,
        evaluator_version=EVALUATOR_VERSION,
        producer_ref={
            "artifact_hash": producer.artifact_hash,
            "component": producer.component,
            "config_hash": producer.config_hash,
            "version": producer.version,
        },
        control={
            "detection_iou_thresholds": list(IOU_THRESHOLDS),
            "scheduler": (
                None if scheduler is None else scheduler.resolved_config()
            ),
            "tracker": None if tracker is None else tracker.resolved_config(),
            "tracking_match_iou_threshold": 0.5,
            "warmup_frames": warmup_frames,
        },
        quality=evaluate_detection_quality(ground_truth, predictions),
        tracking=(
            evaluate_tracking_quality(ground_truth, observations)
            if tracker is not None
            else None
        ),
        cost=CostMetrics(
            decoded_frames=decoded_count,
            selected_frames=selected_count,
            dropped_frames=0,
            detector_latency_p50_ms=_percentile(latencies_ms, 0.50),
            detector_latency_p95_ms=_percentile(latencies_ms, 0.95),
            detector_fps=(selected_count / detector_seconds if detector_seconds else 0.0),
            pipeline_fps=(decoded_count / pipeline_elapsed if pipeline_elapsed else 0.0),
            real_time_factor=(pipeline_elapsed / duration_seconds),
            peak_vram_bytes=detector.peak_vram_bytes(),
            device=detector.device,
        ),
        environment=collect_run_environment(
            detector,
            repository_root,
            code_revision=code_revision,
            dirty_worktree=dirty_worktree,
        ),
        evidence_limit=(
            "Metrics apply only to this hash-pinned synthetic replay, adapter, "
            "configuration, interpreter, and machine; they do not establish indoor "
            "transfer, physical truth, real-time operation, or household readiness."
        ),
    )


def write_evaluation_report(
    report: PerceptionEvaluationReport, path: str | Path
) -> None:
    Path(path).write_text(
        json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
