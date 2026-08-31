# Hash-pinned prerecorded video, media time, and frame scheduling

**Decision status:** `IMPLEMENTED AND VERIFIED ON ONE PROJECT-GENERATED D0 REPLAY`

**Scope:** one 640×360, 10 FPS, 80-frame synthetic key/bag/sofa clip

**Does not establish:** object-detection quality, event inference, indoor generality, real-time camera operation, or 24/7 resource use

## Problems addressed

The perception adapter needs a reproducible source, correct media time, and a bounded way to avoid running an expensive detector on every frame. A filename or filesystem timestamp cannot establish capture order, and a motion-only trigger would permanently lose stationary objects after motion stops.

## Manifest and source integrity

The closed video manifest binds:

- stable source ID/revision and `D0_SYNTHETIC` use class;
- repository-relative media, annotation, and generator references;
- SHA-256 for all three artifacts;
- declared license and project-generated provenance;
- dimensions, frame count, frame rate, entities, event labels, and split.

Only manifests immediately below `examples/media/generated` are accepted. URLs, absolute paths, parent traversal, unknown fields, unresolved licenses, hash mismatches, and non-D0 source envelopes fail before decoding.

The generated MP4 is 63,283 bytes and has SHA-256 `f636b3e1e3b606f7661aadfdfbd29d14b967c2e70c0555b7f98c77281d36078c`. Two consecutive generator runs produced the same hash on the tested Windows/Python/PyAV environment. This is integrity evidence for those bytes, not proof that the depicted event is real.

## PyAV and PTS principle

[PyAV](https://pyav.org/) is a Python binding over FFmpeg. A media container stores compressed packets; the decoder reconstructs frames. Presentation timestamps (PTS) specify presentation order in units of a rational `time_base`. The adapter therefore keeps:

```text
frame_index + integer PTS + time_base numerator/denominator
```

and never substitutes file modification time. Floating-point seconds can be derived for display, but are not the canonical source coordinate. PyAV is imported lazily inside the concrete adapter, so importing the domain or B0 package opens no media and does not require the video extra.

## Motion-plus-periodic scheduling principle

For each decoded RGB frame, the scheduler samples a fixed pixel grid, converts it to grayscale intensity, and computes mean absolute difference from the previous sampled frame:

```text
motion_score = mean(abs(current_sample - previous_sample))
```

The score is only a compute hint. It cannot create a movement, containment, or location claim.

A frame is selected when:

1. it is the first frame;
2. motion exceeds the configured threshold and the minimum gap has elapsed; or
3. the periodic anchor interval has elapsed even without motion.

Periodic anchors are essential because an object that moved and then became stationary still needs occasional re-detection. All thresholds live in immutable validated configuration rather than scattered constants.

With the tested fixture configuration (`threshold=0.005`, `min_gap=2`, `anchor=10`, `stride=8`), 13 of 80 frames were selected: 1 first frame, 6 motion selections, and 6 periodic anchors. This result is fixture-specific and does not yet demonstrate detector latency savings.

## Why these components were selected

- PyAV exposes exact PTS/time-base information and ships pinned wheels for the supported environment.
- A closed manifest provides a smaller trust surface than arbitrary file upload or path input.
- Simple frame differencing is deterministic, inexpensive, and sufficient as a scheduling baseline.
- Periodic anchors avoid the known failure of pure motion-triggered detection on stationary objects.

Alternatives deferred:

- OpenCV is unnecessary for this decode/scheduling slice.
- Optical flow adds compute before a simpler baseline has been disproven.
- Background queues and live stream reconnect logic are excluded from synchronous prerecorded B1.
- Motion events are not committed because pixel change is not object-level evidence.

## Verification evidence and limits

- Manifest, annotation, and generator hashes validate.
- PyAV 18.1.0 decodes exactly 80 frames with monotonic unique integer PTS and declared dimensions.
- The scheduler exercises first, motion, skipped, and periodic-anchor paths.
- The full local suite passes with the locked video environment.
- Public-release audit accepts only the generated media plus its valid manifest.

Synthetic shapes and one clip do not support claims of indoor accuracy or external validity. Detector, tracker, relation, answer, latency, and VRAM gates remain unmeasured.

## Resource and license impact

The base B0 dependency list remains empty. The `video` optional extra is locked in `uv.lock` and contains PyAV 18.1.0, NumPy, and Pillow. The generated replay media is separately marked `CC0-1.0`. No dependency, model weight, live source, credential, or cloud route loads at package import time. `OPERATE` remains disabled.
