# Candidate-source seam and run receipt

**Decision status:** `IMPLEMENTED AND VERIFIED WITH SYNTHETIC CONTRACT TESTS`

**Scope:** B0 semantic fixtures and in-memory D0 candidates only

**Does not establish:** video decoding, perception accuracy, household transfer, live sensing, or operational safety

## Problem

B0 originally accepted only one closed JSON fixture type. B1 needs to translate prerecorded media into the same canonical claims without giving a detector, tracker, UI, or future model access to the ledger or projection. Creating a second B1 write path would make idempotency, conflicts, containment cycles, and query semantics diverge.

## Principle

The dependency-inversion seam is a narrow `ClaimCandidateSource` protocol. A source owns only sequential candidate production and deterministic closure. The application orchestrator owns validation, commit, projection, receipt creation, and the decision to expose a completed session.

```text
ReplayFixture / future recorded-video adapter
  -> ClaimCandidateSource
  -> source and evidence validation
  -> the existing ClaimCommitter
  -> relation projection
  -> ReplaySession only on COMPLETE
```

`SourceDescriptor`, `SourcePosition`, `ProducerRef`, and `EvidenceRef` keep source identity, replay coordinates, producer hashes, and minimal evidence pointers separate from claim semantics. Raw pixels, arbitrary paths, URLs, tensors, and provider objects have no field in these contracts.

`RunReceipt` is execution evidence, not an evaluation verdict. It records the bounded source/run identity, counts, stage timing, versions, and either the completed semantic hash/frontier or a typed failure. `FAILED` and `INCOMPLETE` results always carry `session=None`; partial accepted state is never queryable.

## Inputs and outputs

- Input: a finite local source with a hash-pinned descriptor and canonical `ClaimCandidate` values.
- Success: `ReplayRunResult(COMPLETE, receipt, ReplaySession)`.
- Source interruption after progress: `ReplayRunResult(INCOMPLETE, receipt, None)`.
- Admission or commit failure: `ReplayRunResult(FAILED, receipt, None)`.
- The legacy `run_fixture()` wrapper preserves existing B0 typed exceptions and public behavior.

## Why this was selected

- It keeps one authoritative claim-commit path.
- It adds an interface only where a real second adapter is planned and a fake implementation already tests it.
- It keeps the domain free from video/model SDK types.
- It allows source failure injection without queues, services, databases, or a plugin framework.

Alternatives rejected for this gate:

- A B1-specific ledger or direct projection writer would duplicate semantic authority.
- Passing detector/tracker objects into the application would leak vendor types across the adapter boundary.
- A queue or event broker would add failure and recovery semantics that synchronous prerecorded replay does not need.

## Verification evidence

- Existing B0 conformance and CLI tests remain green.
- The frozen `b0-key-bag-sofa` semantic output remains SHA-256 `226d30a5b826720d607d0b9a29bf3dfb9f5429eeedbbd70ffd1ff23c21233c8f`.
- Generic in-memory replay produces the same ledger, projection, answer, and semantic hash as `run_fixture()`.
- Failure before the first candidate and after partial delivery returns no session.
- Unpinned descriptors, missing evidence, mismatched scope, URL/absolute manifest references, and B0 self-promotion to `estimated` fail closed in tests.

This evidence is executable and behavioral only for the declared synthetic contract cases. It does not support claims about CV quality or real household events.

## Failure modes and limits

- A valid hash identifies bytes; it does not establish source authenticity, license truth, annotation correctness, or physical truth.
- Timing fields are diagnostic measurements and are not part of the deterministic semantic hash.
- Idempotency deliberately ignores delivery offset and evidence delivery metadata. The first accepted provenance is retained for a duplicate semantic claim ID.
- Invalid descriptors are rejected before a run receipt can truthfully describe a pinned source; the source is still closed.
- OS-level capability denial is not established by these Python types. Live and private sources remain absent and prohibited by governance.

## Resource and license impact

The seam uses only the Python standard library and adds no runtime dependency. Original code remains under the repository MIT license. `OPERATE` remains disabled.
