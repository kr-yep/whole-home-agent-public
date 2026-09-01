"""Run the frozen VISOR sparse-frame detector comparison and write a receipt."""

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

from whole_home_agent.adapters.torchvision_coco import (
    TorchvisionCocoDetector,
    load_torchvision_coco_configs,
)
from whole_home_agent.adapters.visor import (
    load_visor_frame_set,
    load_visor_screen_manifest,
)
from whole_home_agent.evaluation import evaluate_frame_set
from evaluation_cli_support import git_state, release_detector_runtime


VISOR_CONFIG = ROOT / "configs" / "evaluation" / "visor-screen-v1.toml"
MODEL_CONFIG = ROOT / "configs" / "perception" / "torchvision-coco-baselines-v1.toml"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate fixed torchvision baselines on VISOR sparse frames."
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument(
        "--include-frozen-test",
        action="store_true",
        help="Run the frozen test source once; never use its result to tune.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=(
            "ssdlite320-mobilenet-v3-large-coco-v1",
            "retinanet-resnet50-fpn-v2-coco-v1",
        ),
        default=None,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.include_frozen_test:
        prior_test_receipts = []
        for path in (ROOT / "runs" / "visor-screen-v1").glob("*/receipt.json"):
            try:
                receipt = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if receipt.get("frozen_test_included") is True:
                prior_test_receipts.append(path)
        if prior_test_receipts:
            _parser().error(
                "frozen test already has a completed local receipt; do not rerun or tune on it"
            )
    revision, dirty = git_state(ROOT)
    dataset = load_visor_screen_manifest(VISOR_CONFIG, repository_root=ROOT)
    model_configs = load_torchvision_coco_configs(
        MODEL_CONFIG,
        repository_root=ROOT,
        device=args.device,
    )
    selected_models = set(args.models or [item.model_id for item in model_configs])
    selected_sequences = [
        item
        for item in dataset.sequences
        if item.split != "test" or args.include_frozen_test
    ]
    reports: list[dict[str, object]] = []
    for model_config in model_configs:
        if model_config.model_id not in selected_models:
            continue
        detector = TorchvisionCocoDetector(model_config)
        for sequence_spec in selected_sequences:
            source = load_visor_frame_set(dataset, sequence_spec.sequence_id)
            report = evaluate_frame_set(
                source,
                detector,
                warmup_frames=1,
                repository_root=ROOT,
                code_revision=revision,
                dirty_worktree=dirty,
            )
            reports.append(report.as_dict())
        del detector
        release_detector_runtime()
    created_at = datetime.now(UTC).replace(microsecond=0)
    receipt = {
        "created_at_utc": created_at.isoformat().replace("+00:00", "Z"),
        "dataset_config_hash": dataset.config_hash,
        "frozen_test_included": args.include_frozen_test,
        "operate": "DISABLED",
        "reports": reports,
        "schema_version": 1,
    }
    run_id = created_at.strftime("%Y%m%dT%H%M%SZ") + "-" + revision[:8]
    output_dir = ROOT / "runs" / "visor-screen-v1" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    output_path = output_dir / "receipt.json"
    output_path.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = [
        {
            "ap50": item["quality"]["ap50"],
            "detector_p95_ms": item["cost"]["detector_latency_p95_ms"],
            "map50_95": item["quality"]["map50_95"],
            "model": item["producer_ref"]["component"],
            "recall50": item["quality"]["recall50"],
            "source": item["source_id"],
            "split": item["control"]["evaluation_split"],
            "vram_bytes": item["cost"]["peak_vram_bytes"],
        }
        for item in reports
    ]
    print(
        json.dumps(
            {"output": output_path.as_posix(), "summary": summary},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
