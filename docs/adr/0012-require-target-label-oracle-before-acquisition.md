# ADR 0012: Require a target-label oracle before data acquisition

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded research decision; not adopted policy

## Context

M14 stopped the off-the-shelf model tournament because generic benchmark improvements
did not establish target-domain priority. M15 then applied a frozen no-media substrate
gate to exactly HOMAGE, CAD-120, and Watch-n-Patch.

None passed every required gate. HOMAGE's scene graphs are sparse interaction samples;
CAD-120's intermediate boxes are tracker-derived and its current official rights and
acquisition path were not established; Watch-n-Patch does not establish per-frame
reference object boxes and likewise lacks a verified current official rights/acquisition
path. All emphasize staged interactions rather than an exhaustive passive inventory.

The review also exposed that the metric oracle itself is underspecified. A dataset name
or an annotation file is not enough to decide which unlabelled objects are negatives,
how occlusion affects denominators, or whether synchronized views leak across splits.

## Decision

- Select no M15 public candidate and perform no acquisition dry run.
- Before acquiring or generating media, prove a no-media D1 label-oracle and metric
  contract using deterministic synthetic annotations and fake predictions.
- Require dense scored-instance coverage, stable identities, explicit negative frames,
  visibility states, complete frame accounting, and source-group split invariants.
- Treat `UNKNOWN` as selection-ineligible without rewriting it as factual failure.
- Apply tie-breaks only among candidates whose every required eligibility gate passes.
- Keep detector and tracker evaluation separate; tracker-derived boxes cannot be the
  sole independent oracle for the tracker they evaluate.

## Consequences

Positive:

- the project can test its scoring semantics without media, GPU, licensing, or privacy
  risk;
- future public, synthetic, or project-generated data must fit one explicit contract;
- sparse interaction labels cannot silently become exhaustive detector negatives;
- three-day effort is spent on a reusable measurement seam rather than another dataset
  or model integration.

Negative:

- no target-domain training is authorized yet;
- realism, detector transfer, and target performance remain unmeasured;
- a later data source may require an explicit adapter and a separately frozen split.

## Revisit when

- the D1 oracle and hostile metric cases pass deterministically;
- one lawful data-generation or acquisition design can satisfy that oracle within the
  declared time and storage budget;
- affected-person consent and policy are separately resolved before any real recording.
