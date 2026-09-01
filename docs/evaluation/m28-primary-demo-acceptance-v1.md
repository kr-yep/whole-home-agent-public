# M28 primary demo acceptance and hardening

## Outcome

M28 returns the normal stop `STOP_M28_PRIMARY_DEMO_ACCEPTANCE`. The two frozen demo
interfaces ran offline with zero socket attempts and produced the same semantic SHA-256,
`18233bb9d86cc6ff3cdd3a8b7179ac8019e6dd90de790b4e215f49fcfa11936e`.
Source, governance, scoped answer, confirmation frames, warnings, diagnostics, and run
receipt were valid. Three frozen assertions failed.

Two were presentation gaps and are now hardened without changing semantics:

- perfect synthetic fixture metrics were top-level primary content;
- those metrics were not in a collapsed, strongly labeled optional section.

Revision `2d8bf868fa4c3bb2ee1d1332535b882bd0d45dbe` moves them into “Optional synthetic fixture metrics — not indoor
evidence,” adds an explicit no-accuracy/no-transfer caption, and adds a one-page judge
card with Windows/POSIX startup, compact CLI backup, recovery, and do-not-claim text.

The third failure is deliberately unresolved in this Goal. M28 froze evidence starts at
the manifest's source event labels (35 and 65), but the committed inference engine emits
claim evidence windows 33→37 and 66→68, with confirmation at 37 and 68. Source event,
inference lookback/stability window, and confirmation are different meanings. Changing
the expected values after seeing the acceptance output would silently rewrite the frozen
contract, so M28 stops instead.

## Exact attempt evidence

The contract was committed at `01b6bccba1475d956b7f72132fbf00318e6a7b48` before the run. The first checker execution
happened from that revision with an uncommitted checker, because invoking `--help`
before it had an argument parser accidentally executed the tool. This provenance is
recorded rather than relabeled as a clean committed run. It made exactly two internal
replays: direct public boundary and compact CLI, with run ID as the sole semantic
comparison exclusion. No third-party/private media or network was accessed.

| Check | Result |
|---|---|
| Source | `b1-key-bag-sofa@2`, 80 frames, pinned hash, CC0 |
| Governance | `D0_SYNTHETIC`, offline prerecorded, `OPERATE DISABLED`, no physical truth |
| Answer | `FOUND`, sofa, estimated, scoped, as-of 68 |
| Claims | `inside(key,bag)` at 37; `at_zone(bag,sofa)` at 68 |
| Interface determinism | Equal semantic document |
| Network attempts | 0 |
| Acceptance result | STOP on one trace-contract mismatch plus two UI gaps |

No second media acceptance attempt was run after hardening because M28 did not freeze a
retry or authorize post-observation changes to the trace assertion. Static regression
tests establish only that the two presentation failures are removed.

Python 3.12.13 passed all `299/299` tests, including `13/13` M28 contract,
helper, and result tests. The staged public-release audit scanned 258 files / 516
index-and-worktree snapshots with zero violations and `operate_enabled: false`.
[Public CI run 33516926134](https://github.com/kr-yep/whole-home-agent-public/actions/runs/33516926134)
succeeded for result revision `7d940c7fe8e4045746760d473ffe9923d8fac823`.

## Next authority

M29 may freeze a semantic correction that explicitly separates source event label,
engine evidence window, and confirmation frame using committed code plus this receipt.
It may then run exactly one acceptance retry with the committed checker. It cannot alter
presentation or relation semantics, use third-party/private media, load a new model,
predict, train, tune, connect live/cloud/action capability, or enable `OPERATE`.
