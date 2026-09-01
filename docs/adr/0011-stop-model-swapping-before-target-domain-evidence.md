# ADR 0011: Stop model swapping before target-domain evidence

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded research decision; not adopted policy

## Context

M12 showed that a stronger generic detector could improve the finite development count
and still fail the target recall gate. M13 showed that engineering compatibility and
low inference cost do not create scientific priority. M14 compared exactly two further
COCO-only candidates without reading media.

D-FINE Medium clears a narrow same-family COCO improvement over D-FINE Small.
RT-DETRv2 Small does not. Neither provides a material same-protocol comparison against
the RF-DETR Small path that was actually screened and rejected on the target sequence.
Generic AP-small and AP75 also do not identify the cause of that local failure or prove
fixed-camera indoor transfer.

## Decision

Stop the current off-the-shelf detector tournament.

- Do not download or preflight D-FINE Medium solely because it scales the already
  engineering-compatible D-FINE family.
- Do not integrate RT-DETRv2 Small; it fails the frozen material-gain subgate and its
  author artifact route is not immutable and safe-loader complete.
- Treat the M14 config's omission of the failed RF-DETR comparator as a fail-closed
  scope gap, not permission to narrow the Goal after seeing results.
- Require a separate target-domain data/training reality gate before any training,
  additional detector selection, development read, or reserved/test read.
- Keep tracker replacement independent; a detector-only pass cannot erase the oracle
  tracker's 16 ID switches.

## Consequences

Positive:

- development evidence is no longer spent on an adaptive model tournament;
- engineering ease and generic COCO gains cannot masquerade as product evidence;
- the next investment targets the missing domain evidence rather than another loader;
- no model/media bytes or operation authority are added.

Negative:

- a D-FINE Medium target improvement remains possible but unmeasured;
- target-domain data may be unavailable or too weak, which can stop training entirely;
- the existing detector and tracker observation path remains rejected.

## Revisit when

- a lawful target-domain substrate and frozen source-separated evaluation exist;
- an independently relevant candidate dominates the failed path under a comparable
  protocol rather than only on generic COCO;
- a bounded target-trained recipe passes its predeclared validation gate;
- tracker evidence can be evaluated without conflating it with detector quality.
