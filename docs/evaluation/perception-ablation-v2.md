# Perception ablation v2 results — 2026-09-05

Completed the [frozen plan](perception-ablation-v2-plan.md): 24 generated clips,
60 development runs, 180 evaluation runs (5 arms x 12 clips x 3 repeats), and
5 separate allocation-instrumented development-clip runs excluded from timing.
No parameter tuning or experiment restart. No production-default changes,
training, camera/API/device calls, commit or push.

Counts below are for one pass of 12 evaluation clips: 12 labelled events and
120 checkpoint questions. Event predictions, lags and answers repeated identically.

| Arm | Matched / false / missed events | Correct questions | Detector calls | Paired time saving |
| --- | --- | --- | --- | --- |
| A full + confirmation | 12 / 0 / 0 | 120 / 120 | 960 | reference |
| B full + single confirmation | 12 / 4 / 0 | 120 / 120 | 960 | -0.1% |
| C burst + confirmation | 12 / 0 / 0 | 120 / 120 | 696 | 25.0% |
| D burst + single confirmation | 12 / 4 / 0 | 120 / 120 | 696 | 24.0% |
| E old scheduler + confirmation | 0 / 0 / 12 | 102 / 120 | 96 | 77.1% |

C passes the synthetic-suite threshold: no per-clip quality loss, 27.5% fewer
detector calls and 25.0% paired median time reduction. Median replay times were
A 1056 ms, B 1056 ms, C 801 ms, D 807 ms, E 243 ms. Paired reductions use matched
clip/repeat ratios, not ratios of those aggregate medians.

B/D falsely inferred containment during brief occlusion and retracted it upon
reappearance: two false events per occlusion clip. Zone queries remained correct
because the bag was outside the sofa. Event scoring exposes this defect that
zone-answer accuracy alone misses. Keep temporal confirmation.

The new scheduler retains a two-frame idle anchor and ten-frame dense hold after
pixel/bbox/label changes. It reads only frames/detections, not annotations, and
preserves observation-gap validation. This heuristic does not prove completion
of every pending relation event.

Separate tracemalloc peaks on contain development variant 0: A 9,642,023 bytes;
C 9,800,077 bytes. Sampling slightly increased Python allocations. This is not
total RAM, GPU VRAM, power measurement or evidence of memory savings.

## Evidence and scope

- [Development receipt](perception-ablation-v2-development.json)
- [Evaluation receipt](perception-ablation-v2-results.json)
- [Dataset index](../../examples/media/generated/ablation_v2.suite.json)

Receipts pin source/configuration hashes, Python version, split, per-run events,
checkpoint answers, detector p50/p95 and abstentions. Evaluation verified unchanged
code/data since development. V1 evidence was not overwritten.

These are correlated procedural variants of colored shapes, one instance per
class, not independent households. No bootstrap/significance/generalization claim.
Same-class identity, lighting, camera motion, prolonged occlusion, real detector
accuracy and long-duration operation remain unverified.

Next bounded step: integrate the candidate behind an explicit replay option while
retaining full sampling as default, then evaluate separately labelled indoor data.

## Verification

570 Python tests passed, no skips/errors/failures (27.839 s); Node character switch
checks passed. Four added tests cover scorer failures, empty-negative F1, scene
expectations and scheduler behavior. A regression-launch permission-review timeout
was retried successfully. Report saving also encountered a review timeout and a
patch-context mismatch before successful saving. Experiment runs were unaffected.
