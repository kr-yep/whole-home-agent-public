# M29 primary demo acceptance retry

## Outcome

M29 returns the normal stop `STOP_M29_PRIMARY_DEMO_ACCEPTANCE_RETRY`. The one
precommitted retry ran from clean checker revision
`714a0fdcc6f8ba3db6ce00bd471754da4dd6d760`, made exactly two internal offline
replays, attempted no socket connection, and produced equal semantic output with
SHA-256 `18233bb9d86cc6ff3cdd3a8b7179ac8019e6dd90de790b4e215f49fcfa11936e`.

The M28 timing mismatch is resolved by meaning, not by changing runtime behavior:

| Relation | Source event label | Engine evidence window | Claim confirmation |
|---|---:|---:|---:|
| `inside(key, bag)` | 35 | 33→37 | 37 |
| `at_zone(bag, sofa)` | 65 | 66→68 | 68 |

Every frozen check passed except `SCOPED_ANSWER`. The returned answer is `FOUND sofa`,
estimated, scoped to `source:b1-key-bag-sofa@2`, as-of 68, and carries the two-claim
relation path. The public answer object does not itself include the expected
`subject_id: key`; `key` appears only in the relation path and fixed presentation
context. That exact output-contract mismatch stops M29.

## Evidence boundary

This does not establish a detector, relation-engine, or demo-runtime failure. It also
does not establish general language understanding, real-home accuracy, or transfer.
M27's primary-demo selection and M28's presentation hardening remain intact. The
committed project-owned D0 synthetic source was the only media read; no third-party or
private media, new model, prediction experiment, training, tuning, live/cloud/action
connection, or operation occurred.

Python 3.12.13 passed all `314/314` tests, including `15/15` M29 contract,
checker, and result tests. The staged public-release audit scanned 262 files / 524
index-and-worktree snapshots with zero violations and `operate_enabled: false`.
[Public CI run 33518077833](https://github.com/kr-yep/whole-home-agent-public/actions/runs/33518077833)
succeeded for result revision `e68f1cbe6667c49ad85c6040787f31f134288ff0`.

M29 authorizes no second acceptance retry. M30 may perform only a repository-based,
no-media decision on whether the public answer schema must expose query-subject
identity and, if so, at which existing boundary. It may not change code or presentation
until that decision is separately frozen.
