# M26 exact YCB-V dual-area replacement D1

## Outcome

M26 returns `PASS_M26_DUAL_AREA_REPLACEMENT_D1`. The exact M25 pair materialized into
four ignored local files twice with byte-identical relative file records. M16 now counts
the sole reference target in `small_0.1_to_1pct`, with zero tiny and zero large targets.

This repairs the metric alignment of a two-frame test-only fixture. No model was loaded,
no prediction was made, and the result says nothing about recall, AP, transfer gain,
movement, relations, or whole-home value.

## Frozen execution

The exact pair contract was committed at
`f475ad0b077d8838ad0bab4680ad72b2a0010ffc`. A synthetic test then found that a newly
invented use-class would violate M16's closed allowlist. Before any source read, M26
reused the existing `TEST_ONLY_MINIMAL_DETECTOR_TRANSFER_ORACLE` class and recorded the
non-semantic vocabulary fix at `ac4b0a649179a4cbc721d61439e11f486a058d6f`.
Frame identities, annotations, thresholds, and branches did not change. The exact-pair
selector and reused materialization primitives were committed at
`75db4457bcd466f5d41dc3cbffeb727e035888d7` before the only real source pass.

That pass reverified both archive hashes, all 10,092 headers / 671,106,741 uncompressed
bytes, and the mapped namespace. It parsed the same 4,123 target entries / 900 frames /
37 JSON members, rejected any deviation from the exact M25 annotation, then read only:

- `test/000050/rgb/000722.png`;
- `test/000048/rgb/000001.png`.

It produced two clean staging trees, compared their four relative file records, loaded
the first oracle through the closed M16 test-use boundary, removed the second staging
tree, and atomically retained one ignored output plus receipt. No partial staging path
remained.

## Result

| Check | Result |
|---|---:|
| Evaluated frames | 2 |
| Complete class-absent negative frames | 1 |
| Scorable targets | 1 |
| M16 tiny targets | 0 |
| M16 small targets | 1 |
| M16 large targets | 0 |
| Reference transitions | 0 |
| Clean materializations | 2, byte-identical |
| Persisted ignored files | 4 files / 1,066,049 bytes |

The positive is object 4 at scene 50/image 722 with bbox
`[473,161,495,290]`, bbox area `0.00923828125`, visible-pixel area
`0.005660807291666667`, and RGB SHA-256
`6bd47f202771e7fc4f2879f2a2e9c63f8ffcead08f937f7ed930c3766174b64b`.
The negative remains scene 48/image 1. Each scene is a separate source sequence; no
cross-scene instance identity or transition exists.

## Claim ledger and next boundary

The evidence establishes only deterministic materialization and the M16 size-bucket
classification for these exact bytes. A single positive and negative cannot estimate
a stable model gain, support bootstrap inference, or represent natural home prevalence.
Label-driven test construction cannot become training or tuning data.

M27 may only design the no-model demo/evaluation contract: keep this two-frame oracle as
a mechanical smoke, state what a future development set and untouched frozen test would
need, and decide the smallest judge-visible story. It may not read media, load a model,
predict, train, tune, create candidates/claims/relations, or enable live/private/cloud/
action capability. `OPERATE` remains disabled.

## Verification

Python 3.12.13 passed all `276/276` tests, including 14 M26 contract, exact-drift,
materialization, M16 metric, direct-startup, and result tests. The staged public-release
audit scanned 247 files / 494 index-and-worktree snapshots with zero violations and
`operate_enabled: false`. This verifies only the declared software and fixture envelope.
