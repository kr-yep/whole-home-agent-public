# VISOR screen v1 — frozen Reality Gate

**Status:** bounded offline evidence, not product validation

**Run date:** 2026-09-01 Asia/Taipei

**Operation:** disabled

## Question and gate

Question: does a ready-made multiscale detector materially improve indoor annotated
target recall over a lightweight detector without exceeding the laptop budget?

The predeclared continuation signal for this first screen is at least `+10` percentage
points validation recall@0.5, with detector p95 below `100 ms` and peak VRAM below
`1 GiB`. This gate selects a method candidate only; it cannot establish whole-home
transfer or an operational model.

## Frozen substrate

| Split | VISOR source video | Frames | Useful mapped examples |
|---|---:|---:|---|
| development | `P01_03` | 61 | refrigerator, bottle, cup, spoon |
| validation | `P03_11` | 29 | refrigerator, knife, toaster |
| frozen test | `P14_05` | 22 | bowl, bottle, spoon, refrigerator |

The public config records exact Bristol URLs, byte sizes, SHA-256 hashes, license, use
class, mappings, and source-video split. Assets stay in ignored local storage. VISOR is
published under CC BY-NC 4.0, so this repository uses it only for local non-commercial
method screening and does not redistribute it.

Masks are converted to original-coordinate `xyxy` boxes. Five mapped objects contained
six polygon points at most 6.91 pixels beyond the declared 1920×1080 boundary; the
adapter clipped them under the frozen 8-pixel tolerance and recorded the counts. No
source bytes were modified.

## Paired results

Both models used torchvision `0.26.0` APIs, official hash-pinned COCO weights,
confidence `0.25`, the same RTX 4070 Laptop GPU, and the same evaluation path.

| Split | Model | Recall@0.5 | 0.1–1% area recall | p95 detector | Peak VRAM |
|---|---|---:|---:|---:|---:|
| development | SSDLite320 MobileNetV3 | 44.4% | 0/7 (0.0%) | 73.6 ms | 85.7 MiB |
| development | RetinaNet R50 FPN v2 | 72.2% | 4/7 (57.1%) | 76.8 ms | 393.3 MiB |
| validation | SSDLite320 MobileNetV3 | 14.3% | 0/3 (0.0%) | 47.4 ms | 85.7 MiB |
| validation | RetinaNet R50 FPN v2 | 25.0% | 1/3 (33.3%) | 71.7 ms | 393.3 MiB |
| frozen test, first run | SSDLite320 MobileNetV3 | 14.3% | 0/1 (0.0%) | 78.8 ms | 85.7 MiB |
| frozen test, first run | RetinaNet R50 FPN v2 | 39.3% | 0/1 (0.0%) | 76.7 ms | 393.3 MiB |

The validation gain is `+10.7` percentage points and passes the bounded continuation
signal. RetinaNet is roughly 4.6× the measured VRAM and 1.5× validation p95 latency,
but remains inside the declared laptop gate. The frozen test was evaluated once and
supports an overall recall difference, not a small-object conclusion.

## Evidence limits and decision

VISOR labels active objects, not every object visible in a scene. A generic detector can
therefore produce a correct box for an unannotated static object. AP and false-positive
counts are retained for paired diagnostics but are not evidence of exhaustive generic
object-detection precision. The screen is first-person kitchen data, not a fixed
whole-room camera; it contains no mapped target below 0.1% of frame area and no
key→bag→sofa relation label.

Decision: **CONTINUE, bounded.** Keep RetinaNet-FPN as the stronger method-screening
candidate and keep SSDLite only as the resource floor. The next experiment is one
validation-only sliced/ROI inference candidate. It must improve validation small-target
recall or overall recall materially while staying below `200 ms` p95 and `1.5 GiB`
VRAM. Do not rerun or tune on `P14_05`; obtain a new untouched source before the next
final test claim.

Reproduction entry points:

```text
python tools/fetch_public_b1_assets.py visor \
  --acknowledge-visor-use-class D0_PUBLIC_NONCOMMERCIAL_METHOD_SCREENING
python tools/fetch_public_b1_assets.py models
python tools/run_visor_screen_eval.py --device cuda
```

The evaluator writes local receipts under ignored `runs/visor-screen-v1/`. It opens no
camera, stream, account, cloud inference route, or action capability.
