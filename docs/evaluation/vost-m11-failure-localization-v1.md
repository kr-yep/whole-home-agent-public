# VOST M11 failure localization v1

**Status:** `VALID DEVELOPMENT-ONLY DIAGNOSTIC`\
**Runtime:** `OPERATE DISABLED`\
**Reserved validation source:** not loaded or run

## Bounded conclusion

On the hash-pinned VOST `3518_unscrew_bottle` development sequence, every visible
target frame had at least one RetinaNet `bottle` proposal at or above the model's
frozen `0.05` post-process floor. The M10 failure was therefore not dominated by a
complete absence of class proposals: 30/51 frames had proposals only below the frozen
`0.25` product threshold, 11/51 had a product-threshold proposal but no IoU@0.5 match,
and 10/51 matched.

This supports replacing or adapting the detector path before semantic movement work.
It does not establish why the network assigned each score, that lowering the threshold
is safe, or that VOST behavior transfers to a fixed home camera.

## Frozen diagnostic contract

- Source: official-train development sequence `3518_unscrew_bottle`, 51 frames.
- Reserved source: `3510_unscrew_bottle`; `reserved_split_allowed = false` and it was
  not loaded.
- Model and product output: the M10 RetinaNet ResNet50 FPN v2 artifact and unchanged
  `0.25` confidence threshold.
- Diagnostic view: post-processed `bottle` proposals from `0.05` upward. These have a
  separate adapter type and never become canonical `Detection` below `0.25`.
- Match: IoU at least `0.50` with the mask-derived target box.
- Oracle association: the existing label-aware greedy IoU tracker receives exactly one
  confidence-1.0 mask-derived box on every visible frame, with its unchanged IoU `0.25`
  and two-missed-update settings.
- Clean implementation revision: `eb5d28a3bbd3bf552fb3e8d0bb00e8bc44c19e81`.
- Receipt: local ignored run `20260901T084359Z-eb5d28a3`; no images, weights, or source
  bytes are committed.

The one model pass made 51 inference calls, reproduced M10's 10 matched frames, and
recorded `validation_run: false`, `reserved_sequence_loaded: false`, and
`operate: DISABLED`.

## Result

| Mutually exclusive frame class | Count | Fraction of 51 |
|---|---:|---:|
| Target absent or void | 0 | 0.0000 |
| No `bottle` proposal at score >= 0.05 | 0 | 0.0000 |
| Proposal exists only from 0.05 to below 0.25 | 30 | 0.5882 |
| Score >= 0.25 but best IoU is below 0.50 | 11 | 0.2157 |
| Score >= 0.25 and IoU >= 0.50 | 10 | 0.1961 |

The confidence-filtered class accounts for 30/41 misses (`0.7317`), so the frozen
decision rule identifies it as the dominant detector symptom. Size stratification was:

| Target area | Confidence-filtered | Localization miss | Matched | Total |
|---|---:|---:|---:|---:|
| `<0.1%` | 1 | 0 | 0 | 1 |
| `0.1–1%` | 21 | 0 | 1 | 22 |
| `>=1%` | 8 | 11 | 9 | 28 |

Sixteen of the 30 confidence-filtered frames had a proposal with IoU at least `0.50`.
Therefore a threshold-only change bounded at the model's existing `0.05` floor can
match at most `(10 + 16) / 51 = 0.5098` frames in these retained outputs. That remains
below M10's unchanged `0.60` gate, before considering additional false positives or
tracking effects. The predeclared router points to threshold calibration, but this
deterministic sufficiency bound rejects threshold-only calibration as the next standalone
experiment without another inference run.

The mask-box oracle tracker matched the target for evaluation on all 51 frames, yet
produced 16 ID switches and zero fragmentations. It fails the unchanged maximum of one
ID switch. This is direct evidence that the current greedy IoU association is also a
separate bottleneck under large mask-box changes; it is not evidence about trackers in
general or about persistent household identity.

## Claim ledger

| Claim ID | Evidence class | Exact evidence | Permissible wording | Forbidden inference |
|---|---|---|---|---|
| M11-C1 | Integrity / executable | Frozen config/input hashes, clean revision, one ignored receipt | The pinned development diagnostic ran once and kept the product threshold unchanged | Reserved validation or household media were tested |
| M11-C2 | Behavioral / descriptive | Exhaustive 51-frame classification | Confidence filtering is the largest recorded miss class for this model/source | Score filtering causally explains every failure |
| M11-C3 | Executable upper bound | Retained per-frame proposal IoUs | Threshold-only inclusion down to 0.05 cannot reach the unchanged 0.60 recall gate on these outputs | A lower threshold would improve precision, tracking, or another source |
| M11-C4 | Behavioral / descriptive | Oracle boxes through unchanged `IoUTracker` | The current tracker exceeds its ID-switch gate even on these mask boxes | All association methods fail, or mask IDs are household identities |
| M11-C5 | Recorded | Receipt flags and source-loading path | Validation was not loaded or run | Validation performance is zero |

No bootstrap interval is used: these are exact descriptive counts over one frozen
sequence, not an estimate of a sampled population. External validity remains unknown.

## Decision

Do not create movement candidates and do not spend another run on threshold-only
calibration. The next detector gate should freeze one replacement whose design can
improve both low-score and localization failures, evaluate it on development first,
and require at least `0.60` recall@0.5 within the existing latency/VRAM bounds before
opening reserved validation. Tracker replacement remains a required later co-gate even
if the detector passes.
