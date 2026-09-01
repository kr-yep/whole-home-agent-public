"""Run one development/validation-only sliced-inference Reality Gate."""

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

from whole_home_agent.adapters.slicing import (
    SlicedDetector,
    load_sliced_validation_gate,
)
from whole_home_agent.adapters.torchvision_coco import (
    TorchvisionCocoDetector,
    load_torchvision_coco_configs,
)
from whole_home_agent.adapters.visor import (
    load_visor_frame_set,
    load_visor_screen_manifest,
)
from whole_home_agent.evaluation import evaluate_frame_set
from evaluation_cli_support import git_state


VISOR_CONFIG = ROOT / "configs" / "evaluation" / "visor-screen-v1.toml"
MODEL_CONFIG = ROOT / "configs" / "perception" / "torchvision-coco-baselines-v1.toml"
SLICE_CONFIG = ROOT / "configs" / "perception" / "sliced-ssdlite-validation-v1.toml"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fixed VISOR development/validation sliced detector gate."
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser


def _small_recall(report: dict[str, object]) -> float | None:
    return report["quality"]["size_recall50"]["small_0.1_to_1pct"]


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    revision, dirty = git_state(ROOT)
    dataset = load_visor_screen_manifest(VISOR_CONFIG, repository_root=ROOT)
    gate = load_sliced_validation_gate(SLICE_CONFIG)
    model_configs = load_torchvision_coco_configs(
        MODEL_CONFIG,
        repository_root=ROOT,
        device=args.device,
    )
    model_config = next(
        (item for item in model_configs if item.model_id == gate.base_model_id),
        None,
    )
    if model_config is None:
        raise ValueError("slice gate base model is absent from the frozen model config")
    base = TorchvisionCocoDetector(model_config)
    sliced = SlicedDetector(base, gate.detector)
    reports: list[dict[str, object]] = []
    for sequence_spec in dataset.sequences:
        if sequence_spec.split == "test":
            continue
        source = load_visor_frame_set(dataset, sequence_spec.sequence_id)
        for variant, detector in (("base", base), ("sliced", sliced)):
            report = evaluate_frame_set(
                source,
                detector,
                warmup_frames=1,
                repository_root=ROOT,
                code_revision=revision,
                dirty_worktree=dirty,
            ).as_dict()
            report["candidate_variant"] = variant
            reports.append(report)
    validation = {
        report["candidate_variant"]: report
        for report in reports
        if report["control"]["evaluation_split"] == gate.selection_split
    }
    base_validation = validation["base"]
    sliced_validation = validation["sliced"]
    overall_gain = (
        sliced_validation["quality"]["recall50"]
        - base_validation["quality"]["recall50"]
    )
    base_small = _small_recall(base_validation)
    sliced_small = _small_recall(sliced_validation)
    small_gain = (
        sliced_small - base_small
        if base_small is not None and sliced_small is not None
        else None
    )
    quality_pass = overall_gain >= gate.min_validation_overall_recall_gain or (
        small_gain is not None
        and small_gain >= gate.min_validation_small_recall_gain
    )
    p95 = sliced_validation["cost"]["detector_latency_p95_ms"]
    vram = sliced_validation["cost"]["peak_vram_bytes"]
    cost_pass = p95 <= gate.max_detector_p95_ms and (
        vram is not None and vram <= gate.max_peak_vram_bytes
    )
    passed = quality_pass and cost_pass
    gate_result = {
        "cost_pass": cost_pass,
        "decision": "KEEP_FOR_FURTHER_SCREENING" if passed else "REJECT_CANDIDATE",
        "overall_recall_gain": overall_gain,
        "passed": passed,
        "quality_pass": quality_pass,
        "small_recall_gain": small_gain,
        "thresholds": {
            "max_detector_p95_ms": gate.max_detector_p95_ms,
            "max_peak_vram_bytes": gate.max_peak_vram_bytes,
            "min_validation_overall_recall_gain": gate.min_validation_overall_recall_gain,
            "min_validation_small_recall_gain": gate.min_validation_small_recall_gain,
        },
    }
    created_at = datetime.now(UTC).replace(microsecond=0)
    receipt = {
        "created_at_utc": created_at.isoformat().replace("+00:00", "Z"),
        "dataset_config_hash": dataset.config_hash,
        "frozen_test_included": False,
        "gate": gate_result,
        "operate": "DISABLED",
        "reports": reports,
        "schema_version": 1,
        "slice_config_hash": gate.config_hash,
    }
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ") + "-" + revision[:8]
    output_dir = ROOT / "runs" / "visor-slice-gate-v1" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "receipt.json"
    output_path.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"gate": gate_result, "output": output_path.as_posix()},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
