# ADR 0010: Separate detector compatibility from scientific priority

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded implementation experiment; not adopted policy

## Context

M12 rejected RF-DETR Small after one valid development screen. D-FINE Small was named
as a possible localization-oriented successor, but naming and mechanism fit were not
evidence that it deserved another read of the same development sequence.

Two D-FINE integration paths had different trust properties. The author-owned `.pth`
had the strongest provenance and benchmark traceability, but required pickle parsing
and an un-packaged upstream source tree with broad import coupling. A pinned
Transformers-compatible Safetensors conversion had a narrower loader and much smaller
integration surface, but was community-converted and had no inspected parity receipt.

An engineering preflight can falsify loader, schema, deterministic-output, latency, and
memory eligibility without reading target data. It cannot decide target-domain model
quality.

## Decision

Use the exact community Safetensors conversion only for a synthetic engineering
qualification, and keep that result separate from scientific candidate priority.

- Pin the model repository revision, all required file sizes/hashes, Transformers
  version/tag/wheel, declared license metadata, dense COCO map, preprocessing, runtime,
  generated input, and strict cost gates.
- Load from the verified local directory only, with no remote code, pickle fallback,
  mutable alias, implicit download, or automatic device map.
- Preserve `artifact_provenance=COMMUNITY_CONVERTED` and
  `original_equivalence_verified=false` in the producer/runtime evidence.
- Permit one clean real-load attempt using only an in-memory generated image. Keep all
  public/private media, training, tracking, movement, claim, live, cloud, action, and
  `OPERATE` paths disabled.
- Treat p95 `<100 ms`, allocated VRAM `<1 GiB`, zero connection attempts, complete
  coverage, and constant canonical output as engineering gates only.
- Do not authorize a VOST development screen merely because those gates pass. Require a
  separate evidence comparison with materially stronger small-object relevance or stop
  off-the-shelf model swapping.

## Consequences

Positive:

- the domain/application boundary remains independent of Transformers and Torch;
- the loader has no pickle or remote-code path;
- dense COCO and threshold semantics are executable rather than implicit;
- no target-source bytes are spent on an engineering incompatibility;
- compatibility cannot silently promote itself into scientific selection.

Negative:

- the converted weights cannot inherit the original model's published metrics;
- the local CUDA environment is frozen in the receipt but not reproduced by the current
  cross-platform lock;
- one repeated generated input is only a rough absolute cost screen;
- the experiment-specific contract and runner add code that should not become product
  surface without a later positive decision.

## Observed outcome

The sole valid real-load attempt at revision
`a01799b52ce4ffeeb239bbe6eb397afa2ff64bcf` completed 51 measured calls with one
canonical digest, p95 `58.8077 ms`, peak allocated VRAM `104,530,432` bytes, and no
recorded socket attempt. No public/private media was read.

The engineering result is `ENGINEERING_COMPATIBLE_SYNTHETIC_ONLY`. The selection result
is `STOP_DFINE_SMALL_NO_DEVELOPMENT_SCREEN` because converted-weight parity is unverified
and the published D-FINE-S small-object prior is not materially stronger than nearby
alternatives. No target-data accuracy or product claim follows.

## Revisit when

- an author-issued Safetensors artifact or independently verified conversion parity
  exists;
- a candidate has materially stronger relevant prior without adapting to the same 51
  development frames;
- a separately authorized target-domain training gate is preferable to continued
  off-the-shelf model swapping;
- the CUDA dependency set has a reproducible lock.
