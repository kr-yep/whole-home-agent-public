# M24 minimal cross-scene YCB-V D1 materialization

## Verdict

`PASS_M24_MINIMAL_CROSS_SCENE_D1`, with one material metric-alignment gap.

The frozen two-frame materialization contract passed. The ignored local D1 contains
one source-ordered 0.1–1% visible-pixel positive and one complete class-absent negative
for the same modeled class from distinct YCB-V test scenes. It is a valid M16 fixture
with two separate source sequences, not a cross-scene physical timeline.

It is **not yet a small-bbox detector oracle**. The selected positive is small by visible
mask pixels (`0.5107%`) but its visible bounding box occupies `3.0430%` of the image, so
the current M16 evaluator assigns it to `large_ge_1pct`. That mismatch must be resolved
before any detector prediction or transfer-gain experiment.

## Precommitted sequence

1. Commit `4e0be76ddd64def94f47b4bbb733dd200671ba42` froze the source,
   archive reuse, exact two-frame selection, cross-scene identity, D1 mapping, two-run
   determinism, M16 shape, stopping rules, and prohibitions before archive reread.
2. Commit `5a8c42f` added the pure cross-scene selector, explicit M16 public-test
   use-class boundary, deterministic local writer, and synthetic tests before real data.
3. Commit `5f15d0c` fixed direct-script import startup and passed its regression before
   the one real materialization run.
4. The run reverified both pinned archives and every ZIP header, read only the 37
   allowlisted annotation JSON members and two selected RGB members, produced two clean
   byte-identical outputs, retained one ignored output, and removed staging.

## Exact selected pair

| Role | Class | Scene / image | Reference evidence | Local representation |
|---|---|---|---|---|
| Positive | `005_tomato_soup_can` (BOP ID 4) | 50 / 620 | bbox `[396, 158, 472, 281]`, visible pixels 0.5107%, visibility 16.64% | source sequence 50, local frame 0, one scene-scoped instance |
| Complete class-absent negative | same modeled class | 48 / 1 | no ID 4 in the complete modeled-object annotation rows | source sequence 48, local frame 0, zero instances |

The two scenes remain separate protected source groups. The negative does not fabricate
an absent physical instance, and no reference transition or relation is emitted.

## Source and output evidence

- both archive sizes and SHA-256 values matched M20/M21;
- all 10,092 headers and 671,106,741 uncompressed bytes passed inherited archive and
  mapped-namespace guards;
- the source scope remained 900 target frames in scenes 48–59;
- two clean generations produced the same four relative file hashes;
- the local output totals 1,041,911 bytes and is ignored by `data/external/`;
- Git records only sanitized identities, aggregates, boxes, and hashes—not RGB or raw
  annotation rows.

The canonical relative-file manifest SHA-256 is
`02bcc544798e495f3fb5b3f6e743b860a689b4cfe66d447f3a09eb176bb5f096`.

## M16 evidence and the discovered mismatch

The explicit test-only loader accepted the generated fixture while the default loader
continued to reject it, preserving synthetic-only behavior for existing callers. Empty
predictions produced two evaluated frames, one negative, one scorable target, zero
false positives, zero transitions, and zero recall as expected.

However, M16 assigns size using bounding-box area. The selected box is `76 × 123`, or
`9,348 / 307,200 = 3.04296875%`; therefore the report contains zero
`small_0.1_to_1pct` targets and one `large_ge_1pct` target. M24 does not retroactively
change its frozen visible-pixel predicate, so materialization mechanics pass, but the
result cannot support a small-object detector comparison.

## What did not occur

- dataset/model download, network access, bulk extraction, depth or mask read;
- source bytes, RGB, or raw annotations added to Git;
- model/detector/tracker load, prediction, training, threshold selection, or test tuning;
- VOST/VISOR/reserved-source read;
- movement candidate, claim, relation, live/private sensing, cloud call, device action,
  or `OPERATE` enablement.

## Claim ledger

| Claim | Evidence | Permissible wording | Unsupported extension |
|---|---|---|---|
| M24-C1 | Pinned archive and header receipts | The exact source archives remained intact and safely mapped | The captures are complete physical truth |
| M24-C2 | Two clean output manifests | The local four-file D1 output is deterministic for these bytes | Another platform or source version is identical |
| M24-C3 | M16 fixture/report | Two separate test sequences score one positive and one negative | The scenes form a movement sequence |
| M24-C4 | Visible-pixel annotation | The target passes the frozen 0.1–1% visible-pixel predicate | It is small under M16 bbox-area metrics |
| M24-C5 | M16 size counts | The selected bbox is in M16's ≥1% bucket | No other YCB-V positive can satisfy both definitions |

## Next gate

M25 should freeze an annotation-only dual-area diagnostic before rereading the same 37
members. It may decide whether any source-ordered class has both a distinct-scene safe
negative and a positive that is 0.1–1% under **both** visible-pixel and M16 bbox area.
It must read no RGB, load no model, and either select an exact replacement pair or stop
the YCB-V small-object oracle direction. No detector run is currently authorized.
