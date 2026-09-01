# M34 teammate drill infrastructure retry

## Outcome

M34 returns `STOP_M34_TEAMMATE_HANDOFF_DRILL`, with no further retry allowed. The sole
uv-version parser repair worked, and the product path then completed mechanically:

- exact public clone: 1,612.715 ms, clean revision `dc2b6fd2…`;
- locked Python 3.12.13 install from a new empty cache: 7,059.658 ms, 40 packages;
- unchanged offline checker: 21,754.661 ms, zero network attempts;
- answer: `key / FOUND / sofa / estimated`, two evidence-backed claims, relation path
  `key → inside → bag → at_zone → sofa`, complete run receipt, `OPERATE DISABLED`;
- semantic SHA-256: `23d57ee4bb7c612c752f61369d5b18450532d24283bacc59b7683b0a2d35d322`.

The checker nevertheless stopped on its frozen `LOCK_OR_MANIFEST` gate. The manifest
matched; the lock identity did not.

## Failure localization

The repository's `uv.lock` Git blob is 571,954 LF bytes with SHA-256 `f2d363…`, exactly
the contract value. The Windows clean checkout used `core.autocrlf=true`, producing
574,709 bytes with 2,755 CRLF pairs and raw SHA-256 `2cd58c…`. `uv sync --frozen`
succeeded, so no lock resolution changed. The checker compared raw working-tree bytes
instead of a checkout-stable versioned-text identity.

This is a reproducibility-contract portability failure, not a demo, dependency, source,
answer, trace, network, or timing failure. It cannot be ignored because raw text hash
stability was a fatal gate.

## Cleanup and limits

The clone was removed normally. The uv cache contained one ACL-restricted editable wheel;
its first removal was partial, then the exact validated cache path was removed with
elevated filesystem permission. No runtime artifact remains.

This establishes one agent-run clean clone/install/offline demo on this Windows host. It
does not establish independent teammate usability, another platform, real-home transfer,
CV gain, or operational authority. M34 is not a PASS and may not be retried.

Python 3.12.13 passed `9/9` focused M34 contract/result tests. The staged public audit
scanned 286 files / 572 index-and-worktree snapshots with zero violations and
`operate_enabled: false`. Result CI is pending.

M35 may only select and harden a checkout-stable identity for versioned text, without an
acceptance/demo rerun or any product/fixture/lock semantic change. `OPERATE` remains
disabled.
