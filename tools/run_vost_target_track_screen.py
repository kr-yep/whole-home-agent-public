"""Run the frozen VOST bottle detection/tracking feasibility gate."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from evaluation_cli_support import git_state, release_detector_runtime
from whole_home_agent.adapters.motion import MotionPeriodicScheduler
from whole_home_agent.adapters.torchvision_coco import (
    TorchvisionCocoDetector,
    load_torchvision_coco_configs,
)
from whole_home_agent.adapters.tracking import IoUTracker
from whole_home_agent.adapters.vost import (
    TargetTrackingCriteria,
    VostMotionSequence,
    load_vost_motion_screen_manifest,
    load_vost_motion_sequence,
)
from whole_home_agent.evaluation import PerceptionEvaluationReport, evaluate_frame_set
from whole_home_agent.motion_evaluation import MotionScreenReport, evaluate_motion_screen


DATA_CONFIG = ROOT / "configs" / "evaluation" / "vost-target-track-screen-v1.toml"
MODEL_CONFIG = ROOT / "configs" / "perception" / "torchvision-coco-baselines-v1.toml"
MODEL_ID = "retinanet-resnet50-fpn-v2-coco-v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate target-aware RetinaNet detection/tracking on VOST bottles."
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser


def _run_perception(
    source: VostMotionSequence,
    model_config,
    *,
    revision: str,
    dirty: bool,
) -> PerceptionEvaluationReport:
    detector = TorchvisionCocoDetector(model_config)
    try:
        return evaluate_frame_set(
            source,
            detector,
            tracker=IoUTracker(),
            warmup_frames=1,
            repository_root=ROOT,
            code_revision=revision,
            dirty_worktree=dirty,
        )
    finally:
        del detector
        release_detector_runtime()


def _run_motion(
    source: VostMotionSequence,
    model_config,
    *,
    scheduler: MotionPeriodicScheduler | None,
    revision: str,
    dirty: bool,
) -> MotionScreenReport:
    detector = TorchvisionCocoDetector(model_config)
    try:
        return evaluate_motion_screen(
            source,
            detector,
            scheduler=scheduler,
            warmup_frames=1,
            repository_root=ROOT,
            code_revision=revision,
            dirty_worktree=dirty,
        )
    finally:
        del detector
        release_detector_runtime()


def _check(actual, operator: str, threshold, passed: bool) -> dict[str, object]:
    return {
        "actual": actual,
        "operator": operator,
        "passed": passed,
        "threshold": threshold,
    }


def _gate(
    source: VostMotionSequence,
    criteria: TargetTrackingCriteria,
    motion_criteria,
    perception: PerceptionEvaluationReport,
    full_motion: MotionScreenReport,
    scheduled_motion: MotionScreenReport,
    *,
    success_decision: str,
    failure_decision: str,
) -> dict[str, object]:
    tracking = perception.tracking
    if tracking is None:
        raise ValueError("target tracking gate requires tracker metrics")
    full_coverage = full_motion.target_detection_coverage
    scheduled_coverage = scheduled_motion.target_detection_coverage
    if full_coverage is None or scheduled_coverage is None:
        raise ValueError("target tracking gate requires target mask ground truth")
    annotated_frames = sum(bool(targets) for targets in source.ground_truth.values())
    if annotated_frames == 0:
        raise ValueError("target tracking gate has no visible target frames")
    matched_fraction = tracking.matched_observations50 / annotated_frames
    full_event_coverage = full_coverage.same_or_following_recall
    scheduled_event_coverage = scheduled_coverage.same_or_following_recall
    retention = (
        scheduled_event_coverage / full_event_coverage
        if full_event_coverage > 0.0
        else 0.0
    )
    p95 = scheduled_motion.cost.detector_latency_p95_ms
    vram = scheduled_motion.cost.peak_vram_bytes
    checks = {
        "full_frame_recall50": _check(
            perception.quality.recall50,
            ">=",
            criteria.minimum_full_frame_recall50,
            perception.quality.recall50 >= criteria.minimum_full_frame_recall50,
        ),
        "matched_observation_fraction": _check(
            matched_fraction,
            ">=",
            criteria.minimum_matched_observation_fraction,
            matched_fraction >= criteria.minimum_matched_observation_fraction,
        ),
        "id_switches": _check(
            tracking.id_switches,
            "<=",
            criteria.maximum_id_switches,
            tracking.id_switches <= criteria.maximum_id_switches,
        ),
        "fragmentations": _check(
            tracking.fragmentations,
            "<=",
            criteria.maximum_fragmentations,
            tracking.fragmentations <= criteria.maximum_fragmentations,
        ),
        "scheduled_target_event_coverage": _check(
            scheduled_event_coverage,
            ">=",
            criteria.minimum_scheduled_target_event_coverage,
            scheduled_event_coverage
            >= criteria.minimum_scheduled_target_event_coverage,
        ),
        "scheduled_target_event_retention": _check(
            retention,
            ">=",
            criteria.minimum_scheduled_target_event_retention,
            retention >= criteria.minimum_scheduled_target_event_retention,
        ),
        "scheduler_mask_change_coverage": _check(
            scheduled_motion.coverage.same_or_following_recall,
            ">=",
            motion_criteria.minimum_validation_mask_change_coverage,
            scheduled_motion.coverage.same_or_following_recall
            >= motion_criteria.minimum_validation_mask_change_coverage,
        ),
        "avoided_detector_fraction": _check(
            scheduled_motion.cost.avoided_detector_fraction,
            ">=",
            motion_criteria.minimum_validation_avoided_detector_fraction,
            scheduled_motion.cost.avoided_detector_fraction
            >= motion_criteria.minimum_validation_avoided_detector_fraction,
        ),
        "detector_p95_ms": _check(
            p95,
            "<=",
            motion_criteria.maximum_detector_p95_ms,
            p95 <= motion_criteria.maximum_detector_p95_ms,
        ),
        "peak_vram_bytes": _check(
            vram,
            "<=",
            motion_criteria.maximum_peak_vram_bytes,
            vram is not None and vram <= motion_criteria.maximum_peak_vram_bytes,
        ),
    }
    passed = all(bool(item["passed"]) for item in checks.values())
    return {
        "annotated_frames": annotated_frames,
        "checks": checks,
        "decision": success_decision if passed else failure_decision,
        "full_frame_target_event_coverage": full_event_coverage,
        "passed": passed,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    revision, dirty = git_state(ROOT)
    dataset = load_vost_motion_screen_manifest(DATA_CONFIG, repository_root=ROOT)
    if dataset.target_label != "bottle" or dataset.target_tracking_gate is None:
        raise ValueError("frozen VOST bottle target gate is missing")
    model_configs = load_torchvision_coco_configs(
        MODEL_CONFIG,
        repository_root=ROOT,
        device=args.device,
    )
    model_config = next(
        (item for item in model_configs if item.model_id == MODEL_ID),
        None,
    )
    if model_config is None:
        raise ValueError("frozen RetinaNet-FPN model config is missing")

    reports: list[dict[str, object]] = []
    development = load_vost_motion_sequence(
        dataset, dataset.sequence("3518_unscrew_bottle").sequence_id
    )
    development_perception = _run_perception(
        development, model_config, revision=revision, dirty=dirty
    )
    development_full = _run_motion(
        development,
        model_config,
        scheduler=None,
        revision=revision,
        dirty=dirty,
    )
    development_scheduled = _run_motion(
        development,
        model_config,
        scheduler=MotionPeriodicScheduler(dataset.scheduler),
        revision=revision,
        dirty=dirty,
    )
    reports.append(
        {
            "perception": development_perception.as_dict(),
            "full_frame_motion": development_full.as_dict(),
            "scheduled_motion": development_scheduled.as_dict(),
            "split": "development",
        }
    )
    development_gate = _gate(
        development,
        dataset.target_tracking_gate,
        dataset.gate,
        development_perception,
        development_full,
        development_scheduled,
        success_decision="CONTINUE_TO_VALIDATION",
        failure_decision="REJECT_ON_DEVELOPMENT",
    )

    validation_gate = None
    if development_gate["passed"]:
        validation = load_vost_motion_sequence(
            dataset, dataset.sequence("3510_unscrew_bottle").sequence_id
        )
        validation_perception = _run_perception(
            validation, model_config, revision=revision, dirty=dirty
        )
        validation_full = _run_motion(
            validation,
            model_config,
            scheduler=None,
            revision=revision,
            dirty=dirty,
        )
        validation_scheduled = _run_motion(
            validation,
            model_config,
            scheduler=MotionPeriodicScheduler(dataset.scheduler),
            revision=revision,
            dirty=dirty,
        )
        reports.append(
            {
                "perception": validation_perception.as_dict(),
                "full_frame_motion": validation_full.as_dict(),
                "scheduled_motion": validation_scheduled.as_dict(),
                "split": "validation",
            }
        )
        validation_gate = _gate(
            validation,
            dataset.target_tracking_gate,
            dataset.gate,
            validation_perception,
            validation_full,
            validation_scheduled,
            success_decision="CONTINUE_TO_MOVEMENT_CANDIDATE_GATE",
            failure_decision="REJECT_ON_VALIDATION",
        )

    final_gate = validation_gate or development_gate
    created_at = datetime.now(UTC).replace(microsecond=0)
    receipt = {
        "created_at_utc": created_at.isoformat().replace("+00:00", "Z"),
        "dataset_config_hash": dataset.config_hash,
        "development_gate": development_gate,
        "evidence_limit": (
            "This screen tests one explicit VOST mask-to-COCO bottle mapping on "
            "egocentric prerecorded sources. It does not prove spatial movement, "
            "containment, fixed-camera transfer, household truth, or live operation."
        ),
        "final_decision": final_gate["decision"],
        "label_review": {
            item.split: {
                "agent_visual_precheck": "MASK_ALIGNS_WITH_VISIBLE_BOTTLE_IN_SAMPLES",
                "source_offsets": list(item.label_review_source_offsets),
            }
            for item in dataset.sequences
        },
        "operate": "DISABLED",
        "reports": reports,
        "schema_version": 1,
        "test_source_used": False,
        "validation_gate": validation_gate,
    }
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ") + "-" + revision[:8]
    output_dir = ROOT / "runs" / "vost-target-track-screen-v1" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "receipt.json"
    output_path.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "development_gate": development_gate,
                "final_decision": final_gate["decision"],
                "output": output_path.as_posix(),
                "validation_gate": validation_gate,
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
