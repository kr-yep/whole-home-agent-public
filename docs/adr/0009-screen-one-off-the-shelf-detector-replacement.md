# ADR 0009: Screen one off-the-shelf detector replacement before validation

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded implementation experiment; not adopted policy

## Context

M11 showed that threshold-only inclusion could not meet the existing recall gate and
that the incumbent detector had both confidence-filtered and localization-miss frames.
A replacement needed a pre-result reason to address both while retaining local,
offline, bounded inference.

RF-DETR Nano had the lowest integration cost, but its published small-object result and
384-pixel input did not align with the dominant sub-1% target subset. RF-DETR Small used
the same reviewed Apache-2.0 package family while providing a 512-pixel input and a
stronger published small-object and AP75 rationale. D-FINE Small and RT-DETRv2 Small
were plausible alternatives, but each required a new artifact/adapter contract. The
published metrics were not treated as locally comparable performance evidence.

## Decision

Freeze RF-DETR Small 1.9.4 as the only M12 candidate and permit exactly one development
screen after a synthetic-only compatibility preflight.

- Bind package, source commit, wheel hash, official checkpoint generation, MD5,
  SHA-256, byte size, Apache scope, and full sparse COCO label map.
- Normalize the SDK's strict threshold behavior to canonical `confidence >= 0.25` and
  keep M10's seven-label allowlist.
- Freeze CUDA 0, 512-pixel model input, FP16, non-compiled in-place inference, no source
  image retention, one excluded warm-up, deterministic flags, and actual dependency
  versions.
- Require a clean worktree and a persistent exclusive attempt marker. Any runtime,
  integrity, network, completeness, or metric breach invalidates the attempt without a
  retry.
- Evaluate only `3518_unscrew_bottle`; require recall@0.5 `>= 0.60`, detector p95
  `< 100 ms`, and peak VRAM `< 1 GiB`.
- Keep AP, false positives, size buckets, and paired M11 recovery descriptive. They do
  not alter the three frozen gates.
- Do not train, load reserved/test data, create a movement candidate or claim, connect
  live/private/cloud/action capability, or enable `OPERATE`.

## Consequences

Positive:

- the real SDK path now validates sparse COCO IDs instead of indexing them as a dense
  list;
- artifact identity and inference semantics are portable even though the local path is
  machine-specific;
- one-run and offline constraints are executable rather than report-only promises;
- cost and quality are measured on the same finite source and evaluator as M10.

Negative:

- the runner and frozen contract add experiment-specific validation code;
- the Python socket guard covers the SDK's Python connection path but is not OS-level
  network isolation;
- the actual CUDA package set diverges from the current cross-platform `uv.lock`;
- one run cannot estimate latency stability or external validity.

## Observed outcome

The valid clean run at revision `4aa0a2ad87dd100be5b38f0db5a01082ab023eb9`
matched 25/51 frames (`0.4902`) versus the M10 comparator's 10/51 (`0.1961`). It
passed p95 (`49.7820 ms`) and peak VRAM (`149,987,840` bytes), but failed the unchanged
recall gate, which required at least 31 matches. It recovered 16/30 prior
confidence-filtered frames, none of the 11 prior localization-miss frames, and retained
9/10 prior matches. Reserved image/mask bytes were not read and validation was not run.

The predeclared decision is `STOP_RFDETR_SMALL_CANDIDATE`. The observed improvement on
this finite development sequence cannot override the gate or support a general RF-DETR,
small-object, indoor, fixed-camera, tracking, movement, or production claim.

## Revisit when

- a D-FINE Small or other localization-oriented candidate has an immutable licensed
  artifact, safe loader, closed adapter contract, and synthetic compatibility evidence;
- a dedicated CUDA lock can reproduce the measured environment;
- a lawful fixed-camera object-movement source and a separate tracker co-gate exist.
