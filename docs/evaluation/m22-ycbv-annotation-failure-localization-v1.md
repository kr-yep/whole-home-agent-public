# M22 YCB-V annotation-only failure localization

## Verdict

`STOP_YCBV_PAIRING_SCOPE_TERM`.

The frozen 900-frame BOP'19 scope contains both required ingredients, but not under the
same object/scene key:

- 81 frames satisfy the unchanged 0.1–1% visible-target predicate;
- 14,775 object/frame cases satisfy the unchanged complete modeled-class-absent
  predicate;
- zero object/scene keys contain both.

M21 therefore failed because its same-scene pairing constraint was too restrictive for
this source structure—not because YCB-V lacks small targets or safe negatives. This
diagnosis does not itself authorize cross-scene pairing.

## Precommitted evidence sequence

1. Commit `41e02477d7830637fa1da2234b6231ec074e05f8` froze the exact M21 source,
   900-frame scope, predicates, completeness checks, branch priority, and prohibitions
   before any annotation reread.
2. Commit `11f083e7940dab3c6b2a5ce4f36f60b91f8bb9dd` added one shared strict BOP
   parser, a pure four-branch diagnostic, direct allowlisted ZIP-member reads, and 12
   synthetic tests before the first real run.
3. The first real run returned source-invalid because the tool passed contract-listed
   members positionally as camera/GT/info to a parser expecting GT/info/camera. This was
   an implementation wiring failure; it established nothing about source validity.
4. Commit `c169693d5ff99b94066fccd5f4465be4edccfa5f` mapped documents by semantic
   filename and added a regression test before one infrastructure retry.
5. The retry verified both source hashes, read only 37 allowlisted JSON members directly
   from ZIP, validated all 900 frames through the shared parser, and ran the pure
   diagnostic twice with byte-identical output.

## Positive evidence

| Object | Positive frames | Scenes | First source-ordered evidence |
|---|---:|---|---|
| `005_tomato_soup_can` | 21 | 50 | scene 50, image 620, area 0.5107%, visibility 16.64% |
| `037_scissors` | 2 | 51 | scene 51, image 1528, area 0.9974%, visibility 54.88% |
| `040_large_marker` | 58 | 57 (40), 59 (18) | scene 57, image 1, area 0.7142%, visibility 97.82% |

All values are derived from the pinned public `scene_gt_info` rows using the exact M21
predicate. They are annotation evidence, not observed detector performance or household
transfer evidence.

## Negative and pairing evidence

All 21 modeled object classes have at least one complete class-absent frame. Across 900
frames this yields 14,775 object/frame negatives in 197 object/scene cells. For each of
the four positive object/scene cells, however, that object appears in every target frame
of the scene; its safe negatives occur only in other scenes. The paired cell count is
therefore exactly zero, reproducing M21 without contradiction.

## Why this changes the decision, but not the rule

The data direction should not be discarded for “no small objects”: that statement is
false under the frozen predicate. It also should not be advanced by quietly taking a
negative from another scene. Whether cross-scene positives and negatives form a valid
detector-transfer oracle depends on the intended metric, source-group semantics, and
comparison protocol. That is a material evaluation decision and belongs in a separate
reality gate.

## What did not occur

- archive download, extraction, RGB/depth/mask or non-allowlisted member read;
- M21 materialization retry, D1 generation, threshold/predicate change;
- model, detector, tracker, prediction, training, test tuning;
- VOST/VISOR/reserved source, movement candidate, claim, relation, live/private sensing,
  cloud inference, action, or `OPERATE`.

## Claim ledger

| Claim | Evidence | Permissible wording | Unsupported extension |
|---|---|---|---|
| M22-C1 | Shared strict parser over 900 target frames | Both predicate terms occur in the pinned scope | Every annotation is physically true |
| M22-C2 | 81 positive counts and first examples | YCB-V has frozen-bucket small-object annotation cases | A detector can detect them |
| M22-C3 | 14,775 complete absent cases | Safe class-absent negatives exist in other scenes | Cross-scene pairing is automatically valid |
| M22-C4 | Zero paired object/scene cells | Same-scene scope is the failed M21 term | Same-scene scope was scientifically wrong |
| M22-C5 | Two byte-identical diagnostic runs | This implementation is deterministic on the pinned input | Results generalize to other archives or versions |

## Next gate

M23 should be a no-data, no-model reality gate. It must compare the existing M16
complete-frame metric semantics with authoritative object-detection evaluation practice
and decide whether a protected cross-scene test-only slice is scientifically comparable.
Until that decision is separately adopted, M21 remains stopped and no D1 materialization
or detector experiment is authorized.
