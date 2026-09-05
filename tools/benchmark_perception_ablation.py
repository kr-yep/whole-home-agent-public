"""Frozen, one-factor B1 ablations. Synthetic evidence, not household accuracy."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from whole_home_agent.adapters.motion import MotionPeriodicScheduler, MotionScheduleConfig
from whole_home_agent.adapters.recorded_perception_source import RecordedPerceptionCandidateSource
from whole_home_agent.adapters.synthetic_color import SyntheticColorDetector, load_synthetic_color_config
from whole_home_agent.adapters.tracking import IoUTracker
from whole_home_agent.model import Predicate, QueryRequest, RunStatus
from whole_home_agent.orchestrator import run_source
from whole_home_agent.perception import TrackObservation
from whole_home_agent.public_demo import (
    REPOSITORY_ROOT as ROOT, PUBLIC_MANIFEST, COLOR_CONFIG, RELATION_CONFIG, RELATION_EVAL_CONFIG,
)
from whole_home_agent.relation_evaluation import evaluate_relations, load_relation_evaluation_config
from whole_home_agent.relation_inference import load_relation_rule_config
from whole_home_agent.video_manifest import load_video_manifest

ARMS = ("baseline", "motion_periodic", "no_tracking", "single_confirmation", "direct_only")
CONFIRMATION_FIELDS = (
    "contained_observations_required", "disappearance_confirmation_frames",
    "take_out_confirmation_frames", "zone_stable_confirmation_frames", "zone_exit_confirmation_frames",
)


class FrameLocalTracker:
    """No temporal association; IDs deliberately cannot persist across frames."""
    def reset(self):
        pass

    def resolved_config(self):
        return {"tracker": "frame-local-no-association/1"}

    def update(self, position, detections):
        if any(item.position != position for item in detections):
            raise ValueError("detections must belong to this frame")
        return tuple(TrackObservation(
            track_id=f"frame-{position.frame_index}-detection-{index}",
            detection=item, track_age=1,
        ) for index, item in enumerate(detections))


class TimedDetector:
    def __init__(self, delegate):
        self.delegate = delegate
        self.latencies_ms = []

    @property
    def producer_ref(self):
        return self.delegate.producer_ref

    def detect(self, frame):
        started = time.perf_counter()
        result = self.delegate.detect(frame)
        self.latencies_ms.append((time.perf_counter() - started) * 1000)
        return result


def percentile(values, fraction):
    """Nearest-rank percentile; no empty sample represented as zero latency."""
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def direct_location(session, subject_id):
    targets = sorted({r.object_id for r in session.projection.active_relations
                      if r.subject_id == subject_id and r.predicate is Predicate.AT_ZONE})
    if len(targets) == 1:
        return "FOUND", targets[0]
    return ("CONFLICT" if targets else "UNKNOWN"), None


def summarize(rows):
    summaries = {}
    for name in ARMS:
        runs = [r for r in rows if r["arm"] == name]
        signatures = {json.dumps(r["quality"], sort_keys=True) for r in runs}
        summaries[name] = {
            "repeat_count": len(runs), "quality_repeatable": len(signatures) == 1,
            "quality": runs[0]["quality"],
            "median_replay_ms": statistics.median(r["replay_ms"] for r in runs),
            "median_detector_calls": statistics.median(r["detector_calls"] for r in runs),
        }
    base = summaries["baseline"]
    for name, arm in summaries.items():
        arm["detector_call_reduction"] = 1 - arm["median_detector_calls"] / base["median_detector_calls"]
        arm["replay_time_reduction"] = 1 - arm["median_replay_ms"] / base["median_replay_ms"]
        fields = ("matched_events", "false_events", "missed_events", "answer_correct")
        preserved = all(all(r["quality"][k] == base["quality"][k] for k in fields)
                        for r in rows if r["arm"] == name)
        arm["quality_preserved"] = preserved
        arm["efficiency_candidate"] = (
            name != "baseline" and base["quality_repeatable"] and base["quality"]["answer_correct"]
            and arm["quality_repeatable"] and preserved
            and arm["detector_call_reduction"] >= .20 and arm["replay_time_reduction"] >= .10
        )
    return summaries


def run_benchmark():
    manifest = load_video_manifest(PUBLIC_MANIFEST, repository_root=ROOT)
    width, height, targets = load_synthetic_color_config(COLOR_CONFIG, repository_root=ROOT)
    rules = load_relation_rule_config(RELATION_CONFIG, repository_root=ROOT)
    evaluator = load_relation_evaluation_config(RELATION_EVAL_CONFIG, repository_root=ROOT)
    rows = []
    for repeat in range(3):
        order = ARMS[repeat:] + ARMS[:repeat]
        for name in order:
            detector = TimedDetector(SyntheticColorDetector(width=width, height=height, targets=targets))
            tracker = FrameLocalTracker() if name == "no_tracking" else IoUTracker()
            config = replace(rules, **{field: 1 for field in CONFIRMATION_FIELDS}) if name == "single_confirmation" else rules
            scheduler = MotionPeriodicScheduler(MotionScheduleConfig()) if name == "motion_periodic" else None
            source = RecordedPerceptionCandidateSource(manifest, detector, tracker, config, scheduler=scheduler)
            started = time.perf_counter()
            result = run_source(source, replay_run_id=f"ablation-{name}-{repeat}")
            elapsed = (time.perf_counter() - started) * 1000
            if result.status is not RunStatus.COMPLETE or result.session is None:
                raise RuntimeError(f"{name} repeat {repeat}: incomplete replay {result.status}")
            diag = source.diagnostics
            quality = evaluate_relations(manifest, result, diag.abstentions, diag.completed, evaluator).quality.as_dict()
            answer = result.session.locate(QueryRequest(
                subject_id=evaluator.query_subject_id, world_scope=result.session.world_scope,
                replay_run_id=result.session.replay_run_id,
                as_of_source_sequence=result.session.projection_frontier,
            ))
            status, location = ((answer.status.value, answer.location_id) if name != "direct_only"
                                else direct_location(result.session, evaluator.query_subject_id))
            quality.update(answer_status=status, answer_location_id=location,
                           answer_correct=status == "FOUND" and location == evaluator.expected_location_id,
                           false_events=quality["predicted_events"] - quality["matched_events"],
                           missed_events=quality["expected_events"] - quality["matched_events"])
            rows.append({
                "arm": name, "repeat": repeat, "replay_ms": elapsed,
                "detector_calls": len(detector.latencies_ms),
                "detector_p50_ms": percentile(detector.latencies_ms, .5),
                "detector_p95_ms": percentile(detector.latencies_ms, .95),
                "decoded_frames": diag.decoded_frames, "selected_frames": diag.selected_frames,
                "quality": quality, "rules": asdict(config), "tracker": tracker.resolved_config(),
                "scheduler": scheduler.resolved_config() if scheduler else None,
                "claims": [{"subject": c.subject_id, "predicate": c.predicate.value,
                            "object": c.object_id, "operation": c.operation.value,
                            "frame": c.source_position.frame_index} for c in result.session.accepted_claims],
            })
    files = [Path(__file__), ROOT / "docs/evaluation/perception-ablation-v1-plan.md",
             COLOR_CONFIG, RELATION_CONFIG, RELATION_EVAL_CONFIG]
    files += sorted((ROOT / "src/whole_home_agent").rglob("*.py"))
    return {
        "schema_version": 1, "scope": "one synthetic clip; no real-home claim",
        "source_hash": manifest.descriptor.content_hash,
        "file_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        "bootstrap_ci": None, "bootstrap_reason": "one independent clip; repeats measure runtime variation only",
        "gpu_vram": None, "gpu_reason": "CPU synthetic color detector; not a YOLO measurement",
        "rows": rows, "summary": summarize(rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    report = run_benchmark()
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output_json:
        args.output_json.write_text(payload, encoding="utf-8")
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    else:
        print(payload)


if __name__ == "__main__":
    main()
