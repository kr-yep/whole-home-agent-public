"""Run the frozen, development-only M11 VOST failure-localization diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from evaluation_cli_support import git_state, release_detector_runtime
from whole_home_agent.adapters.torchvision_coco import (
    TorchvisionCocoDetector,
    TorchvisionDiagnosticProposal,
    load_torchvision_coco_configs,
)
from whole_home_agent.adapters.tracking import IoUTracker, IoUTrackerConfig
from whole_home_agent.adapters.vost import (
    load_vost_motion_screen_manifest,
    load_vost_motion_sequence,
)
from whole_home_agent.evaluation import evaluate_tracking_quality
from whole_home_agent.model import ProducerRef
from whole_home_agent.perception import Detection, GroundTruthObject


CONTRACT_PATH = ROOT / "configs" / "evaluation" / "vost-m11-failure-localization-v1.toml"
CATEGORIES = (
    "target_absent_or_void",
    "no_bottle_proposal",
    "confidence_filtered_proposal",
    "localization_miss",
    "matched",
)
DETECTOR_MISSES = CATEGORIES[1:4]
SIZE_BUCKETS = ("tiny_lt_0.1pct", "small_0.1_to_1pct", "large_ge_1pct")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside_repo(value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field} must be a POSIX repository-relative path")
    relative = Path(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"{field} escaped the repository")
    resolved = (ROOT / relative).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError(f"{field} escaped the repository") from error
    return resolved


def _unit_float(value: object, *, field: str, upper_inclusive: bool = True) -> float:
    if type(value) not in {int, float}:
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    upper_ok = result <= 1.0 if upper_inclusive else result < 1.0
    if not math.isfinite(result) or result < 0.0 or not upper_ok:
        raise ValueError(f"{field} must be between zero and one")
    return result


@dataclass(frozen=True, slots=True)
class M11Contract:
    diagnostic_id: str
    source_config: Path
    source_config_sha256: str
    source_sequence_id: str
    source_split: str
    reserved_sequence_id: str
    model_config: Path
    model_config_sha256: str
    model_id: str
    target_label: str
    model_postprocess_score_floor: float
    diagnostic_score_floor: float
    product_confidence_threshold: float
    match_iou_threshold: float
    expected_frame_count: int
    expected_visible_target_frames: int
    expected_m10_matched_frames: int
    tiny_upper_area_fraction: float
    small_upper_area_fraction: float
    tracker_config: IoUTrackerConfig
    maximum_oracle_id_switches: int
    maximum_oracle_fragmentations: int
    minimum_matched_target_fraction: float
    dominance_minimum_miss_fraction: float
    candidates: dict[str, str]
    config_hash: str


def load_contract(path: Path = CONTRACT_PATH) -> M11Contract:
    raw = path.read_bytes()
    document = tomllib.loads(raw.decode("utf-8"))
    expected = {
        "schema_version",
        "status",
        "diagnostic_id",
        "intended_use",
        "source_config_path",
        "source_config_sha256",
        "source_sequence_id",
        "source_split",
        "reserved_sequence_id",
        "reserved_split_allowed",
        "model_config_path",
        "model_config_sha256",
        "model_id",
        "target_label",
        "model_postprocess_score_floor",
        "diagnostic_score_floor",
        "frozen_product_confidence_threshold",
        "match_iou_threshold",
        "conformance",
        "target_size",
        "oracle_tracker",
        "decision",
    }
    if set(document) != expected or document.get("schema_version") != 1:
        raise ValueError("M11 diagnostic contract schema is invalid")
    if (
        document["status"] != "FROZEN_BEFORE_DIAGNOSTIC_RUN"
        or document["intended_use"] != "DEVELOPMENT_ONLY_FAILURE_LOCALIZATION"
        or document["source_split"] != "development"
        or document["reserved_split_allowed"] is not False
        or document["source_sequence_id"] == document["reserved_sequence_id"]
    ):
        raise ValueError("M11 development-only boundary was loosened")
    conformance = document["conformance"]
    target_size = document["target_size"]
    oracle = document["oracle_tracker"]
    decision = document["decision"]
    if not isinstance(conformance, dict) or set(conformance) != {
        "expected_frame_count",
        "expected_visible_target_frames",
        "expected_m10_matched_frames",
    }:
        raise ValueError("M11 conformance block is invalid")
    if not isinstance(target_size, dict) or set(target_size) != {
        "tiny_upper_area_fraction",
        "small_upper_area_fraction",
    }:
        raise ValueError("M11 target-size block is invalid")
    if not isinstance(oracle, dict) or set(oracle) != {
        "match_iou_threshold",
        "max_missed_updates",
        "maximum_id_switches",
        "maximum_fragmentations",
    }:
        raise ValueError("M11 oracle-tracker block is invalid")
    decision_keys = {
        "minimum_matched_target_fraction",
        "dominance_minimum_miss_fraction",
        "detector_priority_when_below_match_gate",
        "no_proposal_candidate",
        "confidence_filtered_candidate",
        "localization_miss_candidate",
        "mixed_detector_candidate",
        "oracle_tracker_candidate",
        "pass_candidate",
    }
    if not isinstance(decision, dict) or set(decision) != decision_keys:
        raise ValueError("M11 decision block is invalid")
    if decision["detector_priority_when_below_match_gate"] is not True:
        raise ValueError("M11 detector-first decision priority was loosened")
    source_config = _inside_repo(document["source_config_path"], field="source_config_path")
    model_config = _inside_repo(document["model_config_path"], field="model_config_path")
    for configured, actual, name in (
        (document["source_config_sha256"], _sha256(source_config), "source"),
        (document["model_config_sha256"], _sha256(model_config), "model"),
    ):
        if configured != actual:
            raise ValueError(f"M11 {name} config hash changed after freeze")
    diagnostic_floor = _unit_float(
        document["diagnostic_score_floor"], field="diagnostic_score_floor"
    )
    product_threshold = _unit_float(
        document["frozen_product_confidence_threshold"],
        field="frozen_product_confidence_threshold",
    )
    model_floor = _unit_float(
        document["model_postprocess_score_floor"],
        field="model_postprocess_score_floor",
    )
    if not model_floor <= diagnostic_floor < product_threshold:
        raise ValueError("M11 diagnostic confidence intervals are invalid")
    tiny = _unit_float(
        target_size["tiny_upper_area_fraction"],
        field="tiny_upper_area_fraction",
        upper_inclusive=False,
    )
    small = _unit_float(
        target_size["small_upper_area_fraction"],
        field="small_upper_area_fraction",
        upper_inclusive=False,
    )
    if not 0.0 < tiny < small:
        raise ValueError("M11 target-size boundaries are invalid")
    integer_fields = {
        "expected_frame_count": conformance["expected_frame_count"],
        "expected_visible_target_frames": conformance["expected_visible_target_frames"],
        "expected_m10_matched_frames": conformance["expected_m10_matched_frames"],
        "max_missed_updates": oracle["max_missed_updates"],
        "maximum_id_switches": oracle["maximum_id_switches"],
        "maximum_fragmentations": oracle["maximum_fragmentations"],
    }
    if any(type(value) is not int or value < 0 for value in integer_fields.values()):
        raise ValueError("M11 count and tracker limits must be non-negative integers")
    if integer_fields["expected_frame_count"] <= 0:
        raise ValueError("M11 expected frame count must be positive")
    candidate_keys = {
        "no_bottle_proposal": "no_proposal_candidate",
        "confidence_filtered_proposal": "confidence_filtered_candidate",
        "localization_miss": "localization_miss_candidate",
        "mixed_detector_miss": "mixed_detector_candidate",
        "oracle_tracker": "oracle_tracker_candidate",
        "pass": "pass_candidate",
    }
    candidates = {name: decision[key] for name, key in candidate_keys.items()}
    if any(not isinstance(value, str) or not value for value in candidates.values()):
        raise ValueError("M11 candidate decisions must be non-empty strings")
    return M11Contract(
        diagnostic_id=document["diagnostic_id"],
        source_config=source_config,
        source_config_sha256=document["source_config_sha256"],
        source_sequence_id=document["source_sequence_id"],
        source_split=document["source_split"],
        reserved_sequence_id=document["reserved_sequence_id"],
        model_config=model_config,
        model_config_sha256=document["model_config_sha256"],
        model_id=document["model_id"],
        target_label=document["target_label"],
        model_postprocess_score_floor=model_floor,
        diagnostic_score_floor=diagnostic_floor,
        product_confidence_threshold=product_threshold,
        match_iou_threshold=_unit_float(
            document["match_iou_threshold"], field="match_iou_threshold"
        ),
        expected_frame_count=integer_fields["expected_frame_count"],
        expected_visible_target_frames=integer_fields["expected_visible_target_frames"],
        expected_m10_matched_frames=integer_fields["expected_m10_matched_frames"],
        tiny_upper_area_fraction=tiny,
        small_upper_area_fraction=small,
        tracker_config=IoUTrackerConfig(
            match_iou_threshold=_unit_float(
                oracle["match_iou_threshold"], field="oracle.match_iou_threshold"
            ),
            max_missed_updates=integer_fields["max_missed_updates"],
        ),
        maximum_oracle_id_switches=integer_fields["maximum_id_switches"],
        maximum_oracle_fragmentations=integer_fields["maximum_fragmentations"],
        minimum_matched_target_fraction=_unit_float(
            decision["minimum_matched_target_fraction"],
            field="minimum_matched_target_fraction",
        ),
        dominance_minimum_miss_fraction=_unit_float(
            decision["dominance_minimum_miss_fraction"],
            field="dominance_minimum_miss_fraction",
        ),
        candidates=candidates,
        config_hash=hashlib.sha256(raw).hexdigest(),
    )


def _size_bucket(target: GroundTruthObject, *, frame_area: int, contract: M11Contract) -> str:
    ratio = target.bbox.area / frame_area
    if ratio < contract.tiny_upper_area_fraction:
        return SIZE_BUCKETS[0]
    if ratio < contract.small_upper_area_fraction:
        return SIZE_BUCKETS[1]
    return SIZE_BUCKETS[2]


def classify_visible_target(
    target: GroundTruthObject,
    proposals: tuple[TorchvisionDiagnosticProposal, ...],
    *,
    contract: M11Contract,
) -> tuple[str, dict[str, object]]:
    relevant = tuple(item for item in proposals if item.label == contract.target_label)
    product = tuple(
        item
        for item in relevant
        if item.confidence >= contract.product_confidence_threshold
    )
    best_any_iou = max((item.bbox.iou(target.bbox) for item in relevant), default=0.0)
    best_product_iou = max(
        (item.bbox.iou(target.bbox) for item in product), default=0.0
    )
    if not relevant:
        category = "no_bottle_proposal"
    elif not product:
        category = "confidence_filtered_proposal"
    elif best_product_iou < contract.match_iou_threshold:
        category = "localization_miss"
    else:
        category = "matched"
    return category, {
        "best_iou_at_or_above_diagnostic_floor": best_any_iou,
        "best_iou_at_or_above_product_threshold": best_product_iou,
        "diagnostic_proposal_count": len(relevant),
        "maximum_bottle_score": max(
            (item.confidence for item in relevant), default=None
        ),
        "product_proposal_count": len(product),
    }


def select_next_candidate(
    category_counts: dict[str, int],
    *,
    visible_target_frames: int,
    oracle_id_switches: int,
    oracle_fragmentations: int,
    contract: M11Contract,
) -> dict[str, object]:
    matched_fraction = (
        category_counts.get("matched", 0) / visible_target_frames
        if visible_target_frames
        else 0.0
    )
    oracle_passed = (
        oracle_id_switches <= contract.maximum_oracle_id_switches
        and oracle_fragmentations <= contract.maximum_oracle_fragmentations
    )
    miss_counts = {name: category_counts.get(name, 0) for name in DETECTOR_MISSES}
    total_misses = sum(miss_counts.values())
    maximum = max(miss_counts.values(), default=0)
    leaders = [name for name, count in miss_counts.items() if count == maximum and count > 0]
    dominant = (
        leaders[0]
        if len(leaders) == 1
        and total_misses > 0
        and maximum / total_misses >= contract.dominance_minimum_miss_fraction
        else "mixed_detector_miss"
    )
    if matched_fraction < contract.minimum_matched_target_fraction:
        bottleneck = dominant
        candidate = contract.candidates[dominant]
        verdict = "DETECTOR_FAILURE_LOCALIZED"
    elif not oracle_passed:
        bottleneck = "oracle_tracker"
        candidate = contract.candidates["oracle_tracker"]
        verdict = "TRACKER_FAILURE_LOCALIZED"
    else:
        bottleneck = "none"
        candidate = contract.candidates["pass"]
        verdict = "NO_LOCALIZED_FAILURE"
    return {
        "bottleneck": bottleneck,
        "candidate": candidate,
        "detector_priority_applied": matched_fraction
        < contract.minimum_matched_target_fraction,
        "dominant_miss_fraction": maximum / total_misses if total_misses else None,
        "matched_target_fraction": matched_fraction,
        "miss_counts": miss_counts,
        "oracle_tracker_passed": oracle_passed,
        "verdict": verdict,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Localize frozen M10 RetinaNet misses on development only."
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    revision, dirty = git_state(ROOT)
    contract = load_contract()
    dataset = load_vost_motion_screen_manifest(
        contract.source_config, repository_root=ROOT
    )
    source_spec = dataset.sequence(contract.source_sequence_id)
    if (
        source_spec.split != contract.source_split
        or contract.source_sequence_id == contract.reserved_sequence_id
        or dataset.target_label != contract.target_label
    ):
        raise ValueError("M11 source identity or target mapping changed after freeze")
    source = load_vost_motion_sequence(dataset, contract.source_sequence_id)
    if source.split != "development" or source.frame_count != contract.expected_frame_count:
        raise ValueError("M11 source escaped the frozen development envelope")
    model_configs = load_torchvision_coco_configs(
        contract.model_config,
        repository_root=ROOT,
        device=args.device,
    )
    model_config = next(
        (item for item in model_configs if item.model_id == contract.model_id), None
    )
    if (
        model_config is None
        or model_config.confidence_threshold != contract.product_confidence_threshold
    ):
        raise ValueError("M11 frozen model or product threshold changed")

    detector = TorchvisionCocoDetector(model_config)
    oracle_tracker = IoUTracker(contract.tracker_config)
    oracle_producer = ProducerRef(
        component="vost-mask-box-oracle",
        version="1",
        artifact_hash=source.annotation_hash,
        config_hash=contract.config_hash,
    )
    category_counts: Counter[str] = Counter()
    size_category_counts = {
        size: {category: 0 for category in CATEGORIES} for size in SIZE_BUCKETS
    }
    frames: list[dict[str, object]] = []
    oracle_observations = {}
    model_floor_seen: float | None = None
    product_output_count = 0
    try:
        oracle_tracker.reset()
        for expected_index, frame in enumerate(source.iter_frames()):
            if frame.position.frame_index != expected_index:
                raise ValueError("M11 source order changed during replay")
            batch = detector.detect_with_diagnostics(
                frame,
                diagnostic_score_floor=contract.diagnostic_score_floor,
            )
            if batch.model_postprocess_score_floor is None or not math.isclose(
                batch.model_postprocess_score_floor,
                contract.model_postprocess_score_floor,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("M11 model post-process score floor changed")
            model_floor_seen = batch.model_postprocess_score_floor
            product_output_count += len(batch.product_detections)
            expected_product = tuple(
                (item.label, item.confidence, item.bbox.as_xyxy())
                for item in batch.diagnostic_proposals
                if item.confidence >= contract.product_confidence_threshold
            )
            actual_product = tuple(
                (item.label, item.confidence, item.bbox.as_xyxy())
                for item in batch.product_detections
            )
            if actual_product != expected_product:
                raise ValueError("M11 diagnostic seam changed frozen product output")
            targets = source.ground_truth[expected_index]
            if len(targets) > 1:
                raise ValueError("M11 contract permits at most one target per frame")
            oracle_detections: tuple[Detection, ...]
            if not targets:
                category = "target_absent_or_void"
                details = {
                    "best_iou_at_or_above_diagnostic_floor": None,
                    "best_iou_at_or_above_product_threshold": None,
                    "diagnostic_proposal_count": sum(
                        item.label == contract.target_label
                        for item in batch.diagnostic_proposals
                    ),
                    "maximum_bottle_score": max(
                        (
                            item.confidence
                            for item in batch.diagnostic_proposals
                            if item.label == contract.target_label
                        ),
                        default=None,
                    ),
                    "product_proposal_count": sum(
                        item.label == contract.target_label
                        for item in batch.product_detections
                    ),
                }
                size_bucket = None
                target_area_fraction = None
                oracle_detections = ()
            else:
                target = targets[0]
                category, details = classify_visible_target(
                    target,
                    batch.diagnostic_proposals,
                    contract=contract,
                )
                size_bucket = _size_bucket(
                    target,
                    frame_area=source.width * source.height,
                    contract=contract,
                )
                target_area_fraction = target.bbox.area / (source.width * source.height)
                size_category_counts[size_bucket][category] += 1
                oracle_detections = (
                    Detection(
                        label=target.label,
                        confidence=1.0,
                        bbox=target.bbox,
                        position=frame.position,
                        producer_ref=oracle_producer,
                    ),
                )
            category_counts[category] += 1
            oracle_observations[expected_index] = oracle_tracker.update(
                frame.position, oracle_detections
            )
            frames.append(
                {
                    "category": category,
                    "frame_index": expected_index,
                    "size_bucket": size_bucket,
                    "source_offset": frame.position.source_offset,
                    "target_area_fraction": target_area_fraction,
                    **details,
                }
            )
    finally:
        runtime = detector.runtime_metadata()
        peak_vram = detector.peak_vram_bytes()
        del detector
        release_detector_runtime()

    if sum(category_counts.values()) != contract.expected_frame_count:
        raise ValueError("M11 classification is not exhaustive")
    if set(category_counts) - set(CATEGORIES):
        raise ValueError("M11 emitted an undeclared category")
    visible_target_frames = contract.expected_frame_count - category_counts[
        "target_absent_or_void"
    ]
    if visible_target_frames != contract.expected_visible_target_frames:
        raise ValueError("M11 visible-target count disagrees with M10")
    if category_counts["matched"] != contract.expected_m10_matched_frames:
        raise ValueError("M11 product-output matches do not reproduce M10")
    oracle_quality = evaluate_tracking_quality(source.ground_truth, oracle_observations)
    decision = select_next_candidate(
        dict(category_counts),
        visible_target_frames=visible_target_frames,
        oracle_id_switches=oracle_quality.id_switches,
        oracle_fragmentations=oracle_quality.fragmentations,
        contract=contract,
    )
    created_at = datetime.now(UTC).replace(microsecond=0)
    receipt = {
        "claim_ledger": [
            {
                "claim_id": "M11-C1",
                "evidence_class": "integrity/executable",
                "permissible": "One frozen development sequence was classified once under the pinned thresholds.",
                "forbidden": "The reserved validation sequence or household scenes have the same distribution.",
            },
            {
                "claim_id": "M11-C2",
                "evidence_class": "behavioral/descriptive",
                "permissible": "The recorded category counts localize this model path's misses on this sequence.",
                "forbidden": "The diagnostic categories establish the causal reason for every miss.",
            },
            {
                "claim_id": "M11-C3",
                "evidence_class": "behavioral/descriptive",
                "permissible": "The oracle-box result tests this tracker on the source mask boxes only.",
                "forbidden": "An oracle pass proves robust association under detector noise or a stable camera.",
            },
        ],
        "code_revision": revision,
        "config_hash": contract.config_hash,
        "created_at_utc": created_at.isoformat().replace("+00:00", "Z"),
        "decision": decision,
        "diagnostic_id": contract.diagnostic_id,
        "dirty_worktree": dirty,
        "evidence_limit": (
            "Development-only, single-sequence descriptive diagnosis. Low-score proposals "
            "are evaluation data, not product detections, observations, claims, or truth."
        ),
        "experiment_status": "VALID",
        "frame_categories": frames,
        "model_inference_calls": contract.expected_frame_count,
        "model_postprocess_score_floor": model_floor_seen,
        "operate": "DISABLED",
        "oracle_tracker": {
            "fragmentations": oracle_quality.fragmentations,
            "id_switches": oracle_quality.id_switches,
            "matched_observations50": oracle_quality.matched_observations50,
            "resolved_config": oracle_tracker.resolved_config(),
        },
        "product_output_count": product_output_count,
        "reserved_sequence_id": contract.reserved_sequence_id,
        "reserved_sequence_loaded": False,
        "runtime": {**runtime, "peak_vram_bytes": peak_vram},
        "schema_version": 1,
        "source": {
            "annotation_hash": source.annotation_hash,
            "config_hash": dataset.config_hash,
            "frame_count": source.frame_count,
            "sequence_id": contract.source_sequence_id,
            "split": source.split,
        },
        "summary": {
            "category_counts": {
                category: category_counts[category] for category in CATEGORIES
            },
            "size_by_category": size_category_counts,
            "visible_target_frames": visible_target_frames,
        },
        "test_source_used": False,
        "thresholds": {
            "diagnostic_score_floor": contract.diagnostic_score_floor,
            "match_iou_threshold": contract.match_iou_threshold,
            "product_confidence_threshold": contract.product_confidence_threshold,
        },
        "validation_run": False,
    }
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ") + "-" + revision[:8]
    output_dir = ROOT / "runs" / contract.diagnostic_id / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "receipt.json"
    output_path.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "decision": decision,
                "oracle_tracker": receipt["oracle_tracker"],
                "output": output_path.as_posix(),
                "summary": receipt["summary"],
                "validation_run": False,
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
