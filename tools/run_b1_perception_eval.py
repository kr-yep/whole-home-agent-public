"""Run the fixed synthetic B1 detector/tracker benchmark and emit JSON."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from whole_home_agent.adapters.annotation_oracle import AnnotationOracleDetector
from whole_home_agent.adapters.motion import MotionPeriodicScheduler, MotionScheduleConfig
from whole_home_agent.adapters.synthetic_color import (
    SyntheticColorDetector,
    load_synthetic_color_config,
)
from whole_home_agent.adapters.tracking import IoUTracker
from whole_home_agent.evaluation import evaluate_perception
from whole_home_agent.video_manifest import load_video_manifest


DEFAULT_MANIFEST = (
    ROOT / "examples" / "media" / "generated" / "key_bag_sofa_v1.manifest.json"
)
DEFAULT_COLOR_CONFIG = ROOT / "configs" / "perception" / "synthetic-color-v1.toml"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate one allowlisted prerecorded D0 perception adapter."
    )
    parser.add_argument(
        "--detector", choices=("synthetic-color", "annotation-oracle"), default="synthetic-color"
    )
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument(
        "--test-only-oracle",
        action="store_true",
        help="Required acknowledgement when selecting the annotation oracle.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
    manifest = load_video_manifest(DEFAULT_MANIFEST, repository_root=ROOT)
    if args.detector == "annotation-oracle":
        if not args.test_only_oracle:
            _parser().error("annotation-oracle requires --test-only-oracle")
        detector = AnnotationOracleDetector(manifest, test_only=True)
    else:
        width, height, targets = load_synthetic_color_config(
            DEFAULT_COLOR_CONFIG, repository_root=ROOT
        )
        detector = SyntheticColorDetector(width=width, height=height, targets=targets)
    scheduler = (
        MotionPeriodicScheduler(
            MotionScheduleConfig(
                motion_threshold=0.005,
                min_gap_frames=2,
                anchor_interval_frames=10,
                sample_stride=8,
            )
        )
        if args.scheduled
        else None
    )
    report = evaluate_perception(
        manifest,
        detector,
        tracker=IoUTracker(),
        scheduler=scheduler,
        repository_root=ROOT,
        code_revision=revision,
        dirty_worktree=dirty,
    )
    print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
