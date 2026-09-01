# M16 target-label-oracle feasibility proposal

## Purpose

Prove that the project can represent and score the intended detector evidence before it
spends time on media generation, acquisition, labels, models, or training. This is a
no-media design and conformance gate.

## Smallest implementation slice

Define one versioned synthetic-only D1 annotation contract and one pure evaluator for:

- source group, sequence, frame index/time basis, dimensions, stable instance ID, class,
  box coordinates, and visibility state;
- explicit present, occluded, absent, truncated, and unknown handling;
- complete evaluated-frame accounting, including empty negative frames;
- recall at IoU 0.50, AP50:95, recall for 0.1–1% frame-area objects, and false positives
  per evaluated frame;
- a separate temporal transition reference keyed by persistent instance, without
  creating product `MovementCandidate` or semantic claims;
- split validation that keeps a participant, house/room, session, source sequence,
  camera/time group, and synchronized views together.

Use tiny semantic fixtures, not images. Predeclare fake prediction cases:

1. perfect predictions must score perfectly;
2. empty predictions must produce zero recall without pretending evaluation failed;
3. duplicate predictions must add a false positive;
4. wrong-class and badly localized predictions must not match;
5. empty negative frames must count in the FP/frame denominator;
6. unknown/unscored frames must not be treated as negatives;
7. cross-group or synchronized-view leakage must fail validation.

## Pass gate

Pass only if every frozen fixture produces the exact expected metric and split result,
results are invariant to input ordering, all evaluated frames are accounted for, and
the existing public B0/B1 suite remains green. Missing, duplicate, or conflicting
source/frame/instance identities must fail closed.

If the schema cannot express these cases without importing CV/model/storage/runtime
technology into the domain, stop and revise the boundary. If it passes, the next Goal
may compare at most three no-media generation strategies and `STOP`, with the existing
project-generated renderer as the reuse baseline.

## Boundaries

No image or video generation, media/archive download, household recording, detector or
tracker load, training, VOST/VISOR or reserved-source read, movement candidate, accepted
claim, live/private/cloud/action connection, or `OPERATE` enablement is authorized.
