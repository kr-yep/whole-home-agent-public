# ADR 0004: Route recorded perception through the B0 claim-commit boundary

- Status: Proposed
- Date: 2026-08-31
- Decision authority: Unassigned
- B1 applicability: Design and bounded experiment only; not adopted or implemented

## Context

B0 already accepts canonical `ClaimCandidate` values through one deterministic commit boundary, records accepted reports in a session ledger, rebuilds typed relations, and returns scoped answers. B1 needs a place for prerecorded-video decoding, motion gating, small-object detection, tracking, and event extraction without letting model SDK types or probabilistic output redefine those semantics.

Starting a second CV-specific event store or allowing perception to mutate current state would create competing truth paths. Exposing frames, tensors, YOLO results, tracker objects, or generic tools to domain/application code would also couple the product to the first model choice.

## Decision

This ADR proposes that B1 add one replaceable, local-only recorded-perception adapter which emits the existing canonical `ClaimCandidate` contract.

- The composition root selects the frozen semantic fixture source or the recorded-perception source.
- Decode, motion gating, detector, tracker, and event-extractor types remain inside the adapter boundary.
- Every emitted candidate carries source order, timestamp basis, provenance, artifact/config version, and epistemic status.
- Every candidate passes through the existing B0 `ClaimCommitter`; perception, an LLM/VLM, Agent, and UI cannot commit or mutate projection state.
- Runtime remains one synchronous local process until a measured quality scenario justifies concurrency.
- B1 adds no live camera/RTSP, network/cloud client, durable database, credential, action intent, executor, or physical capability.

The detailed responsibilities, failure semantics, quality scenarios, evaluation gate, and complexity triggers are in `docs/b0-b1-architecture-plan.md`.

## Consequences

Positive:

- B0 fixtures remain the deterministic regression oracle for all later perception work;
- detectors and trackers can be compared without rewriting claim, relation, or query semantics;
- model output remains an evidence-bearing report instead of becoming world authority;
- negative capability tests can prove that live/network/action paths are absent from B1 composition.

Negative:

- B1 cannot bypass validation for lower latency;
- an adapter may need internal translation code and its own contract tests;
- session state still disappears on restart and is rebuilt by replay;
- sequential replay may be slower than a streaming pipeline, but this must be measured before adding queues/workers.

## Alternatives considered

- Let YOLO/tracker write directly to current state: rejected because it merges probabilistic inference, admission, and world-state authority.
- Add a CV-specific event database first: deferred because persistence and migration are not required for the first prerecorded replay gate.
- Put detector/tracker ports in the domain: rejected because tensors and provider types are adapter concerns.
- Introduce a message broker or multi-agent runtime: deferred until a frozen workload demonstrates an independent deployment or coordination need.
- Use an LLM/VLM as the commit judge: rejected because a general model cannot be the deterministic authority boundary.

## Revisit when

- a frozen indoor benchmark proves the sequential adapter cannot meet a predeclared throughput target;
- a second concrete adapter requires a narrower internal detector/tracker contract;
- cross-run history becomes an adopted requirement with retention, correction, and migration policy;
- the typed B0 projection cannot answer a frozen required query set;
- live/private sensing becomes eligible through separately adopted roles, consent, policy, enforcement, and activation.
