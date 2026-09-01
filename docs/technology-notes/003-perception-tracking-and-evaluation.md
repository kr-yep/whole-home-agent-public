# Perception, tracking, and evaluation baseline

**Status:** implemented and tested for the hash-pinned D0 synthetic replay only
**Operation:** offline prerecorded replay; `OPERATE DISABLED`

## Why these pieces exist

The perception stage reports frame-level estimates. It does not write household state. Every adapter must translate its native output into the same original-frame `Detection` contract: label, confidence, `xyxy` box, media position, and pinned producer reference. A clip-local track ID is only an association aid; it is not a persistent person or household-object identity.

The annotation oracle and pixel detector are deliberately separate:

- `AnnotationOracleDetector` reads exact labels and can prove the evaluator, tracker, and score implementation reach a perfect ceiling. It requires `test_only=True` and is not perception.
- `SyntheticColorDetector` consumes decoded RGB pixels and a closed TOML configuration. Squared RGB distance produces a mask; the mask extent becomes an original-frame box. This provides a deterministic no-download smoke baseline for the generated artwork, not a real-home detector.
- `IoUTracker` greedily associates same-label boxes by intersection-over-union with stable tie-breaking. It is intentionally simpler than ByteTrack so its failure modes remain visible before another dependency is justified.

## What the fixed evaluator measures

The runner scores every declared annotation frame, including frames skipped by the motion scheduler. Missing predictions therefore reduce recall rather than disappearing from the denominator.

- AP50 and mAP50:95 use 101-point interpolated precision across fixed IoU thresholds `0.50:0.05:0.95`.
- Key recall and false positives expose the small-object failure separately from average scores.
- Tracking reports matched observations, ID switches, and fragmentations at IoU 0.50.
- Cost reports selected/decoded/dropped frames, detector p50/p95 wall latency, detector and pipeline FPS, real-time factor, device, and peak VRAM when the adapter can measure it.
- The receipt also records source/annotation/artifact/config/lock hashes, code revision and dirty flag supplied by the runner, dependency versions, measurement method, and model runtime metadata.

On the Windows/Python 3.12 development machine, the full-frame synthetic color baseline on browser-compatible source revision 2 produced AP50 `1.0`, mAP50:95 approximately `0.7293`, key recall and overall recall `1.0`, and zero false positives. Detector p95 was roughly 10–14 ms and the pipeline real-time factor roughly 0.14–0.16 across the recorded local checks. These numbers describe one 80-frame generated clip and cannot support an indoor-transfer or 24/7 claim.

The oracle ceiling is AP50/mAP50:95/key recall `1.0` with zero ID switches and fragmentations. The pixel baseline reaches zero ID switches and fragmentations on this easy generated clip, but that does not make tracking a passed product capability; occlusion, repeated instances, room transitions, and indoor media remain untested.

Run the same benchmark with:

```powershell
uv sync --frozen --extra video
.venv\Scripts\python.exe tools\run_b1_perception_eval.py
```

Add `--scheduled` to expose the compute/coverage trade-off. Add `--detector annotation-oracle --test-only-oracle` only for plumbing diagnostics.

## RF-DETR Nano/Small evaluation adapter

The optional `rfdetr==1.9.4` dependency is resolved in `uv.lock`, although the M12 CUDA environment used a separately recorded PyTorch stack that the current lock does not reproduce. The adapter accepts only a local reviewed Nano or Small artifact whose byte size, MD5, SHA-256, sparse COCO ID map, and scored-label allowlist are supplied before model construction. Contract tests verify clipping, sparse `44 -> bottle` mapping, SDK-name cross-checks, normalized `>=` confidence behavior, and that SDK-native objects do not escape. Model weights remain ignored and are never bundled.

The M12 screen selected Small rather than Nano because its 512-pixel input and published small-object/AP75 results were a stronger pre-result rationale for M11's failure mix. On the frozen VOST development sequence, the complete Small adapter path matched 25/51 frames, passed the p95 and VRAM gates, but failed the required 0.60 recall and recovered none of the 11 prior localization-miss frames. It is rejected without retry or reserved validation; this does not establish that RF-DETR generally fails. Official sources: [RF-DETR repository](https://github.com/roboflow/rf-detr), [1.9.4 registry](https://github.com/roboflow/rf-detr/blob/1.9.4/src/rfdetr/assets/model_weights.py), and [PyPI 1.9.4 provenance](https://pypi.org/project/rfdetr/1.9.4/).

M13 adds a narrower D-FINE Small qualification seam without promoting it to a product
dependency. It accepts one hash-pinned local Safetensors snapshot, forbids remote code
and network retrieval, validates the full dense COCO map (`39 -> bottle`, `44 ->
spoon`), and translates only canonical detections. Fake-output tests require no Torch or
Transformers; the normal constructor is the only model-loading path. One generated-input
GPU attempt passed the absolute cost and deterministic-output checks, but the artifact
is a community conversion with no verified author-checkpoint parity. No VOST accuracy
run follows from this engineering result. See the [M13 evidence report](../evaluation/m13-dfine-small-synthetic-v1.md).

The rejected inference screen is frozen in `configs/evaluation/vost-m12-rfdetr-small-v1.toml`; the older training proposal remains separately versioned in `configs/perception/rfdetr-nano-training-gate-v1.toml`. Any future specialist training experiment remains capped at 20 epochs with early-stopping patience 5, must use video/scene-separated training and validation data, must not tune on test, and must beat the same fixed quality/cost gate. No RF-DETR training has been run here.

## Deferred alternatives

Grounding DINO remains a zero-shot/open-vocabulary baseline candidate because it can query labels such as “key” without a task-specific class head. Its text/image backbone is heavier, and the current synthetic drawing is not a credible selection set. It will be tested only on a licensed frozen indoor replay set. The [official implementation](https://github.com/IDEA-Research/GroundingDINO) and [Transformers model documentation](https://huggingface.co/docs/transformers/model_doc/grounding-dino) are Apache-licensed sources for that future experiment.

ByteTrack and sliced inference are likewise deferred. They should replace the simple baseline only if they improve the fixed event/recall metric by at least 5 percentage points without answer regressions and stay within 2× p95 latency, or stay within 1 percentage point of quality while reducing measured cost by at least 30%.

## Evidence boundary

The implemented evaluator validates contract behavior and one generated clip. It does not show that a model recognizes real keys, understands containment, transfers across rooms, operates continuously, or observes physical truth. Relation inference and claim admission remain separate M4 work, and every future estimated relation still has to pass through the deterministic claim-commit boundary.
