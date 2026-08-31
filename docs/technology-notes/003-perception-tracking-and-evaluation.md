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

On the Windows/Python 3.12 development machine, the full-frame synthetic color baseline repeatedly produced AP50 `0.9604`, mAP50:95 `0.5203`, key recall `0.8857`, overall recall `0.9795`, and zero false positives. Detector p95 was roughly 10–12 ms and the pipeline real-time factor roughly 0.14–0.16. These numbers describe one 80-frame generated clip and cannot support an indoor-transfer or 24/7 claim.

The oracle ceiling is AP50/mAP50:95/key recall `1.0` with zero ID switches and fragmentations. The pixel baseline still shows three ID switches and two fragmentations under the fixed matching definition, so tracking is not yet a passed product capability.

Run the same benchmark with:

```powershell
uv sync --frozen --extra video
.venv\Scripts\python.exe tools\run_b1_perception_eval.py
```

Add `--scheduled` to expose the compute/coverage trade-off. Add `--detector annotation-oracle --test-only-oracle` only for plumbing diagnostics.

## RF-DETR Nano candidate

The optional `rfdetr==1.9.4` dependency is resolved in `uv.lock`. The adapter accepts only a local RF-DETR Nano artifact whose SHA-256 and class map are supplied before model construction; mutable aliases and implicit model downloads are not accepted. Contract tests use a fake SDK result to verify clipping, label mapping, confidence handling, and that SDK-native objects do not escape. No real checkpoint has been downloaded or benchmarked in this repository, so RF-DETR is a candidate, not a selected runtime.

RF-DETR is worth testing after a frozen indoor set exists because the official Nano model uses a DINOv2-based detection transformer, is intended for fine-tuning, and its Nano through Large code/weights are Apache 2.0. The public project excludes the Plus XL/2XL components with a different license. Official sources: [RF-DETR repository](https://github.com/roboflow/rf-detr), [installation guide](https://rfdetr.roboflow.com/latest/getting-started/install/), and [PyPI 1.9.4 provenance](https://pypi.org/project/rfdetr/1.9.4/).

The candidate limits and adoption threshold are versioned in `configs/perception/rfdetr-nano-training-gate-v1.toml`. Any specialist training experiment remains capped at 20 epochs with early-stopping patience 5. It must use video/scene-separated training and validation data, must not tune on test, and must beat the same fixed quality/cost gate. No such training has been run here.

## Deferred alternatives

Grounding DINO remains a zero-shot/open-vocabulary baseline candidate because it can query labels such as “key” without a task-specific class head. Its text/image backbone is heavier, and the current synthetic drawing is not a credible selection set. It will be tested only on a licensed frozen indoor replay set. The [official implementation](https://github.com/IDEA-Research/GroundingDINO) and [Transformers model documentation](https://huggingface.co/docs/transformers/model_doc/grounding-dino) are Apache-licensed sources for that future experiment.

ByteTrack and sliced inference are likewise deferred. They should replace the simple baseline only if they improve the fixed event/recall metric by at least 5 percentage points without answer regressions and stay within 2× p95 latency, or stay within 1 percentage point of quality while reducing measured cost by at least 30%.

## Evidence boundary

The implemented evaluator validates contract behavior and one generated clip. It does not show that a model recognizes real keys, understands containment, transfers across rooms, operates continuously, or observes physical truth. Relation inference and claim admission remain separate M4 work, and every future estimated relation still has to pass through the deterministic claim-commit boundary.
