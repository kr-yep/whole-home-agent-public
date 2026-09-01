"""Run the frozen VOST motion-gate screen with full-frame RetinaNet-FPN."""

from __future__ import annotations

import argparse
import gc
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from whole_home_agent.adapters.motion import MotionPeriodicScheduler, MotionScheduleConfig
from whole_home_agent.adapters.torchvision_coco import (
    TorchvisionCocoDetector,
    load_torchvision_coco_configs,
)
from whole_home_agent.adapters.vost import (
    load_vost_motion_screen_manifest,
    load_vost_motion_sequence,
)
from whole_home_agent.motion_evaluation import (
    decide_motion_gate,
    evaluate_motion_screen,
    evaluate_scheduler_selection,
)


DATA_CONFIG = ROOT / "configs" / "evaluation" / "vost-motion-screen-v1.toml"
MODEL_CONFIG = ROOT / "configs" / "perception" / "torchvision-coco-baselines-v1.toml"
MODEL_ID = "retinanet-resnet50-fpn-v2-coco-v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate frozen motion-plus-periodic scheduling on VOST."
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser


def _git_state() -> tuple[str, bool]:
    safe = f"safe.directory={ROOT.as_posix()}"
    revision = subprocess.run(
        ["git", "-c", safe, "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "-c", safe, "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    )
    return revision, dirty


def _release_detector_runtime() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    revision, dirty = _git_state()
    dataset = load_vost_motion_screen_manifest(DATA_CONFIG, repository_root=ROOT)
    sources = {
        spec.split: load_vost_motion_sequence(dataset, spec.sequence_id)
        for spec in dataset.sequences
    }

    development = sources["development"]
    candidate_reports = []
    for threshold in dataset.development_candidate_motion_thresholds:
        config = MotionScheduleConfig(
            motion_threshold=threshold,
            min_gap_frames=dataset.scheduler.min_gap_frames,
            anchor_interval_frames=dataset.scheduler.anchor_interval_frames,
            sample_stride=dataset.scheduler.sample_stride,
        )
        report = evaluate_scheduler_selection(
            development,
            MotionPeriodicScheduler(config),
        )
        candidate_reports.append(report)
    eligible = [
        item
        for item in candidate_reports
        if item.coverage.same_or_following_recall
        >= dataset.development_selection_minimum_mask_change_coverage
    ]
    if not eligible:
        raise RuntimeError("no development-only scheduler candidate passed coverage")
    selected_candidate = max(
        eligible,
        key=lambda item: (
            item.avoided_detector_fraction,
            float(item.scheduler["motion_threshold"]),
        ),
    )
    if selected_candidate.scheduler != MotionPeriodicScheduler(
        dataset.scheduler
    ).resolved_config():
        raise RuntimeError("frozen scheduler disagrees with development-only selection")

    model_configs = load_torchvision_coco_configs(
        MODEL_CONFIG,
        repository_root=ROOT,
        device=args.device,
    )
    matches = [item for item in model_configs if item.model_id == MODEL_ID]
    if len(matches) != 1:
        raise RuntimeError("frozen RetinaNet-FPN model config is missing or ambiguous")
    model_config = matches[0]

    reports = []
    for split in ("development", "validation"):
        source = sources[split]
        for mode in ("full_frame", "motion_plus_periodic"):
            detector = TorchvisionCocoDetector(model_config)
            scheduler = (
                None
                if mode == "full_frame"
                else MotionPeriodicScheduler(dataset.scheduler)
            )
            report = evaluate_motion_screen(
                source,
                detector,
                scheduler=scheduler,
                warmup_frames=1,
                repository_root=ROOT,
                code_revision=revision,
                dirty_worktree=dirty,
            )
            reports.append(report)
            del detector
            _release_detector_runtime()

    validation_scheduled = next(
        item
        for item in reports
        if item.split == "validation" and item.mode == "motion_plus_periodic"
    )
    gate = decide_motion_gate(dataset.gate, validation_scheduled)
    created_at = datetime.now(UTC).replace(microsecond=0)
    receipt = {
        "schema_version": 1,
        "created_at_utc": created_at.isoformat().replace("+00:00", "Z"),
        "dataset_config_hash": dataset.config_hash,
        "development_candidate_reports": [item.as_dict() for item in candidate_reports],
        "development_selected_scheduler": selected_candidate.scheduler,
        "gate": gate.as_dict(),
        "operate": "DISABLED",
        "reports": [item.as_dict() for item in reports],
        "test_source_used": False,
    }
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ") + "-" + revision[:8]
    output_dir = ROOT / "runs" / "vost-motion-screen-v1" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "receipt.json"
    output_path.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = [
        {
            "avoided_detector_fraction": item.cost.avoided_detector_fraction,
            "detector_calls": item.cost.detector_calls,
            "detector_p95_ms": item.cost.detector_latency_p95_ms,
            "mask_change_coverage": item.coverage.same_or_following_recall,
            "mode": item.mode,
            "peak_vram_bytes": item.cost.peak_vram_bytes,
            "source": item.source_id,
            "split": item.split,
        }
        for item in reports
    ]
    print(
        json.dumps(
            {
                "gate": gate.decision,
                "output": output_path.as_posix(),
                "summary": summary,
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
