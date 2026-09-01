# ADR 0014: Select a tiny project-owned vector substrate

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded implementation; not adopted policy

## Context

M16 proved the no-media D1 label-oracle contract. M17 then compared exactly the existing
project-owned 2D renderer, Blender headless procedural 3D, Kubric with licensed assets,
and STOP using frozen feasibility, provenance, delivery, storage, and dependency gates.

The existing renderer was the only candidate with every required gate supported. Blender
and Kubric offer richer rendering evidence, but an exact D1 integration and bounded
delivery were not established; Blender also needs a frozen repository-script licensing
disposition, while Kubric's canonical setup and asset path conflict with the no-cloud
requirement.

## Decision

- Select only the existing project-owned vector 2D route for one tiny D1-conformant slice.
- Preserve the current B1 golden replay and hashes; add a separate generated dataset.
- Assign protected source groups before rendering and keep every protected factor in one
  split.
- Emit image/annotation pairs, exact M16 D1 records, and seed/config/code/license/output
  hashes from one deterministic composition path.
- Treat negative, unknown, occluded, truncated, absent, location-transition, and
  containment-transition states explicitly.
- Stop after substrate conformance and reproducibility; do not load a model or train.

## Consequences

Positive:

- the smallest existing code path tests the complete data/oracle seam;
- project-owned artwork removes third-party asset acquisition and attribution ambiguity;
- the slice can fail quickly without adding a large renderer or runtime;
- Blender and Kubric remain replaceable future adapters.

Negative:

- simple vector scenes may have little or negative synthetic-to-real transfer;
- three source groups and 18 frames prove mechanics, not dataset scale;
- exact generated labels can hide failure modes present in real annotations.

## Revisit when

- the tiny vector slice fails its D1 or reproducibility contract;
- it passes mechanics but a separately frozen detector transfer gate rejects its realism;
- a Blender or Kubric route has a pinned, licensed, fully local, bounded implementation
  plan with stronger expected information value.

