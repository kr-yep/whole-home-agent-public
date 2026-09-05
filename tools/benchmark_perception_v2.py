"""Five-arm development/evaluation experiment, never changes production defaults."""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time
import tracemalloc

from generate_ablation_v2 import ROOT, OUT, SUITE, digest, write_json
from benchmark_perception_ablation import CONFIRMATION_FIELDS, percentile
from whole_home_agent.adapters.motion import MotionPeriodicScheduler, MotionScheduleConfig, FrameSelection, SelectionReason
from whole_home_agent.adapters.recorded_perception_source import RecordedPerceptionCandidateSource
from whole_home_agent.adapters.synthetic_color import SyntheticColorDetector, load_synthetic_color_config
from whole_home_agent.adapters.tracking import IoUTracker
from whole_home_agent.model import QueryRequest, RunStatus
from whole_home_agent.orchestrator import run_source
from whole_home_agent.relation_inference import load_relation_rule_config
from whole_home_agent.video_manifest import load_video_manifest

ARMS = ("A_full_confirm", "B_full_single", "C_burst_confirm", "D_burst_single", "E_old_scheduler")
CONFIG = dict(idle_gap=2, burst_frames=10, stride=4, pixel_threshold=.12, bbox_threshold=1)
DEVELOPMENT = ROOT / "docs/evaluation/perception-ablation-v2-development.json"
EVALUATION = ROOT / "docs/evaluation/perception-ablation-v2-results.json"


class BurstScheduler:
    """Dense hold on observed change; no labels/events from the scene generator."""
    def __init__(self):
        self.previous = None
        self.last = None
        self.until = -1
        self.boxes = None

    def evaluate(self, frame):
        import numpy as np
        index = frame.position.frame_index
        sample = np.asarray(frame.rgb)[::CONFIG["stride"], ::CONFIG["stride"]].astype(np.float32) / 255
        score = None if self.previous is None else float(np.abs(sample-self.previous).max())
        if score is not None and score >= CONFIG["pixel_threshold"]:
            self.until = index + CONFIG["burst_frames"]
        first = self.last is None
        dense = index <= self.until
        selected = first or dense or index-self.last >= CONFIG["idle_gap"]
        reason = SelectionReason.FIRST if first else SelectionReason.MOTION if dense else SelectionReason.PERIODIC_ANCHOR if selected else SelectionReason.SKIPPED
        self.previous = sample
        if selected:
            self.last = index
        return FrameSelection(index, frame.position.pts, selected, reason, score)

    def observe(self, frame, detections):
        boxes = {item.label: item.bbox.as_xyxy() for item in detections}
        changed = self.boxes is None or boxes.keys() != self.boxes.keys() or any(
            max(abs(a-b) for a,b in zip(box, self.boxes[label])) > CONFIG["bbox_threshold"]
            for label,box in boxes.items())
        if changed:
            self.until = frame.position.frame_index + CONFIG["burst_frames"]
        self.boxes = boxes


class DetectorProbe:
    def __init__(self, detector, scheduler):
        self.detector, self.scheduler, self.times = detector, scheduler, []

    @property
    def producer_ref(self):
        return self.detector.producer_ref

    def detect(self, frame):
        start = time.perf_counter()
        detections = self.detector.detect(frame)
        self.times.append((time.perf_counter()-start)*1000)
        if isinstance(self.scheduler, BurstScheduler):
            self.scheduler.observe(frame, detections)
        return detections


def score_events(expected, predicted):
    used, lags = set(), []
    fields = ("operation", "subject_id", "predicate", "object_id")
    for event in expected:
        candidates = [(p["frame_index"]-event["frame_index"], i) for i,p in enumerate(predicted)
                      if i not in used and all(p[k] == event[k] for k in fields)
                      and 0 <= p["frame_index"]-event["frame_index"] <= 8]
        if candidates:
            lag, index = min(candidates)
            used.add(index)
            lags.append(lag)
    tp, fp, fn = len(used), len(predicted)-len(used), len(expected)-len(used)
    return dict(tp=tp, fp=fp, fn=fn, lags=lags,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)


def snapshot():
    paths = [Path(__file__), ROOT/"tools/generate_ablation_v2.py", ROOT/"tools/benchmark_perception_ablation.py",
             ROOT/"docs/evaluation/perception-ablation-v2-plan.md", SUITE, ROOT/"uv.lock"]
    paths += sorted((ROOT/"src/whole_home_agent").rglob("*.py"))
    paths += sorted((ROOT/"configs/perception").glob("*.toml"))
    paths += sorted(OUT.glob("ablation_v2_*.manifest.json"))
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}


