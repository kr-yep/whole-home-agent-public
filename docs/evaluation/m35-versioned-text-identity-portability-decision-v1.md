# M35 versioned-text identity portability decision

## Outcome

Candidate A, exact Git-blob SHA-256 plus an exact revision and clean worktree, is the
sole 8/8 selection. It uses the committed bytes as version authority while treating
working-tree EOL as checkout representation.

Canonical-LF working-tree hashing passes six gates but fails version authority and the
explicit-environment gate: it creates checker-derived bytes and a second fallback
identity. Raw working-tree hashing passes five gates and is directly falsified by M34.

## Evidence

M34 observed the same clean revision with `core.autocrlf=true`:

- Git blob: 571,954 bytes, 0 CRLF, SHA-256 `f2d363…`;
- Windows worktree: 574,709 bytes, 2,755 CRLF, SHA-256 `2cd58c…`;
- `uv sync --frozen`: success.

The current `.gitattributes` explicitly controls common source extensions but not
`uv.lock`. The drill checker already refuses the wrong Git revision or a dirty worktree,
so Git is not a new runtime assumption.

## Selected implementation boundary

M36 may change only the teammate checker and focused tests. It must hash
`git show HEAD:uv.lock`, keep exact revision and clean-worktree checks, fail without Git,
and expose committed-blob versus working-tree hashes as distinct receipt fields. The raw
worktree hash may remain diagnostic but cannot be the fatal version identity.

M36 may not edit `.gitattributes`, `uv.lock`, fixture, lock resolution, product code,
answer/trace semantics, or dependencies, and may not run clone/install/demo/acceptance.
M34 remains a normal STOP with no retry. `OPERATE` remains disabled.

Python 3.12.13 passed `7/7` focused M35 contract/result tests. The staged public audit
scanned 291 files / 582 index-and-worktree snapshots with zero violations and
`operate_enabled: false`. Public CI is pending.
