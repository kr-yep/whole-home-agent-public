# ADR 0008: Separate detection and association failure localization

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded implementation experiment; not adopted policy

## Context

M10 rejected one RetinaNet, greedy-IoU-tracker, and scheduler path on development.
Aggregate recall and ID-switch counts could not distinguish an absent class proposal,
confidence filtering, poor localization, missing target, or downstream association.
Choosing a replacement from those aggregate values would be underdetermined.

## Decision

Add one evaluation-only diagnostic seam to the existing torchvision adapter and one
development-only runner.

- Keep the canonical product threshold at `0.25`; low-score output cannot be returned
  as `Detection`.
- Read only post-processed proposals at or above RetinaNet's pinned `0.05` floor and
  classify every development frame exactly once.
- Keep absent/void, no class proposal, confidence-filtered proposal, localization miss,
  and match mutually exclusive.
- Feed mask-derived boxes separately through the unchanged tracker to test association
  without detector localization or confidence failure.
- Route a below-gate detector before tracker replacement because association cannot
  recover observations that were not admitted. Preserve a failed oracle tracker as a
  separate blocker.
- Never load reserved validation after an M10 development failure, and create no model
  training, movement candidate, claim, state mutation, or action path.

## Consequences

Positive:

- low-score diagnostic data remains structurally separate from product output;
- one model pass localizes the finite development failures without threshold tuning;
- detector and tracker limitations can be reported independently.

Negative:

- RetinaNet's own post-processing hides candidates below `0.05` and pre-NMS anchors;
- categories are descriptive symptoms, not causal explanations of network behavior;
- VOST masks and egocentric transformation remain weak proxies for a fixed home camera.

## Observed outcome

All 51 visible target frames had a bottle proposal at or above `0.05`. Thirty were
confidence-filtered, 11 were localization misses, and 10 matched at the product gate.
Only 16 of the 30 low-score frames were IoU-matchable, so threshold-only inclusion down
to `0.05` has a `26/51 = 0.5098` matched-frame upper bound and cannot reach the unchanged
`0.60` gate on these outputs. The oracle-box tracker produced 16 ID switches despite
51/51 matched observations.

The result supports a detector replacement gate and records tracker replacement as a
second requirement. It does not establish home-scene transfer, physical truth, or a
specific replacement's superiority.

## Revisit when

- a replacement detector passes development and needs the reserved validation gate;
- a tracker candidate can be compared on both oracle boxes and the frozen detector
  outputs;
- a lawful fixed-camera object-movement source is frozen.
