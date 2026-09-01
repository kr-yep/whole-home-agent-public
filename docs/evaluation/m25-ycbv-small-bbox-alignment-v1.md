# M25 YCB-V small-bbox metric alignment

## Outcome

M25 returns `SELECT_DUAL_AREA_CROSS_SCENE_PAIR` within the frozen annotation-only
envelope. The exact source contains two frames, across two modeled classes, whose same
annotation is 0.1% (inclusive) to 1% (exclusive) under both visible-pixel area and M16
visible-bbox area. The source-ordered choice is object 4 (`005_tomato_soup_can`) at
scene 50/image 722, paired only for detector scoring with a complete class-absent frame
at scene 48/image 1.

This selects one exact replacement-materialization contract. It is not a detector,
training, transfer-gain, movement, relation, prevalence, fixed-camera, or whole-home
result.

## Precommitted method

The contract was committed at `73af8ffc73a74c9f69b3b7b9fda9e96028592f0a`
before any real annotation reread. The pure implementation and synthetic SELECT/STOP,
boundary, source-order, identity-conflict, and no-media tests were committed at
`5bbf39efc43bd3f5ab944f369b0016acc25b6d8b` before the one permitted read.

The run reused the exact M21 archives, immutable source revision, 4,123 target entries,
900 unique frames, 12 scenes, and 37 JSON members. It read members directly from ZIP,
parsed the complete frame contract, ran the pure diagnostic twice over the same
in-memory values, and required byte-identical canonical output. It read no RGB, depth,
mask, VOST, VISOR, reserved media, model, or prediction.

The positive predicate requires, on the same annotation:

- visibility fraction at least 0.10;
- `0.001 <= px_count_visib / 307200 < 0.01`;
- `0.001 <= bbox_visib_width * bbox_visib_height / 307200 < 0.01`;
- a positive, in-frame visible bbox.

The negative must be a complete frame in a different scene with the selected modeled
class absent. Object, positive, and negative ordering were fixed before observation.

## Evidence

| Measure | Result |
|---|---:|
| Target frames | 900 |
| Pixel-small positive frames | 81 |
| Bbox-small positive frames | 2 |
| Same-annotation dual-area positives | 2 |
| Classes with dual-area positives and a distinct-scene safe negative | 2 |
| Complete class-absent object/frame cases | 14,775 |
| Annotation reads | 1 |
| Pure runs over the in-memory parse | 2, byte-identical |

The selected positive has `bbox_visib=[473,161,22,129]`, visible-pixel area
`0.005660807291666667`, bbox area `0.00923828125`, and visibility
`0.17551473556721842`. The second eligible class is object 18 (`040_large_marker`) at
scene 59/image 164. Object 17 (`037_scissors`) contributes two pixel-small annotations
but no bbox-small annotation.

## Evidence-bounded claim ledger

| Claim | Evidence permits | Evidence does not permit |
|---|---|---|
| Source identity | These two pinned archives and this source revision matched the frozen hashes | Capture authenticity or household representativeness |
| Dual-area count | Two parsed reference annotations satisfy both exact predicates | Detector recall, AP, or a transfer gain |
| Selected pair | The deterministic rule selects the recorded positive and complete-absent negative | A physical object transition or cross-scene identity |
| Next work | One exact two-RGB replacement materialization may be separately frozen | Adaptive frame selection, model work, or test tuning |

## Adversarial pass and limits

No independent reviewer was available in this execution, so the challenge pass is
explicitly non-independent. The selected box is narrow and elongated, the object is
partially visible, `bbox_visib` is a rectangle rather than exact mask support, and one
positive plus one negative has essentially no statistical power for a stable gain
claim. Selection is also label-driven construction on a test-only source. These are
fatal to performance, generalization, natural-prevalence, and movement claims, but not
to the narrow mechanical question of whether the M16 small bucket can be populated.

M26 must freeze the exact two RGB members before reading either one, retain separate
scene sequences and zero transitions, and prove exactly one M16 small-bbox target. It
must stop on any identity, completeness, mapping, hash, determinism, or metric mismatch.
No result here authorizes prediction, training, test tuning, candidate/claim emission,
live/private/cloud access, physical action, or `OPERATE`.

## Verification

Python 3.12.13 passed all `262/262` tests, including 19 M25 contract, synthetic,
failure, and result checks. The staged public-release audit scanned 242 files / 484
index-and-worktree snapshots with zero violations and `operate_enabled: false`. These
checks support only the code, frozen source-envelope handling, and recorded result.
Public CI independently reran the repository workflow successfully on clean result
revision `e9185da4132265e2bccba8fd4c67cdd965b5e6bb` in
[run 33512733734](https://github.com/kr-yep/whole-home-agent-public/actions/runs/33512733734).
