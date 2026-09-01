# ADR 0013: Put the D1 oracle before media generation

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded implementation; not adopted policy

## Context

M15 found no fully eligible public target substrate. It also showed why a dataset with
boxes can still be an invalid oracle: sparse interaction annotations, tracker-derived
reference boxes, unknown negatives, or related views crossing splits can produce
plausible but misleading detector metrics.

The existing B1 quality calculator correctly computes canonical AP and recall after it
receives a complete ground-truth/prediction mapping. It did not own the upstream decision
about which frames and instances were complete enough to score.

## Decision

- Add one pure D1 target-oracle boundary before the existing quality calculator.
- Reuse canonical boxes, detections, IoU, AP, recall, and small-area buckets; do not
  create a second metric implementation.
- Require complete unique zero-based frame records, explicit scored/unknown state,
  stable instance identity and label, explicit negative frames, and reference-only
  visibility/transition semantics.
- Reject predictions on unknown frames and reject scored frames containing unknown
  instances rather than treating them as background.
- Protect participant, house/room, session, source sequence, camera/time, and synchronized
  views from crossing development, validation, or test splits.
- Keep reference transitions outside the product claim and movement-candidate path.

## Consequences

Positive:

- future data strategies have one executable output contract;
- incomplete annotations and split leakage fail before model results exist;
- existing evaluation math remains the single implementation;
- the new path is testable without media, GPU, storage, network, or runtime authority.

Negative:

- the D1 loader/validator adds schema code that future adapters must target;
- the current fixture is intentionally tiny and does not prove scale or external-format
  compatibility;
- no image realism or model transfer evidence exists yet.

## Revisit when

- a generation or acquisition adapter needs a demonstrably different coordinate,
  visibility, or grouping rule;
- a frozen external annotation convention can be translated without losing unknown and
  exhaustive-label semantics;
- temporal evaluation needs a separately specified metric rather than only a reference
  transition contract.
