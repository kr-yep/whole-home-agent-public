# ADR 0002: Store semantic events and project current state

- Status: Proposed
- Date: 2026-08-23
- B0 applicability: Deferred
- Roadmap scope: B1/B2 persistence candidate only after a measured persistence trigger and separate adoption

> Scope notice — 2026-08-24: This unadopted persistence proposal is not a B0 requirement. Legacy `semantic fact`, `event`, and `current state` wording means, at most, an accepted claim record and rebuildable state estimate; it is not physical truth. SQLite remains deferred, not rejected, superseded, or adopted for a later phase.

## Context

The product must answer both "where is the object now?" and "what evidence led to that answer?" For example, the camera may observe a key being placed inside a bag and later observe only the bag moving to a sofa. Saving only the latest object location loses the explanation; saving every frame as an event creates excessive storage and noise.

Full Event Sourcing provides immutable history and rebuildable projections, but it also requires disciplined schema evolution, replay/upcasting, ordering, snapshot, privacy, and consistency design. That infrastructure is disproportionate for a three-day MVP. A graph database is also unnecessary for the first relation chain and would add another operational dependency.

## Decision

If separately adopted for a post-B0 phase, this ADR proposes distinguishing transient video data from durable accepted-claim records.

- Frames and model observations travel through bounded in-process buffers and are not durable domain events.
- Only schema/invariant-accepted claim records, corrections, retractions, confirmations, and privacy-deletion records enter the audit store; acceptance does not prove the physical proposition.
- Events use a versioned, CloudEvents-inspired envelope with stable identity, source/camera/session sequence, occurrence and ingestion time, epistemic status, confidence, evidence references, and model/config provenance.
- SQLite stores an append-oriented semantic event audit table and a query-optimized current-state/relation projection.
- Event application is idempotent. Corrections append new events rather than rewriting ordinary history.
- Privacy deletion is an explicit exception: it must remove governed personal artifacts and affected derivatives even when that reduces historical completeness.
- Query logic infers a location through active relations. A container movement does not fabricate a direct observation that every hidden item moved.

We deliberately describe this as an event audit plus projection, not as full Event Sourcing or CQRS.

## Consequences

Positive:

- answers can include a claim/evidence chain and distinguish source reports from derived estimates;
- current locations remain fast to query while event history supports debugging and replay;
- duplicate processing can be made safe with stable event identity;
- event contracts can later cross a process boundary without changing domain semantics.

Negative:

- projection, ordering, correction, schema-version, and retention behavior need explicit tests;
- event and projection tables duplicate some information;
- deleting private data can conflict with audit completeness and therefore needs a documented cascade policy.

Neutral:

- SQLite is a deferred B1/B2 roadmap candidate, not a B0 requirement or part of the domain model.
- event history does not guarantee that an inference is true; epistemic status, confidence, abstention, and evidence remain mandatory.

## Alternatives considered

- Store only current location: rejected because it cannot explain container propagation or reconstruct how an answer was reached.
- Persist every frame/detection: rejected because frames are high-volume transient data and contain unnecessary private content.
- Full Event Sourcing/CQRS: deferred until audit/reconstruction requirements justify its schema and operational cost.
- Neo4j or another graph database: deferred; the initial typed relation projection fits SQLite and in-memory traversal.

## Revisit when

- state must be rebuilt from a long production history under multiple schema versions;
- independent read/write scaling or many downstream event consumers are required;
- SQLite write contention is measured under the intended multi-camera load;
- legal/privacy requirements establish a different retention or erasure model.

## References

- [CloudEvents specification](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md)
- [Microsoft, Event Sourcing pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)
- [Microsoft, Publisher-Subscriber pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/publisher-subscriber)
- [NIST Privacy Framework](https://www.nist.gov/privacy-framework)
