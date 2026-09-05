# Perception ablation v2 — frozen experiment

User-approved local synthetic evaluation. No production defaults change, no
camera/device/API calls, training, Kaggle access, commit or push.

Six scenarios x four variants: stationary, move, contain-and-move, take-out,
brief occlusion, disappearance without containment. Variants 0/1 are development;
2/3 are held-out evaluation. These are related procedural variants, not independent
households. Each 80-frame RGB video is 640x360 at 10 fps. Scene descriptions,
event labels and time-indexed query targets are generated before inference.
Source, annotation and generator hashes are frozen in individual manifests.
Old v1 artifacts are never overwritten.

Arms: A full sampling + existing confirmation; B full + five confirmation counts
set to one; C burst sampling + existing confirmation; D burst + single confirmation;
E existing motion-periodic defaults + existing confirmation (negative control).
All other detection/tracker/rule settings are identical to v1.

Initial burst candidate is fixed before development results: idle anchor 2 frames,
RGB subsample stride 4, maximum-channel change >= 0.12 starts a 10-frame dense
window. Every selected detection also extends that window when labels change or
any bbox coordinate changes by > 1 pixel. This holds sampling during candidate
changes without reading annotations or private temporal-engine state. It is an
approximation to pending-event coverage, not proof of event completion. Maximum
observation-gap validation remains unchanged. No parameter search in this version.

Development: 12 clips x 5 arms once (60 runs), diagnostic only. Then freeze code
and configuration hashes in a development receipt. Evaluation requires that
receipt and identical code/data hashes: 12 clips x 5 arms x 3 rotated repeats
(180 runs). No tuning after evaluation. Fix infrastructure/harness defects only
with an explicit restart note; do not silently replace measured runs.

Events match one-to-one by operation/subject/predicate/object, with lag 0..8
frames. Early/unmatched events are false positives. Empty-event negative clips
are scored using false-event counts; do not award artificial F1=1 for no events.
Query checks use the original source timeline at predetermined checkpoints;
grading happens after the complete replay, outside pipeline timing. Include
before/after/occluded/removed states and both key and bag queries.

Measure matched/false/missed events, precision/recall/F1, checkpoint query accuracy,
confirmation lag, detector calls, replay wall time and detector p50/p95. An
additional untimed baseline replay per arm measures Python allocation peak with
tracemalloc; this is NOT total process RAM or GPU VRAM, which remain unmeasured.
Do not mix allocation-instrumented timings into speed comparisons.

Efficiency eligibility: baseline answers must be correct and baseline have zero
false/missed events; candidate must not regress any clip's false/missed counts or
checkpoint correctness across repeats. At least 20% aggregate detector-call
reduction and 10% paired median replay-time reduction are required. Every arm
still reports failures even if baseline is wrong. No bootstrap/significance claim
for correlated procedural variants; repeated timing is not extra sample size.

Stop after bounded runs, targeted tests, full regression and report, even if all
candidates fail. No indefinite training. Same-class tracking, light/camera changes,
real detector resource profiling and real indoor accuracy need separate suites.
