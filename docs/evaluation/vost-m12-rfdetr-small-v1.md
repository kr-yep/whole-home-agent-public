# VOST M12 RF-DETR Small development screen v1

**Status:** `VALID DEVELOPMENT RESULT / CANDIDATE REJECTED`\
**Runtime:** `OPERATE DISABLED`\
**Reserved validation source:** image and mask bytes not read; no validation run

## Bounded conclusion

On the frozen 51-frame VOST `3518_unscrew_bottle` development sequence, the complete
RF-DETR Small 1.9.4 adapter path matched 25 target boxes at IoU at least `0.50`. This
was 15 more matches than the frozen RetinaNet full-frame comparator on the same
frames, but `25/51 = 0.4902` did not meet the predeclared `0.60` development gate.
The candidate is therefore stopped without a second attempt or reserved validation.

The measured detector p95 was `49.7820 ms` and peak allocated VRAM was `149,987,840`
bytes, both inside their strict bounds. These are one-run observations on the declared
RTX 4070 Laptop environment, not stable latency, sustained throughput, 24/7, or
production evidence.

## Why this candidate was screened

M11 found two detector symptoms: 30 confidence-filtered frames and 11 localization
misses. Official published COCO tables gave RF-DETR Small at 512-pixel input a stronger
small-object and AP75 rationale than RF-DETR Nano and the incumbent RetinaNet. Those
cross-publication results were candidate-selection evidence only, not a paired VOST
comparison. RF100-VL results were excluded from the decision because they follow
target-dataset training rather than off-the-shelf inference.

