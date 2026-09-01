# M20 YCB-V BOP'19 acquisition and D1 translation gate

## Verdict

`STOP_YCBV_REAL_TRANSFER_ORACLE_MATERIALIZATION`, with normal fail-closed
completion.

Both selected archives were downloaded from the immutable BOP Hugging Face revision and
matched the exact frozen byte counts and SHA-256 values. Materialization then stopped
before extraction because the test archive uses top-level `test/`, while the frozen M20
contract required every archive to use top-level `ycbv/`.

This is an infrastructure-contract mismatch, not evidence that the archives are corrupt
or that YCB-Video is unsuitable. M20 cannot repair the rule after seeing the archive
headers because unexpected roots were an explicit stop condition. No real annotation,
RGB frame, model, prediction, or D1 translation was read or run.

## Evidence sequence

1. Commit `2a69db3` froze the immutable source revision, archive identities, single-root
   rule, cost limits, D1 semantics, and stop branch before download.
2. Commit `769c2ae` implemented the safe ZIP preflight and BOP-to-D1 adapter. The
   committed synthetic BOP fixture passed exact positive, negative, source-order,
   dimension, deterministic-output, and zero-relation tests before real data access.
3. The official archives were downloaded once into the Git-ignored local root.
4. Both archives passed size and SHA-256 checks.
5. `ycbv_base.zip` passed header preflight with top-level `ycbv/`.
6. `ycbv_test_bop19.zip` exposed top-level `test/`; preflight returned
   `UNEXPECTED_TOP_LEVEL_ROOT` and stopped before extraction.

## Verified archive identity

| Archive | Bytes | SHA-256 | Observed root | M20 preflight |
|---|---:|---|---|---|
| `ycbv_base.zip` | 15,805 | `98440f8bd403100b21cf11a6729fabe8b3d5ce714472edc57a18b7f1fcd4bb18` | `ycbv/` | PASS |
| `ycbv_test_bop19.zip` | 660,198,701 | `c0c11251849877e7b2f373f6c7acf54739dc69d0fb2649c20050ca977bf5513d` | `test/` | FAIL against frozen root |

Both belong to source revision
`5c2c4aa229800355648cd268040aa814f8dc94f0`. These values establish local byte
identity with the M20 source contract. They do not establish capture authenticity,
annotation truth, or dataset fitness.

## Why the contract was wrong

The base archive is self-rooted as `ycbv/...`; the test archive is packaged for
extraction into an already selected dataset directory and begins at `test/...`. M20
incorrectly represented an extraction destination rule as a source-member invariant.

Changing the rule in place would make a result-dependent contract edit. The bounded
repair is instead a new gate that freezes per-archive source roots and an explicit
destination mapping before trying extraction. Every content, license, size, hash,
selection, scoring, and safety threshold remains unchanged.

## What was not reached

- ZIP member extraction: zero files;
- real `test_targets_bop19.json` or scene JSON reads: zero;
- real PNG header or image reads: zero;
- small-target and class-absence check: not run;
- real D1 slice and repeated translation: not run;
- detector, tracker, prediction, training, test tuning, relation, movement candidate,
  semantic claim, live/private source, cloud inference, action, or `OPERATE`: not used.

The two verified local archives remain ignored and uncommitted so a separately frozen
repair can reuse them without a second download.

## Verification

On clean result revision `ff4368eba2651f1a7aa182039c40197b1bbdf738`, Python
3.12.13 passed all `188/188` tests. The public-release audit scanned 218 tracked files
and 436 index/worktree snapshots with zero violations and `operate_enabled: false`.
The M20-focused module contributed 15 passing contract, synthetic-translation,
archive-safety, and stopped-result tests. These checks support only the bounded software
and release claims above; they do not validate unexamined dataset contents.

## Claim ledger

| Claim | Evidence | Permissible wording | Unsupported extension |
|---|---|---|---|
| M20-C1 | Exact local bytes and frozen metadata | Both archives match the selected immutable source identity | The dataset annotations are true or complete |
| M20-C2 | ZIP central-directory headers | Base uses `ycbv/`; test uses `test/` | Either source is unsafe or corrupt |
| M20-C3 | Frozen stop rule and execution stage | M20 stopped before extraction on a contract mismatch | YCB-V failed the small-target or D1 gate |
| M20-C4 | Committed synthetic tests | The translator and archive guards satisfy their synthetic contract | They have processed the real archive successfully |
| M20-C5 | Bounded next proposal | A per-archive root-mapping repair is justified | Threshold, source, license, or dataset substitution is allowed |

## Next gate

M21 may change exactly one infrastructure assumption: freeze `ycbv/` as the base source
root, `test/` as the test source root, and prepend `ycbv/` only when mapping test members
to the ignored extraction destination. It must test cross-archive destination collision
and escape behavior synthetically before reusing the already verified archives. All
source identities, cost limits, selection rules, small-target range, negative/unknown
semantics, zero-relation rule, and model/training/claim/operation prohibitions remain
unchanged.
