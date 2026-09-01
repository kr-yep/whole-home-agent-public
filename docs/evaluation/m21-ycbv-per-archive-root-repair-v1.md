# M21 YCB-V per-archive root repair and translation gate

## Verdict

`STOP_YCBV_REAL_TRANSFER_ORACLE_AFTER_SINGLE_ROOT_REPAIR`, with normal fail-closed
completion.

The sole M21 infrastructure repair worked: both pinned local archives passed exact byte
identity, every ZIP header passed the frozen safety limits, and mapping `ycbv/` to
`ycbv/` plus `test/` to `ycbv/test/` produced one collision-free destination namespace.
The run then stopped at the first scientific gate. The unchanged annotation-only
selector found no object/scene pair that contained both a 0.1–1% visible-area positive
and a complete frame in which that selected class was absent.

No RGB member was extracted or read, no D1 slice was completed, and no threshold or
selection rule was changed after observing the result.

## Evidence sequence

1. Commit `07f498341c55ae65836bbf6c84b100f7f0566c20` froze the sole per-archive
   mapping change before archive reuse, extraction, or real annotation access.
2. Commit `5164634ec419f3547996001f45d4aac1978acff7` added the no-network mapper,
   full destination-namespace preflight, metadata-first selective extraction, and
   synthetic two-archive tests before real archive reuse.
3. Both ignored M20 archives again matched their exact pinned sizes and SHA-256 values.
4. Header preflight covered 10,092 members and 671,106,741 uncompressed bytes; both
   source-root mappings and the combined destination namespace passed.
5. The tool transiently extracted one target list and three scene JSON files for each of
   12 target scenes. It read the 4,123 target rows covering 900 unique frames.
6. The unchanged selector returned `NO_FROZEN_SLICE`; the staging tree was removed and
   the ignored M21 output root contains zero files and zero subdirectories.

## Archive and source structure

| Archive | Members | Uncompressed bytes | Mapping | Result |
|---|---:|---:|---|---|
| `ycbv_base.zip` | 5 | 271,812 | `ycbv/` → `ycbv/` | PASS |
| `ycbv_test_bop19.zip` | 10,087 | 670,834,929 | `test/` → `ycbv/test/` | PASS |

The source target list covers scenes 48–59. These counts establish only the structure
read by the frozen gate. They do not establish annotation truth, capture authenticity,
or fitness for another evaluation protocol.

## Exact evidence boundary

M21 evaluated a conjunction. Its failure establishes that no same-object, same-scene
pair satisfies both terms under the frozen BOP'19 target-frame scope. It does **not**
establish which term failed independently. In particular, M21 does not support the
stronger statements that YCB-V contains no 0.1–1% targets, that it has no usable absent
frames under any other lawful protocol, or that a detector cannot benefit from it.

Separately diagnosing those terms is useful, but doing so cannot retroactively turn M21
into a pass or authorize a changed negative definition.

## Verification

On clean result revision `5da866ce90b57baf77bb22d1eb040fbab5e20bad`, Python
3.12.13 passed all `203/203` tests. The M21-focused module contributed 15 passing
contract, mapping, safety, selective-extraction, and stopped-result tests. The public
release audit scanned 222 tracked files and 444 index/worktree snapshots with zero
violations and `operate_enabled: false`. These checks support only the bounded software,
execution, and release claims above.

## What did not occur

- archive download or alternate mirror/source use in M21;
- persistent extraction, committed source bytes, or redistribution;
- RGB, depth, mask, detector, tracker, prediction, training, or test tuning;
- D1 completion, relation, transition, movement candidate, semantic claim, live/private
  sensing, cloud inference, action, or `OPERATE`.

## Claim ledger

| Claim | Evidence | Permissible wording | Unsupported extension |
|---|---|---|---|
| M21-C1 | Exact hashes plus ZIP preflight | The one root-mapping repair matches these pinned archives | Arbitrary BOP archives are safe |
| M21-C2 | Combined namespace validation | The mapped destination has no detected collision or path conflict | The scientific slice passes |
| M21-C3 | Frozen selector result | No pair satisfies the combined M21 predicate | Neither predicate term ever occurs |
| M21-C4 | Empty ignored output root | Failed staging left no persistent extracted/derived file | No annotation bytes were transiently read |
| M21-C5 | Frozen prohibitions and execution trace | M21 used no model, prediction, training, claim, or operation | YCB-V detector transfer has been tested |

## Next gate

M22 may perform one annotation-only failure localization over the same 900 pinned public
target frames. It may report the positive and negative conjuncts separately using the
unchanged M21 definitions. It may not download another source, read RGB, retry
materialization, change a threshold or negative definition, run a model, or promote a
diagnostic into transfer evidence. Its output is a bounded decision about whether the
real-oracle direction should stop or require a separately governed data decision.
