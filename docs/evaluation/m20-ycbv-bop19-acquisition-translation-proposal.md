# M20 YCB-V BOP'19 acquisition and D1 translation proposal

## Purpose

Verify the actual bytes behind M19's selected route and materialize one local real-image
D1 transfer slice without loading a detector. This is an acquisition, integrity, and
translation gate—not a training or accuracy experiment.

## Frozen source scope

- repository: `bop-benchmark/ycbv` on the BOP Hugging Face organization;
- archives: exactly `ycbv_base.zip` and `ycbv_test_bop19.zip`;
- displayed pre-acquisition sizes: 15.8 kB and 660 MB;
- expected dataset terms: MIT, confirmed again from the author toolbox and acquired
  metadata;
- local destination: an explicit ignored public-data directory under `data/`;
- no original 265 GB corpus, models archive, real/synthetic training archive, PBR data,
  other BOP dataset, account, mirror, or private source.

## Pre-model gates

1. Resolve immutable source revision metadata and record URLs, sizes, SHA-256 hashes,
   acquisition time, and license evidence.
2. Inspect ZIP members before extraction; reject absolute paths, drive prefixes,
   traversal, links, duplicates, unexpected roots, encrypted members, or size expansion
   beyond the frozen bound.
3. Confirm public ground truth, RGB frames, 640×480 dimensions, object IDs, visible/amodal
   boxes or masks, pixel counts, scene/image IDs, and the BOP'19 target list.
4. Implement the BOP-to-M16 translator against small synthetic BOP-format contract
   fixtures before reading real annotations through it.
5. Apply one deterministic source-order rule: choose the lowest object ID and then the
   lowest scene ID for which the complete BOP'19 source contains both a visible target
   with area fraction in `[0.001, 0.01]` and a complete frame where that selected class
   is absent. Select the smallest source-ordered frame set that proves both cases, up to
   18 frames; stop if no such set exists.
6. Put the complete slice in the project `test` split, preserve original IDs in a local
   manifest, renumber only D1 frame indexes, mark visibility below the declared BOP
   threshold unknown/unscored, ignore unmodeled objects, and emit zero transitions.
7. Run exact D1 validation twice and prove a regenerated local manifest is identical.

## Pass decision

Pass only when the two source archives are lawful, public, hash-pinned, safely extracted,
within 5 GiB, and translated into a complete local D1 slice with at least one 0.1–1%
positive and one class-scoped negative in no more than eight working hours.

Passing authorizes only the design of a paired no-training transfer experiment. It does
not authorize loading a detector in M20.

## Stop conditions

Stop normally on source or license drift, login/application requirements, unsafe archive
structure, missing ground truth, incomplete class-scoped negatives, missing small targets,
size or time overrun, translator non-conformance, or nondeterministic output. Do not
substitute HB, a mirror, a larger archive, a different target rule, or a relaxed bucket
inside the same Goal.

## Boundaries

All downloaded and extracted source bytes remain ignored and uncommitted. No model,
prediction, tracker, training, test tuning, MovementCandidate, ClaimCandidate,
AcceptedClaim, relation assertion, live/private sensing, cloud inference, external
action, or `OPERATE` enablement is allowed.
