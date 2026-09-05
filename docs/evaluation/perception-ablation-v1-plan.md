# Perception ablation v1 — frozen before execution

Scope: four one-factor comparisons against the existing B1 synthetic pipeline.
No production defaults are changed. No camera, cloud API, physical action,
training, Kaggle submission, commit or push is part of this experiment.

## Fixed experiment

Use `examples/media/generated/key_bag_sofa_v2.manifest.json` and its verified
video/annotations. Keep the synthetic color detector, event matching tolerance,
entity binding and all unspecified settings fixed. Record resolved settings,
source hash and experiment code hash in the machine-readable output.

| Arm | Only change from baseline | Question |
| --- | --- | --- |
| baseline | None: every frame, IoU tracking, existing temporal rules, chain query | Reference |
| motion_periodic | Existing scheduler defaults: threshold .03, gap 2, anchor 10, stride 8 | Can scheduling save work without losing events? |
| no_tracking | New independent track IDs each frame, no cross-frame association | Does this bounded pipeline use tracking information? |
| single_confirmation | Five observation/confirmation counts reduced to 1; geometry and lookback unchanged | What changes without repeated confirmation? |
| direct_only | Query only active direct at_zone relations, no containment traversal | Does chaining enable the final key-location answer? |

Direct-only is **not** a complete alternative last-seen bounding-box database.
It preserves retractions through the same active projection and reports UNKNOWN
when only containment is known. It must not invent a previous visible zone.
Single-confirmation still uses historical disappearance logic; it is not a
single-image VLM or complete removal of all temporal state.

## Measurements and decisions

Run three repeats per arm, rotating arm order each repeat, with fresh state.
Measure complete replay wall time (including decode, excluding setup/evaluation),
detector calls and per-call p50/p95, decoded/selected frames, matched/false/missed
events, event precision/recall/F1, confirmation lag, and final answer correctness.
Record full individual runs; repeat disagreement is a defect, not an average gain.

An efficiency candidate qualifies for further validation only if every repeat
preserves baseline event counts and final-answer correctness, detector calls
decrease at least 20%, and median replay time decreases at least 10%.
Equal accuracy without that saving is inconclusive, not a reason to remove code.
Lower confirmation lag alone does not justify disabling confirmation without
negative/occlusion cases. Direct-only failure supports retaining chain queries.

One video is one independent sample: no bootstrap confidence interval or
statistical significance claim from repeated executions. CPU synthetic detector
means no meaningful YOLO VRAM/household-power claim. No trained weights change.

## Boundaries and next evidence

Stop after 15 completed runs and regression tests. On an implementation error,
fix the harness and rerun the same frozen settings; log that restart. Do not
tune scheduler or thresholds using these results. No indefinite training.

Before household defaults can change, a separate versioned evaluation needs
independently labelled indoor clips: stationary objects, true moves, transient
occlusion, put-in/take-out, same-class objects/crossings, lighting/camera motion,
and disappearance without containment. Labels must identify events, identities,
times, zones and expected answers (including UNKNOWN/CONFLICT), and dataset
licensing must permit the use. Split development and held-out clips before
tuning. Missing real labels are an evidence limitation, not synthetic success.

The present manifest has one instance per label; the binder uses labels and the
relation engine does not consume track IDs. Thus no-tracking equality can expose
an unused connection here but cannot establish multi-object tracking redundancy.

## Run

From a checkout with the demo dependencies installed:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
uv run --frozen --extra demo python tools/benchmark_perception_ablation.py --output-json docs/evaluation/perception-ablation-v1-results.json
```

The experiment makes no network requests and never modifies the source clip.
