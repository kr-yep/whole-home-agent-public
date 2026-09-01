# ADR 0015: Select BOP YCB-V as the real transfer oracle

- Status: Proposed
- Date: 2026-09-01
- Decision authority: Unassigned
- B1 applicability: Explicitly requested bounded implementation; not adopted policy

## Context

M18 proved a tiny project-owned image/annotation seam but could not test whether its
vector appearance transfers to real indoor images. M19 compared exactly GMU Kitchens,
HomebrewedDB, and YCB-Video under a no-download AND gate covering current rights,
acquisition, localization, identities, complete scoring, protected groups, small-target
verification, D1 translation, storage, and delivery cost.

GMU's author-cited dataset URL no longer exposes the dataset or current terms. HB and
YCB-V both pass through the current BOP institutional distribution. The frozen first
two tie-breaks remain tied; YCB-V wins the third because its annotated BOP'19 archive is
660 MB versus 2.35 GB for HB's smallest public annotated route.

## Decision

- Select only BOP's YCB-V BOP'19 subset for one bounded acquisition and translation
  slice.
- Acquire only the base and BOP'19 test archives from the official BOP Hugging Face
  repository; keep all source bytes ignored and outside Git.
- Preserve source scene, image, object, camera, license, URL, size, and computed hash
  provenance.
- Translate only the 21 modeled YCB classes. Ignore unmodeled objects, mark incomplete
  or deeply occluded cases unknown, and emit no relation or movement transition.
- Choose the local D1 target and frames with one frozen annotation-only, source-order
  rule before any model result exists.
- Stop before detector load, predictions, training, claim generation, or operation.

## Consequences

Positive:

- a compact real-image oracle can directly falsify synthetic-to-real detector gain;
- MIT terms, named household objects, 640×480 dimensions, public per-frame localization,
  and BOP's standard format reduce legal and adapter ambiguity;
- a 660 MB archive is practical for teammate reproduction without publishing its bytes.

Negative:

- the data is an arranged pose benchmark, not passive household movement;
- camera and scene statistics may differ substantially from a fixed webcam;
- a label-driven small-target slice can test the bucket but does not estimate natural
  household object prevalence;
- the current selection rests on published metadata until M20 verifies actual bytes.

## Revisit when

- M20 finds license, archive, annotation, size, hash, path, completeness, or small-target
  evidence inconsistent with the frozen result;
- a later fixed-camera real oracle passes an equally strict rights and completeness gate;
- the paired transfer experiment shows the selected slice cannot distinguish candidate
  behavior.

## M20 pre-extraction evidence

M20 verified both selected immutable archive identities, then stopped before extraction:
the base archive is rooted at `ycbv/`, while the test archive is rooted at `test/` for
extraction into an existing dataset directory. The frozen single-root contract therefore
failed as designed. This does not change the dataset selection or its thresholds. A
separate M21 proposal may repair only the per-archive source-to-destination mapping and
must prove collision safety before reusing the ignored local archives.

## M21 annotation-selection evidence

The sole per-archive mapping repair passed for the exact pinned archives. The unchanged
selector then found no same-object/same-scene pair with both the required small visible
positive and complete class-absent frame, so M21 stopped before RGB or D1 completion.
This closes the one materialization-repair authority. A bounded annotation-only
diagnostic may distinguish the two failed conjuncts, but it cannot make M21 pass or
authorize a changed source, threshold, or negative definition.

## M22 failure-localization evidence

The exact M21 target-frame scope contains 81 frozen-bucket positives and 14,775 safe
class-absent object/frame cases, but zero object/scene cells contain both. The failed M21
term is therefore same-scene pairing. Cross-scene pairing is not adopted by this finding:
its validity and comparability require a separate no-data/no-model decision gate before
any further materialization or detector experiment.

## M23 cross-scene validity evidence

The official BOP 2D evaluator filters target images within each scene, merges the
scene-level COCO annotations/results, and runs one COCO evaluation over the combined
image identities. The official COCO evaluator accumulates category TP/FP evidence over
those image identities. Together with the local M16 complete-frame and protected-group
contracts, this supports cross-scene positive/complete-absent pairing inside one
test-only diagnostic oracle. It does not support scene invariance, training on test,
movement, relations, physical truth, or whole-home transfer. M23 therefore selects only
an at-most-18-frame materialization proposal; all data/model work remains a later gate.

## M24 materialization evidence

The smallest source-ordered cross-scene pair materialized deterministically into an
ignored local M16 fixture: object 4 is positive at scene 50/image 620 and completely
absent at scene 48/image 1. The scenes remain separate sequences and no physical
identity or transition crosses them. The frozen visible-pixel predicate passes, but the
positive bbox occupies 3.043% of the frame, so M16 classifies it as `large_ge_1pct`.
This does not invalidate the bounded materialization result; it blocks a small-bbox
detector experiment until a separate annotation-only metric-alignment gate passes.
