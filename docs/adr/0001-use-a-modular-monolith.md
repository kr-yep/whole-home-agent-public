# ADR 0001: Use a modular monolith for the hackathon MVP

- Status: Proposed
- Date: 2026-08-23
- B0 applicability: Modular-monolith responsibility boundary is compatible but not adopted
- Deferred clauses for B0/B1: live `VideoSource`, background worker, and bounded streaming queue

> Scope notice — 2026-08-24: This unadopted ADR is retained as design context. For B0, `docs/minimal-viable-architecture.md` defines one synchronous offline process and the minimum seams. Recorded B1 may add a local perception adapter; live source and streaming-runtime clauses belong to a separately authorized B2. This classification does not adopt or supersede the ADR.

## Context

Five people have three days to produce an evidence-backed home visual-memory demonstration. The camera, detector, tracker, event verifier, memory store, query interface, and UI need clear ownership so team members can work in parallel. At the same time, likely model and storage choices are not stable yet.

Microservices can create independent deployment and scaling boundaries, but they also require service discovery, serialization, networking, observability, failure handling, and coordinated local environments. Those costs do not help prove the core product within this hackathon. A single script would be quick initially, but it would couple camera, model, memory, and UI behavior and make replay testing or model replacement difficult.

## Decision

This ADR proposes one deployable Python application as a modular monolith with lightweight ports and adapters.

- `domain` owns technology-independent event, entity, relation, and temporal rules.
- `application` owns use cases and declares the ports it needs.
- concrete camera, detector, tracker, verifier, storage, telemetry, API, and UI technologies live at adapter/entrypoint boundaries.
- a single composition root selects and wires concrete implementations.
- live camera and recorded replay implement the same `VideoSource` contract.
- module dependencies remain acyclic and cross-module access uses public contracts.
- Python `typing.Protocol` is sufficient initially; we will not add a DI container or dynamic plugin framework.

The initial application may use a bounded in-process queue and one background vision worker, but no network broker. One process owns the CUDA model.

## Consequences

Positive:

- team members can work against small stable contracts without operating several services;
- detector, VLM, camera, and storage implementations can be replaced independently;
- the core can be tested with fake ports and recorded video without a camera, GPU, or cloud API;
- future extraction of a GPU worker remains possible if a real deployment boundary appears.

Negative:

- a slow or failing component can still affect the whole process unless bounded queues, timeouts, and lifecycle handling are implemented;
- Python package boundaries are conventional rather than process-enforced, so architecture tests and code review must prevent invalid imports;
- the application scales as one deployment until a component is deliberately extracted.

Neutral:

- modularity is not measured by the number of folders. We will introduce modules only around meaningful responsibilities and likely points of change.
- this decision does not select a detector, tracker, VLM, API framework, or UI.

## Alternatives considered

- One large demo script: rejected because it makes model replacement, replay tests, and parallel ownership fragile.
- Microservices plus Kafka/RabbitMQ: deferred because the operational and failure-handling cost exceeds the three-day benefit.
- Full plugin framework or DI container: deferred until third-party extension or runtime discovery becomes a demonstrated requirement.

## Revisit when

- GPU inference must run on a different device;
- a component needs independent scaling, deployment, security, or fault isolation;
- module boundaries and serialized contracts have been validated by the monolith;
- measured contention cannot be solved with a bounded local pipeline.

## References

- [Martin Fowler, Monolith First](https://martinfowler.com/bliki/MonolithFirst.html)
- [Alistair Cockburn, Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture)
- [Microsoft, Design for evolution](https://learn.microsoft.com/en-us/azure/architecture/guide/design-principles/design-for-evolution)
- [Google Cloud, Promote modular design](https://docs.cloud.google.com/architecture/framework/performance-optimization/promote-modular-design)
