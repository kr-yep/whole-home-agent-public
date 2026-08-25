# ADR 0003: Prove an offline read-only baseline before adding specialized memory or operation

- Status: Proposed
- Date: 2026-08-24
- Decision authority: Unassigned
- Current alignment: Selected by `DIR-002/DIR-003` as the proposed B0 basis for bounded review or an explicitly requested implementation experiment; not adopted

## Context

The whole-home vision concept may eventually need persistent history, relation traversal, multi-camera processing, richer retrieval, or controlled actions. None of those needs has yet been demonstrated by executable code, a frozen indoor evaluation set, a workload measurement, adopted household authority, or operational safety evidence.

The earlier draft proposes SQLite event audit and current-state projection. Those may be useful soon, but making them the first acceptance dependency would combine state semantics, persistence, perception, and operation before the smallest failure can be isolated. A three-day hackathon also benefits from knowing whether a failure belongs to visual perception or to relation/query logic.

## Decision

We propose the following order:

1. `B0` is one local process and one application orchestrator operating only on frozen D0 semantic replay fixtures.
2. Candidates pass one deterministic validation/commit boundary into a session-local claim ledger. Validation proves schema/invariant acceptance, not physical truth. A pure reducer creates a rebuildable typed relation view, and queries return a fixture/run/as-of-scoped evidence trace.
3. `B0` has no live source, cloud/network client, durable database requirement, Memory Core, graph database/service, vector store, LLM/VLM requirement, multi-agent coordination, device credential, action interface, or executor.
4. `B1` may add one local recorded-video perception profile only after the blocking B0 conformance cases pass. The B0 scripted producer remains the deterministic regression oracle; B1 must preserve the same downstream contract and use only synthetic/generated or lawfully usable public D0 recordings.
5. Persistence, graph, richer memory, multi-agent, live sensing, and non-safety action capabilities each require a concrete quality scenario, paired evidence against the simpler baseline, and a separate material decision.
6. Safety/life-critical actions are excluded from this architecture path. They cannot be enabled by extending a general Agent planner.
7. `B2` live/private sensing belongs to `OPERATE`, is currently `DISABLED`, and is not an automatic next step after B1. It requires R1 scope, named roles, affected-person consent, retention, executable enforcement, separate adoption, and a separate activation record before design or construction of live adapters.

This proposal does not supersede ADR 0001 or ADR 0002 while all remain `Proposed`. The repository guardrails now classify their phase applicability, but only an explicit adoption decision by recorded authority can make this ADR normative or state what it supersedes.

## Consequences

Positive:

- relation, time, provenance, abstention, replay, scope, and query semantics can be tested without CV/GPU variability;
- action capability is absent rather than protected only by prompt text or a runtime flag;
- failures have a smaller search space and complexity additions need measurable justification;
- model, storage, graph, and orchestration choices remain replaceable proposals.

Negative:

- session state is lost on process failure and must be rebuilt from the frozen source;
- B0 does not demonstrate perception quality, cross-session memory, live camera behavior, or whole-home usefulness;
- the existing SQLite-specific interim test guardrail would need an authorized update if this proposal is adopted as the normative first baseline.

Neutral:

- a Python list/dictionary or typed relation table is an implementation detail, not a Memory Core or graph authority;
- an immutable replay artifact is source evidence for a test, not evidence that a real household event occurred;
- human team parallelism does not imply a multi-agent runtime architecture.

## Alternatives considered

- Start with live camera plus detector plus SQLite: deferred because it couples governance, perception, persistence, and query failure modes and is not currently authorized.
- Start with a durable event store: deferred until cross-restart continuity or non-replayable authorized input becomes an explicit requirement.
- Start with a graph database or memory platform: rejected as a default because the first bounded relation chain can be represented and tested with simpler typed state.
- Start with multiple agents: rejected as a default because no independently scalable runtime workload or measured coordination benefit exists.
- Add an action proposal/executor interface now but keep it disabled: rejected for B0/B1 because capability absence is a stronger and smaller boundary.

## Revisit when

- B0 conformance evidence exists and B1 requires recorded-video perception;
- a predeclared restart/history requirement cannot be met by full replay;
- a frozen query/workload set shows simple typed relations cannot meet latency, correctness, or maintainability gates;
- a single orchestrator fails a measured throughput or fault-isolation scenario;
- adopted roles, consent, policy, executable enforcement, and a separately approved non-safety capability make live sensing or action design eligible for review.

## References

- `docs/minimal-viable-architecture.md`
- `AGENTS.md`
- `PROJECT_STATE.md`
- `ACTION_POLICY.md`
