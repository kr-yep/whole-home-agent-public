# VOST motion screen v1 — frozen Reality Gate

**Status:** bounded offline evidence, not product validation

**Run date:** 2026-09-01 Asia/Taipei

**Operation:** disabled

## Question and gate

Question: on real consecutive indoor frames, can the existing motion-plus-periodic
scheduler reduce full-frame RetinaNet-FPN calls while still selecting almost every
annotated object-mask change within one 5 fps frame?

The predeclared validation gate is:

- mask-change coverage, changed frame or one following frame: at least `95%`;
- avoided detector calls: at least `30%`;
- detector p95: no more than `100 ms`;
- peak VRAM: no more than `1 GiB`.

Passing advances only this prerecorded scheduling candidate. It is not authority to use
a camera and is not evidence that the detector correctly identified the changing object.

## Frozen substrate and acquisition

| Split | Upstream VOST sequence | Frames | Dimensions | Source partition |
|---|---|---:|---:|---|
| development | `8253_open_bag` | 66 | 1920×1080 | train |
| validation | `5182_open_box` | 136 | 1440×1080 | val |

VOST documents its JPEG and mask sequences as sampled at 5 fps. The adapter preserves
the `frameNNNNN` value as `source_offset`; local ordinals provide replay indexing and a
documented 1/5-second replay time base. No capture timestamps are inferred.

The official ZIP is 54,012,104,924 bytes. The range downloader verifies S3 version
`7pdbmOMes16B1h8hfbAswCyfXpBi5KwO`, ETag
`656e2cc81e3dece60378b161992b3f1d-6439`, and central-directory SHA-256
`7685955fd97adaade763a9a8f667ab8589b8fd63bac596eb207697ac68ed6d34`.
It materializes 404 selected JPEG/mask files totaling 52,172,072 bytes with canonical
manifest SHA-256 `3a4b440fd2e4d5d45363a9daf2c986799ca14a9bee0578a29f910ae41ec7863f`,
plus the upstream license, README, and train/validation lists. Every upstream byte stays
under ignored local storage and is not distributed by this repository.

The ZIP package states CC BY-NC-SA 4.0. This experiment is local, non-commercial method
screening only. The upstream license and attribution requirements continue to apply.

## Event and scheduler semantics

Only mask ID `1` is the selected transformation target; `255` is treated as void. A
mask-change event is a target-mask IoU below `0.5` between adjacent frames. Coverage is
reported in two ways:

- **exact:** the changed frame itself was selected;
- **same-or-following:** the changed frame or one later frame was selected, limiting
  scheduler evidence lag to 0.2 seconds at 5 fps.

Four thresholds were screened only on development. All other controls were fixed at
minimum gap 2 frames, periodic anchor 10 frames, and grayscale sample stride 8.

| Development threshold | Selected calls | Avoided calls | Same-or-following coverage |
|---:|---:|---:|---:|
| 0.005 | 33/66 | 50.0% | 100.0% |
| 0.010 | 33/66 | 50.0% | 100.0% |
| 0.020 | 33/66 | 50.0% | 100.0% |
| 0.030 | 33/66 | 50.0% | 100.0% |

The deterministic tie rule selected `0.03`, the most restrictive tied candidate, before
the validation result was used.

## Paired results

Both modes used the same hash-pinned torchvision RetinaNet ResNet50 FPN v2 COCO weights,
confidence `0.25`, RTX 4070 Laptop GPU, source adapter, and measurement path.

| Split | Mode | Detector calls | Avoided | Exact coverage | Same-or-following | Detector p95 | Scheduler p95 | Pipeline RTF | Peak VRAM |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| development | full frame | 66 | 0.0% | 100.0% | 100.0% | 71.52 ms | n/a | 0.45 | 393.3 MiB |
| development | motion + periodic | 33 | 50.0% | 52.9% | 100.0% | 71.93 ms | 0.74 ms | 0.24 | 393.3 MiB |
| validation | full frame | 136 | 0.0% | 100.0% | 100.0% | 65.63 ms | n/a | 0.35 | 352.2 MiB |
| validation | motion + periodic | 52 | 61.8% | 43.9% | 97.6% | 65.15 ms | 0.58 ms | 0.16 | 352.2 MiB |

The scheduled validation pass selected 40 of 41 mask-change events within the declared
one-frame window and reduced calls from 136 to 52. All four gates passed, so the bounded
decision is **CONTINUE**.

## What this does and does not show

The scheduler can pay the FPN cost on fewer 5 fps frames while retaining nearly all
declared mask-change coverage on these two sequences. Its own p95 overhead remained
below 1 ms, and paired pipeline real-time factor fell from 0.35 to 0.16 on validation.

This is not yet “record only when an object moved.” The validation exact-frame recall is
43.9%; the accepted window permits one frame of delay. Both sources are egocentric, so
global camera motion frequently triggers the simple grayscale score. No periodic-anchor
selection was needed in these clips; much of the saving comes from the two-frame minimum
gap. A fixed camera may behave differently and needs separate evidence.

RetinaNet produced plausible COCO scene labels such as bottle, cup, knife, bowl, and
refrigerator, but VOST's selected bag/box transformation mask is not a COCO-class ground
truth contract. Mask-change coverage therefore measures scheduler selection only. It
does not show target detection, identity continuity, containment, movement semantics,
or a `key → bag → sofa` answer.

## Reproduction

```text
python tools/fetch_vost_motion_subset.py \
  --acknowledge-use-class D0_PUBLIC_NONCOMMERCIAL_MOTION_SCREENING
python tools/fetch_public_b1_assets.py models
python tools/run_vost_motion_screen.py --device cuda
```

The evaluator writes local receipts under ignored `runs/vost-motion-screen-v1/`. It has
no test-source option and opens no camera, stream, account, cloud route, or action path.
