# VOST target-tracking screen v1

**Status:** `VALID DEVELOPMENT RUN / REJECTED ON DEVELOPMENT`  
**Runtime:** `OPERATE DISABLED`  
**Validation source:** reserved and not run

## Bounded conclusion

Under the hash-pinned VOST `3518_unscrew_bottle` development sequence, torchvision
RetinaNet ResNet50 FPN v2, the existing greedy IoU tracker, and the frozen scheduler,
the observed result rejects this exact target-observation path before movement-candidate
work. It does not establish a general limit for pretrained detectors, tracking, or
fixed-camera home scenes.

## Frozen design

- Development: official VOST train sequence `3518_unscrew_bottle`, 51 paired JPEG/mask
  frames at the documented 5 fps replay rate.
- Reserved validation: official VOST validation sequence `3510_unscrew_bottle`, 69 pairs;
  not run unless development passed every gate.
- Local subset: 240 files, 39,189,582 bytes, canonical hash
  `1e9f53eb1c0e302a0eea54cb5d9bff86d5029ee207b6bb7168c6260a199de060`.
- Target mapping: mask ID `1` to COCO `bottle`, after an agent visual precheck at the
  frozen offsets recorded in the config and receipt.
- Model: torchvision `0.26.0+cu128`, torch `2.11.0+cu128`, RetinaNet artifact SHA-256
  `5905b1c544219215e544dbe319720397bc4e68de61a733a59350d7976645b769`.
- Hardware: NVIDIA GeForce RTX 4070 Laptop GPU, Windows 11, Python 3.12.13.
- Clean code revision: `581507229d43808fa6e4072b8b82ad98f8946268`.

No test source, household data, live camera, cloud inference, model training, or action
capability was used.

## Development result

| Measure | Observed | Gate | Result |
|---|---:|---:|---|
| Full-frame recall@0.5 | 0.1961 | >= 0.60 | Fail |
| Matched-observation fraction | 0.1961 | >= 0.60 | Fail |
| ID switches | 5 | <= 1 | Fail |
| Fragmentations | 4 | <= 2 | Fail |
| Full-frame target-event coverage | 0.2821 | reference | — |
| Scheduled target-event coverage | 0.2051 | >= 0.60 | Fail |
| Scheduled/full target-event retention | 0.7273 | >= 0.90 | Fail |
| Mask-change selection coverage | 1.0000 | >= 0.95 | Pass |
| Avoided detector calls | 0.4902 | >= 0.30 | Pass |
| Scheduled detector p95 | 73.76 ms | <= 100 ms | Pass |
| Scheduled scheduler p95 | 0.74 ms | reported | — |
| Peak VRAM | 412,383,744 bytes | <= 1 GiB | Pass |
| Full/scheduled real-time factor | 0.416 / 0.246 | reported | — |

Additional descriptive values were AP50 `0.1436`, mAP50:95 `0.0808`, small-object
recall `0.0455` for 22 targets occupying 0.1–1% of the frame, and large-object recall
`0.3214` for 28 targets at or above 1%.

The result followed the predeclared stopping rule. Validation remained untouched and is
not a missing zero or failed score; it is **not run because development failed**.

## Claim ledger

| Claim ID | Evidence class | Exact evidence | Permissible wording | Forbidden inference |
|---|---|---|---|---|
| M10-C1 | Integrity / executable | Config hash, subset hash, clean run receipt | The frozen development path ran on verified local source bytes | The source class label is source-authored COCO truth |
| M10-C2 | Behavioral | 51-frame development metrics | This RetinaNet path missed the declared recall/tracking gates on this sequence | RetinaNet cannot detect household bottles in general |
| M10-C3 | Comparative | Paired full/scheduled target-event coverage | Scheduling retained 72.7% of full-frame target-event coverage while avoiding 49.0% of calls | Scheduling caused every miss or is unusable on fixed cameras |
| M10-C4 | Recorded | Validation gate is null; receipt says no test source | Validation was not run after development rejection | Validation performance is zero or would also fail |

## Evidence limits and next decision

VOST records egocentric object transformation, not stable-camera spatial movement. A
mask-change event is not a home-object movement event, and an IoU track is not persistent
household identity. The failure is sufficient to stop semantic movement work on this
exact observation path, but not to choose a replacement model.

The next smallest useful task is failure localization on development only: determine
whether misses are dominated by confidence filtering, localization IoU, target size,
occlusion/absence, or label mismatch using already-produced detector outputs or one
instrumented development rerun. That diagnostic must not move thresholds or expose the
reserved validation sequence.
