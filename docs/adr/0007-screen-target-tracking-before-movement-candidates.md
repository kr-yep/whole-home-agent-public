# ADR 0007: Screen target tracking before movement candidates

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded implementation experiment; not adopted policy

## Context

The VOST motion gate showed that the frozen scheduler can avoid detector calls while
covering mask changes, but it did not test whether the detector saw the masked object.
Adding a movement-candidate type before establishing target detection and clip-local
association would preserve compute savings around unreliable observations.

## Decision

Freeze a development-only feasibility gate before any movement-candidate work.

- Use `3518_unscrew_bottle` from the official VOST training partition for development.
- Reserve `3510_unscrew_bottle` from the official validation partition and run it only
  if every development gate passes. Add no test source.
- Map target mask ID `1` to COCO `bottle` only after fixed source-offset samples visually
  align the mask extent with the visible bottle. This is an agent visual precheck, not
  source-authored class metadata or physical-truth confirmation.
- Reuse the existing mask-to-box `GroundTruthObject`, RetinaNet-FPN, `IoUTracker`,
  perception evaluator, motion evaluator, and scheduler. Do not create a movement event,
  `ClaimCandidate`, state mutation, new model, or training path in this gate.
- Require full-frame recall@0.5 and matched-observation fraction of at least `0.60`, no
  more than one ID switch and two fragmentations, scheduled target-event coverage of at
  least `0.60`, and at least `0.90` retention versus full-frame event coverage. Retain
  the existing mask-coverage, call-saving, p95, and VRAM gates.
- Treat a development failure as a valid stop. Do not expose the reserved validation
  sequence after a failed development result.

All source bytes and receipts remain ignored and local. The path is offline,
non-commercial evaluation only and keeps `OPERATE` disabled.

## Consequences

Positive:

- the project can reject a weak target-observation path before adding semantic or memory
  complexity;
- source split, target mapping, target box, tracking, scheduling, quality, and cost are
  bound in one reproducible receipt;
- the existing VOST range downloader can accept another frozen repository-local config.

Negative:

- VOST is egocentric transformation footage, not a fixed-camera movement benchmark;
- the explicit bottle mapping depends on a bounded visual precheck because VOST does not
  provide a COCO class contract;
- the screen measures one pretrained detector and one simple tracker only.

## Observed outcome

The clean development run at code revision `581507229d43808fa6e4072b8b82ad98f8946268`
returned `REJECT_ON_DEVELOPMENT`. Full-frame recall@0.5 was `0.1961`, with five ID
switches and four fragmentations. Scheduled target-event coverage was `0.2051`, or
`0.7273` of the full-frame target-event coverage, although the scheduler still covered
all mask-change events within one frame and avoided `0.4902` of detector calls.
Validation was not run.

This contradicts only the claim that this frozen RetinaNet/tracker/scheduler path passes
the declared development gate on this source. It does not establish that all ready-made
detectors, fine-tuned models, trackers, fixed-camera sources, or home-object systems fail.

## Revisit when

- a detector candidate has a predeclared reason to improve transparent/occluded bottle
  target recall without using validation feedback;
- a fixed-camera, lawfully reusable source with object identity and spatial-movement
  annotations is frozen;
- a training proposal preserves the 20-epoch, patience-5 cap and separate validation.
