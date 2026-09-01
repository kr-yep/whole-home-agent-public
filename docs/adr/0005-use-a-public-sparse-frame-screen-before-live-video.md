# ADR 0005: Use a public sparse-frame screen before any live-video work

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded implementation experiment; not adopted policy

## Context

The generated B1 clip proves composition and relation semantics but says nothing about
real indoor perception. Live or private sensing remains prohibited, and downloading a
full multi-hour video corpus would add cost before the detector boundary is credible.
VISOR publishes sparse first-person kitchen frames and active-object masks under a
non-commercial license. Those masks can be converted into boxes for a small indoor
method screen, but the frame set has source indexes rather than declared capture PTS,
and active-object annotations are not exhaustive scene-object annotations.

## Decision

This ADR proposes one local-only `visor-screen-v1` evaluation adapter.

- Freeze `P01_03`, `P03_11`, and `P14_05` by source video as development,
  validation, and test respectively before detector results are inspected.
- Keep images, annotations, archives, and model weights under Git-ignored local paths.
  Commit only source URLs, license/use metadata, sizes, full SHA-256 values, adapters,
  and derived evidence.
- Preserve the original source frame index as `source_offset` with the explicit
  `source_frame_index` timestamp basis. Never infer capture time from filenames or
  filesystem metadata.
- Convert mapped mask polygons to canonical boxes inside the VISOR adapter. Clip only
  coordinates within a declared 8-pixel annotation tolerance and report every clip.
- Score only explicit, defensible VISOR-to-COCO label mappings. Treat recall and
  localization on annotated targets as the primary evidence; generic-detector false
  positives and AP are limited because unannotated scene objects may be real objects.
- Compare a lightweight SSDLite320 baseline with a RetinaNet ResNet50 FPN v2 baseline
  using hash-pinned official torchvision weights, the same threshold, hardware, data,
  and measurement path.
- Run the frozen test only once locally. Later tuning uses development/validation and
  needs a new untouched test source before another final claim.

This is an evaluation path only. It does not emit household claims, change the B0
commit/query path, add live capture, or enable operation.

## Consequences

Positive:

- real indoor images challenge the detector before any live-camera integration;
- source-video splits and hashes make paired results comparable;
- the lightweight-versus-multiscale cost trade-off is measured on the user's GPU;
- third-party media and weights remain outside the public repository.

Negative:

- sparse egocentric kitchen frames do not reproduce a fixed security-camera stream;
- VISOR active-object labels cannot prove generic-scene precision;
- the selected screen contains no target below 0.1% of frame area and does not label
  the desired key-inside-bag-to-sofa relation;
- the non-commercial license prevents treating this screen as unrestricted product
  training data.

## Alternatives considered

- Record a household webcam now: rejected because `OPERATE` and private sensing are
  disabled and no consent/retention controls exist.
- Download the complete 28.4 GiB VISOR release: deferred because three source-separated
  sequences are sufficient for the first falsifiable gate.
- Use public livestreams: rejected because consent, license, ground truth, and replay
  stability are generally inadequate.
- Tune on the frozen test: rejected because it would destroy the comparison boundary.
- Add an Ultralytics runtime to the MIT package immediately: deferred pending license
  and dependency review; the first paired baseline uses torchvision's reviewed path.

## Revisit when

- a validation-only sliced/ROI experiment passes or fails its declared quality/cost
  gate;
- a new license-compatible fixed-camera indoor set is available;
- container/occlusion relation labels are needed rather than detector screening;
- live/private sensing becomes eligible through separate governance and activation.
