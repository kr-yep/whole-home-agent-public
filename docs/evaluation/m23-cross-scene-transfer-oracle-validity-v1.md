# M23 cross-scene transfer-oracle validity gate

## Verdict

`SELECT_CROSS_SCENE_TEST_ONLY_ORACLE_CONTRACT`.

All five frozen AND gates pass. A minimal M16 detector oracle may use a small positive
and a complete class-absent negative for the same modeled YCB-V class from different
scenes, provided every frame stays in the same test-only project split and retains its
source scene/image identity. This authorizes only a proposal for at most 18 D1 frames.
It is not data materialization, model evaluation, training authority, or transfer gain.

## Why cross-scene aggregation is valid here

The current [BOP challenge page](https://bop.felk.cvut.cz/challenges/) identifies its
COCO path for 2D detection. The official
[`eval_bop22_coco.py`](https://github.com/thodan/bop_toolkit/blob/master/scripts/eval_bop22_coco.py)
filters target images within each scene, merges annotations and results from all target
scenes with collision-safe image-ID offsets, and then runs one `COCOeval` over every
merged image ID. The official
[`cocoeval.py`](https://github.com/cocodataset/cocoapi/blob/master/PythonAPI/pycocotools/cocoeval.py)
first evaluates image/category pairs and then concatenates detections, matches, and
ignore flags across the selected images before cumulative TP/FP and precision/recall.

Inference: because the authoritative BOP detection evaluator itself aggregates one
category across target images from multiple scenes, requiring a positive and negative
to share a scene is not necessary for a bounded detection metric. This says nothing
about scene invariance, synthetic-to-real gain, physical movement, relations, or a
home deployment.

## Frozen gate matrix

| Gate | Result | Evidence | Hard limit |
|---|---|---|---|
| G1 cross-image class aggregation | Pass | BOP merges target scenes before one COCO evaluation; COCO accumulates category matches across image IDs | Detection aggregation only |
| G2 negative denominator | Pass | COCO unmatched non-ignored detections contribute FP evidence; M16 counts every scored frame and rejects predictions on unknown frames | Only complete modeled-class absence is negative |
| G3 protected-group/no leakage | Pass | M16 preserves source-sequence identity and rejects any protected value assigned across splits | Every selected YCB-V frame remains test-only; no random adjacent-frame split |
| G4 paired comparability | Pass | The frozen M23 contract requires identical frames; the executable local evaluator records warm-up, measurement method, frame counts, revision, dirty flag, and environment | A later comparison is invalid if any candidate sees different frames or protocol |
| G5 small-slice uncertainty | Pass | Exact class/frame counts, an 18-frame cap, and explicit non-generalization wording are mandatory | Diagnostic sentinel only; no prevalence or broad transfer estimate |

The [BOP dataset-format specification](https://github.com/thodan/bop_toolkit/blob/master/docs/bop_datasets_format.md)
defines scene/image organization, COCO ground truth, bounding boxes, pixel counts, and
visibility fields. It supports provenance and reference-label translation, not capture
authenticity or physical truth. Sources were accessed 2026-09-01.

## Project metric remains M16

BOP/COCO is evidence for the evaluation topology, not a silent metric replacement. The
project's exact oracle remains [`target_oracle.py`](../../src/whole_home_agent/target_oracle.py):

- all and only `SCORED` frames form the denominator;
- a scored frame with no scorable target is a negative;
- `UNKNOWN`, unmodeled, absent-without-complete-labeling, and prohibited visibility
  states cannot be invented as negatives;
- predictions on unknown frames are rejected;
- frame identity includes source sequence and frame index;
- protected participant, house, session, sequence, camera-time, and synchronized-view
  values cannot cross project splits.

The existing finite-source evaluator records environment and measurement semantics,
but a future result must additionally prove that every candidate used the exact same
manifest, labels, hardware, warm-up, and measurement method.

## Hostile review

- **Scene shortcut:** real risk, not dismissed. Preserve scene IDs and report outcomes
  by scene; do not claim causal or scene-invariant behavior.
- **At most 18 frames:** too small for generalization. Use it only to falsify obvious
  synthetic-to-real failure and report exact counts. A later independent gate is needed
  for confidence intervals or general claims.
- **BOP pose task differs from M16:** accepted. BOP/COCO supports the cross-image
  aggregation premise only; M16 defines the binary project metrics.
- **Test-only reuse:** accepted as a prohibition. No training, threshold selection,
  candidate selection after results, adaptive retry, or test tuning is allowed.
- **Annotations are not truth:** accepted. They remain source reference labels and
  cannot become observations, movement events, or household claims.

No material objection remains unresolved inside this narrow oracle. All remain active
limits on what a later result may say.

## Evidence and boundaries

The no-data/no-model contract was committed at
`3205d2c1e9660b1d4308a8574212f9c0717f3708` before the web research. M23 read only
official public specifications/implementations and existing repository contracts. It
did not reread source archives or media, download data or models, materialize D1, run a
prediction, train, tune, emit a movement candidate/claim/relation, connect a camera,
cloud, account, or device, or enable `OPERATE`.

On clean result revision `799af167c9568d1293e149368f7831a745ad947a`, Python
3.12.13 passed all `228/228` tests. The M23 module contributed eight passing frozen-
contract, AND-gate, hostile-limit, result, boundary, and next-authority tests. The public
release audit scanned 232 tracked files and 464 index/worktree snapshots with zero
violations and `operate_enabled: false`. These checks support only the recorded decision
and mechanical repository boundary.

## Claim ledger

| Claim | Evidence | Permissible wording | Unsupported extension |
|---|---|---|---|
| M23-C1 | Official BOP evaluator | BOP merges target scenes for COCO detection evaluation | BOP proves this custom slice is representative |
| M23-C2 | Official COCO evaluator plus M16 | Complete class-absent scored images can contribute FP evidence | Every image without this class is a safe negative |
| M23-C3 | M16 split validator | Test-only scenes can retain identity without cross-split leakage | Different scenes are statistically independent household samples |
| M23-C4 | Frozen paired protocol and local evaluator | A same-frame, same-protocol comparison is implementable | A future run is comparable without checking its receipt |
| M23-C5 | Explicit cap and language boundary | An at-most-18-frame diagnostic oracle is allowed | The slice estimates home transfer or natural prevalence |

## Next gate

M24 may freeze and then materialize only the smallest source-ordered, one-class,
cross-scene test pair (one frozen-bucket positive plus one complete class-absent
negative is preferred) with full provenance. It must keep third-party bytes ignored,
perform no prediction or training, and fail closed if source completeness, image
identity, label translation, or deterministic output differs from the frozen contract.