The candidate used the official Apache-2.0 RF-DETR 1.9.4 implementation at source
commit `9b009fa928d6218320439803d1da01869a85c072`. The exact Small checkpoint generation
was bound to upstream MD5, local SHA-256, and byte size before inference. See the
[official RF-DETR paper](https://arxiv.org/abs/2511.09554),
[official benchmark methodology](https://github.com/roboflow/rf-detr#benchmarks), and
[1.9.4 weight registry](https://github.com/roboflow/rf-detr/blob/1.9.4/src/rfdetr/assets/model_weights.py).

## Frozen contract and integrity

- Candidate: exactly one `RFDETRSmall`, package `rfdetr==1.9.4`.
- Checkpoint: GCS generation `1753220474114031`, `386,045,550` bytes, MD5
  `fb37061c1af7bace359c91b723a8d5c1`, SHA-256
  `d81979a9213a2109345158ce9232668df4c1ae52e9b8db3f2ec0a8cbad959b33`.
- Model profile: 512-pixel model input, CUDA device 0, FP16, non-compiled, in-place
  inference, batch 1, and `include_source_image=false`.
- Output contract: the full official sparse COCO ID map, including `44 -> bottle`,
  cross-checked against the SDK class-name output; the same seven scored labels as M10;
  canonical confidence `>= 0.25` and IoU `>= 0.50`.
- Source: `3518_unscrew_bottle`, development only, 51 visible target frames.
- Gates: recall@0.5 `>= 0.60`, detector p95 `< 100 ms`, and peak VRAM `< 1 GiB`.
- Attempt policy: one clean attempt; failure, invalidity, network attempt, missing metric,
  or incomplete coverage cannot be retried in M12.
- Execution boundary: a run-scoped Python socket guard covered model construction,
  warm-up, and inference; zero connection attempts were recorded.
- Clean implementation revision: `4aa0a2ad87dd100be5b38f0db5a01082ab023eb9`.
- Frozen config SHA-256:
  `804bf7fa19b0c08de221202abb5f8220811170f1efd5d641fb66b7d2dad0ba4f`.
- Ignored local receipt SHA-256:
  `7189a177950d2b26031332341d51da0654e7dfb27224bc58bb6d758c731856ae`.

One excluded warm-up call repeated the first frame, followed by 51 measured calls. The
receipt records 52 total adapter calls, complete measured coverage, no tracker, no
training, no test source, no validation, no movement candidate, no claim commit, and
`OPERATE: DISABLED`.

The actual GPU environment used torch `2.11.0+cu128`, torchvision `0.26.0+cu128`,
CUDA `12.8`, cuDNN `91900`, driver `610.74`, and an NVIDIA GeForce RTX 4070 Laptop GPU.
The repository `uv.lock` currently resolves a different PyTorch stack and is explicitly
recorded as not reproducing this GPU environment.

## Results

| Metric | M10 RetinaNet full-frame | M12 RF-DETR Small | M12 gate | Result |
|---|---:|---:|---:|---|
| Matched frames | 10/51 | 25/51 | at least 31/51 | Fail |
| Recall@0.5 | 0.1961 | 0.4902 | >= 0.60 | Fail |
| AP50 | 0.1436 | 0.2762 | descriptive only | Not a gate |
| mAP50:95 | 0.0808 | 0.1792 | descriptive only | Not a gate |
| False positives@0.5 | 130 | 228 | descriptive only | Not a gate |
| Detector p50 | 70.7523 ms | 37.9323 ms | — | Descriptive |
| Detector p95 | 75.7594 ms | 49.7820 ms | < 100 ms | Pass |
| Peak allocated VRAM | 412,383,744 B | 149,987,840 B | < 1,073,741,824 B | Pass |

The AP and false-positive values use the same finite frame set, evaluator, confidence
threshold, IoU rules, and seven-label allowlist. They were not predeclared decision
gates and cannot override the recall failure.

### Target size

| Mask-box area relative to frame | M10 matched / total | M12 matched / total |
|---|---:|---:|
| `<0.1%` | 0/1 | 0/1 |
| `0.1–1%` | 1/22 | 13/22 |
| `>=1%` | 9/28 | 12/28 |

This exact sequence shows more matches in the `0.1–1%` bucket. It does not establish a
general small-object improvement or indoor transfer.

### Paired against the M11 frame classes

| Prior M11 class | Frames | Matched by M12 |
|---|---:|---:|
| Confidence-filtered | 30 | 16 |
| Localization miss | 11 | 0 |
| Previously matched | 10 | 9 |

These categories are descriptive pairings, not causal labels. In particular, zero
recovery among the 11 prior localization-miss frames supports seeking a candidate with
a different localization design rationale; it does not prove RF-DETR generally cannot
localize bottles.

## Claim ledger

| Claim ID | Class | Exact evidence | Permissible wording | Forbidden inference |
|---|---|---|---|---|
| M12-C1 | Integrity / executable | Config, artifact hashes, clean revision, attempt and receipt | One immutable candidate completed one frozen development screen with zero recorded socket attempts | Every network route was OS-isolated or the run is reproducible from the current lock |
| M12-C2 | Behavioral / finite development | 25/51 matches and three predeclared checks | The complete adapter path missed the recall gate while passing the two cost gates on these frames | RF-DETR architecture caused the result or all RF-DETR variants fail |
| M12-C3 | Paired / descriptive | Same-frame M10 comparator and M11 group indexes | This path matched 15 more frames and 16 prior low-score frames | A general small-object capability gain or causal recovery mechanism |
| M12-C4 | Recorded | Attempt flags and exact loader path | Reserved image/mask bytes were not read and validation was not run | Reserved performance is zero or known |
| M12-C5 | Recorded / descriptive | AP, mAP, false-positive and size tables | These additional metrics describe the one valid run | They can replace the predeclared recall verdict |

No bootstrap interval is used for the exact finite-sequence counts. Run-to-run timing
variation, source sampling uncertainty, fixed-camera transfer, household object
coverage, tracker adequacy, and external validity remain unmeasured.

## Decision

Apply `STOP_RFDETR_SMALL_CANDIDATE`. Do not rerun M12, change its threshold or profile,
or open `3510_unscrew_bottle`. The next bounded experiment should establish an
immutable, safely loadable D-FINE Small artifact and adapter contract on synthetic data
only. Its fine-grained distribution refinement and 640-pixel input are a falsifiable
localization-oriented rationale, not an assumed improvement. Only a later clean Goal
may decide whether that candidate earns one development screen.
