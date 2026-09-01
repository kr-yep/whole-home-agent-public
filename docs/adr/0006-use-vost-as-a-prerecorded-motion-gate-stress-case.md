# ADR 0006: Use VOST as a prerecorded motion-gate stress case

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded implementation experiment; not adopted policy

## Context

The sparse VISOR screen selected RetinaNet-FPN as the stronger ready-made detector,
but sparse frames cannot answer whether motion-plus-periodic scheduling avoids enough
detector calls without skipping object-change evidence. Live cameras and private
household media remain prohibited. A useful substrate therefore needs consecutive
public frames, source-separated development and validation data, object-change ground
truth, a verifiable license, and a download path that does not require the full corpus.

VOST publishes JPEG sequences sampled at 5 fps, matching transformation masks, raw
MP4 files, and official split lists. Its package is CC BY-NC-SA 4.0 and is hosted as a
54 GB public S3 ZIP with byte-range support. The videos are egocentric, so they are a
deliberately difficult camera-motion case rather than a proxy for a fixed home camera.

## Decision

This ADR proposes the local-only `vost-motion-screen-v1` evaluation path.

- Freeze `8253_open_bag` from the upstream training partition as development and
  `5182_open_box` from the upstream validation partition as validation. Add no test
  source and expose no test-selection flag.
- Fetch only the configured JPEG/mask members plus upstream license, README, and split
  files. Verify the S3 version header, ETag, object length, central-directory SHA-256,
  ZIP CRC, extracted size, per-file SHA-256, and canonical subset hash. Keep every
  third-party byte and receipt under Git-ignored local paths.
- Preserve the original `frameNNNNN` number as `source_offset`. Use the local ordinal
  as `frame_index` and PTS only for a 5 fps replay clock explicitly supported by the
  upstream README. Do not claim an original capture timestamp.
- Define one bounded scheduler target: a mask-change event occurs when target-mask IoU
  between adjacent 5 fps frames is below `0.5`. Coverage means the scheduler selects
  the changed frame or one following frame, a maximum lag of 0.2 seconds.
- Screen motion thresholds `0.005`, `0.01`, `0.02`, and `0.03` only on development.
  Among candidates with at least 95% coverage, maximize avoided detector calls and use
  the higher threshold to break exact ties. Freeze every other scheduler parameter.
- Compare full-frame and scheduled RetinaNet-FPN passes on both sources. Continue only
  if validation coverage is at least 95%, avoided calls at least 30%, detector p95 no
  more than 100 ms, and peak VRAM no more than 1 GiB.
- Treat mask-change coverage as a scheduling measurement, not evidence that RetinaNet
  detected, identified, or understood the transformed VOST target.

This path is evaluation-only. It does not emit `ClaimCandidate`, mutate the session
ledger, open a camera/stream, access household data, or enable `OPERATE`.

## Consequences

Positive:

- the existing scheduler and selected FPN detector are measured on real consecutive
  indoor imagery before any live-source design;
- development selection and validation evaluation are executable and separated;
- the range downloader materializes about 52 MB of selected data rather than a 54 GB
  archive and retains exact source/license evidence;
- the same canonical frame and detector contracts remain replaceable.

Negative:

- ego-camera motion makes the grayscale motion score fire frequently; savings may come
  partly from the minimum frame gap rather than stationary-scene rejection;
- a one-frame coverage window tolerates 0.2 seconds of lag and exact-frame coverage is
  reported separately;
- VOST masks transformation targets but does not provide a directly usable COCO class
  for the selected bag/box sequences;
- CC BY-NC-SA 4.0 restricts this substrate to non-commercial screening and affects any
  distributed adapted dataset material.

## Alternatives considered

- Use a live webcam or RTSP stream: rejected because sensing, consent, retention, and
  operational enforcement are not authorized.
- Download the complete VOST package: rejected because HTTP Range can retrieve the
  frozen members and authoritative metadata without the 54 GB cost.
- Use CAD-120 immediately: deferred because an authoritative, currently accessible
  source and license package could not be validated for automated acquisition.
- Treat full-frame RetinaNet output as truth: rejected because model agreement is not
  physical ground truth and the selected VOST target is not a COCO category contract.
- Tune on an additional test sequence: rejected; this gate needs no test claim and a
  future final product claim requires a separately frozen source.

## Revisit when

- a fixed-camera, license-compatible indoor sequence with object identity and movement
  annotations becomes available;
- scheduled detections are connected to clip-local tracks and conservative event
  candidates without promoting model output to fact;
- commercial data/model terms are required;
- live/private sensing becomes eligible through separate governance and activation.