def run_one(clip, arm, repeat):
    manifest_path = OUT/clip["manifest"]
    if digest(manifest_path) != clip["manifest_hash"]:
        raise ValueError("suite manifest was modified")
    manifest = load_video_manifest(manifest_path, repository_root=ROOT)
    width,height,targets = load_synthetic_color_config(ROOT/"configs/perception/synthetic-color-v1.toml", repository_root=ROOT)
    rules = load_relation_rule_config(ROOT/"configs/perception/relation-rules-v1.toml", repository_root=ROOT)
    if arm in (ARMS[1],ARMS[3]):
        rules = replace(rules, **{k:1 for k in CONFIRMATION_FIELDS})
    scheduler = BurstScheduler() if arm in (ARMS[2],ARMS[3]) else MotionPeriodicScheduler(MotionScheduleConfig()) if arm == ARMS[4] else None
    detector = DetectorProbe(SyntheticColorDetector(width=width,height=height,targets=targets), scheduler)
    source = RecordedPerceptionCandidateSource(manifest, detector, IoUTracker(), rules, scheduler=scheduler)
    start = time.perf_counter()
    result = run_source(source, replay_run_id=f"v2-{clip['name']}-{arm}-{repeat}")
    elapsed = (time.perf_counter()-start)*1000
    if result.status is not RunStatus.COMPLETE or result.session is None:
        raise RuntimeError(f"incomplete replay {clip['name']} {arm}: {result.status}")
    session = result.session
    predicted = [dict(operation=c.operation.value,subject_id=c.subject_id,predicate=c.predicate.value,
                      object_id=c.object_id,frame_index=c.source_position.frame_index) for c in session.accepted_claims]
    queries = []
    for target in clip["queries"]:
        answer = session.locate(QueryRequest(target["subject"], session.world_scope, session.replay_run_id,
                                            min(target["frame"],session.projection_frontier)))
        queries.append(dict(**target, actual_status=answer.status.value, actual_location=answer.location_id,
                            correct=answer.status.value == target["status"] and answer.location_id == target["location"]))
    return dict(clip=clip["name"], scenario=clip["scenario"], arm=arm, repeat=repeat,
                replay_ms=elapsed, detector_calls=len(detector.times), decoded_frames=source.diagnostics.decoded_frames,
                detector_p50_ms=percentile(detector.times,.5),detector_p95_ms=percentile(detector.times,.95),
                events=score_events(manifest.events,predicted),predicted=predicted,queries=queries,
                abstentions=[dict(frame=x.frame_index,reason=x.reason) for x in source.diagnostics.abstentions],
                rules=asdict(rules))


def summarize(rows):
    summary = {}
    for arm in ARMS:
        runs = [r for r in rows if r["arm"]==arm]
        tp,fp,fn = [sum(r["events"][k] for r in runs) for k in ("tp","fp","fn")]
        correct = sum(q["correct"] for r in runs for q in r["queries"])
        count = sum(len(r["queries"]) for r in runs)
        summary[arm] = dict(runs=len(runs),tp=tp,fp=fp,fn=fn,
            event_f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            query_correct=correct,query_count=count,query_accuracy=correct/count,
            detector_calls=sum(r["detector_calls"] for r in runs),median_replay_ms=statistics.median(r["replay_ms"] for r in runs))
    base = summary[ARMS[0]]
    baseline_by_key = {(r["clip"],r["repeat"]):r for r in rows if r["arm"]==ARMS[0]}
    for arm, value in summary.items():
        runs = [r for r in rows if r["arm"]==arm]
        ratios, preserved = [], True
        for r in runs:
            b = baseline_by_key[(r["clip"],r["repeat"])]
            ratios.append(r["replay_ms"]/b["replay_ms"])
            preserved &= r["events"]["fp"] <= b["events"]["fp"] and r["events"]["fn"] <= b["events"]["fn"]
            preserved &= all(not a["correct"] or q["correct"] for a,q in zip(b["queries"],r["queries"]))
        value["paired_time_reduction"] = 1-statistics.median(ratios)
        value["call_reduction"] = 1-value["detector_calls"]/base["detector_calls"]
        value["quality_preserved"] = bool(preserved)
        value["eligible"] = bool(arm != ARMS[0] and preserved and base["fp"]==base["fn"]==0
            and base["query_correct"]==base["query_count"] and value["call_reduction"]>=.2 and value["paired_time_reduction"]>=.1)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("development","evaluation"))
    args = parser.parse_args()
    output = DEVELOPMENT if args.phase=="development" else EVALUATION
    if output.exists():
        raise FileExistsError("result already exists; never silently overwrite evidence")
    identity = snapshot()
    if args.phase=="evaluation":
        prior = json.loads(DEVELOPMENT.read_text(encoding="utf-8"))
        if prior["snapshot"] != identity:
            raise ValueError("code/data changed after development freeze")
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    split = "train" if args.phase=="development" else "test"
    clips = [c for c in suite["clips"] if c["split"]==split]
    repeats = 1 if split=="train" else 3
    rows = []
    for repeat in range(repeats):
        for index,clip in enumerate(clips):
            offset = (repeat+index)%len(ARMS)
            for arm in ARMS[offset:]+ARMS[:offset]:
                rows.append(run_one(clip,arm,repeat))
            print(f"{args.phase}: {len(rows)}/{len(clips)*len(ARMS)*repeats} replays", flush=True)
    peaks = {}
    if split=="test":
        memory_clip = next(c for c in suite["clips"] if c["scenario"]=="contain" and c["variant"]==0)
        for arm in ARMS:
            tracemalloc.start()
            run_one(memory_clip,arm,"memory")
            peaks[arm] = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
    write_json(output,dict(phase=args.phase,snapshot=identity,config=CONFIG,python=platform.python_version(),
        platform=platform.system(),rows=rows,summary=summarize(rows),python_allocation_peak_bytes=peaks,
        limitations="CPU synthetic detector; correlated procedural clips; no total RAM/VRAM or household generalization claim"))
    print(json.dumps(summarize(rows),indent=2))


if __name__ == "__main__":
    main()
