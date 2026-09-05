"""Development-only necessary-condition screen; never an end-to-end pass."""
import json
from pathlib import Path
import time

from benchmark_perception_v2 import BurstScheduler, CONFIG
from generate_ablation_v2 import digest, write_json
from whole_home_agent.adapters.vost import load_vost_motion_screen_manifest, load_vost_motion_sequence

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/evaluation/real-burst-feasibility-v1.json"


def main():
    if OUTPUT.exists():
        raise FileExistsError("do not overwrite measured evidence")
    config = ROOT / "configs/evaluation/vost-motion-screen-v1.toml"
    manifest = load_vost_motion_screen_manifest(config, repository_root=ROOT)
    spec = next(s for s in manifest.sequences if s.split == "development")
    source = load_vost_motion_sequence(manifest, spec.sequence_id)
    rows = []
    for repeat in range(3):
        scheduler = BurstScheduler()
        selected = []
        start = time.perf_counter()
        for frame in source.iter_frames():
            if scheduler.evaluate(frame).selected:
                selected.append(frame.position.frame_index)
        events = source.mask_change_frames
        covered = sum(any(i in selected for i in range(e, min(source.frame_count,e+source.coverage_window_frames+1))) for e in events)
        rows.append(dict(repeat=repeat, frames=source.frame_count, selected=len(selected),
            selected_indexes=selected, maximum_possible_call_reduction=1-len(selected)/source.frame_count,
            mask_change_events=len(events), covered=covered,
            coverage=covered/len(events) if events else None,
            decode_and_scheduler_ms=(time.perf_counter()-start)*1000))
    # Detector feedback can extend a dense window, never remove selected frames.
    # Failure here therefore rejects the savings target even before detector runs.
    cost_impossible = any(r["maximum_possible_call_reduction"] < .20 for r in rows)
    report = dict(source_id=source.descriptor.source_id, split=source.split,
        data_config_sha256=digest(config), scheduler_file_sha256=digest(ROOT/"tools/benchmark_perception_v2.py"),
        source_content_hash=source.descriptor.content_hash, config=CONFIG, rows=rows,
        status="FAIL_EFFICIENCY_NECESSARY_CONDITION" if cost_impossible else "NEEDS_FULL_VALIDATION",
        end_to_end_pass=False, detector_calls_executed=0, push_condition_met=False,
        limitations="Real egocentric development clip, 5fps not fixed-camera 10fps; pixel-only scheduler lower bound. No detector feedback, object-location or containment accuracy measured. No tuning. Validation sequence not evaluated.")
    write_json(OUTPUT,report)
    print(json.dumps(report,indent=2))


if __name__ == "__main__":
    main()
