# ADR 0016: Select the synthetic end-to-end replay as the primary demo

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- Applicability: Explicitly requested bounded hackathon implementation; not adopted policy

## Context

The repository has one fully packaged project-owned prerecorded key→bag→sofa replay,
one ignored two-frame real small-bbox oracle, and no validated new model/data story.
The primary hackathon demo must be clear in about 90 seconds, reproducible by teammates,
show end-to-end user value and evidence boundaries, and avoid unsupported claims.

## Decision

Use the existing project-owned prerecorded end-to-end replay as the primary demo. Keep
M26 as optional mechanical CV evidence, not a required visual or accuracy result. Defer
new model/data work to a separate protected-group development plus untouched-test
contract. Preserve `OPERATE DISABLED` and the local prerecorded boundary.

## Consequences

Positive:

- the main story is already runnable, traceable, public, and scoped to the three-day
  delivery envelope;
- judges see the product value—object/container/location memory and a query answer—rather
  than a disconnected detector box;
- third-party data and unproven accuracy are not hidden dependencies.

Negative:

- the primary visual is synthetic and cannot establish real-home CV performance;
- the fixed question demonstrates a scoped query rather than general conversation;
- real small-object evidence remains a tiny optional smoke, not a gain measurement.

## Revisit when

- a protected-group indoor development/test contract produces paired gain and cost
  evidence without test tuning;
- a teammate exercise finds the public primary demo non-reproducible;
- the judge format materially differs from the current 90-second assumption.
