# M36 checker Git-blob identity hardening

## Outcome

M36 passes its bounded implementation gate. The teammate checker now hashes the exact
`HEAD:uv.lock` Git-blob bytes for fatal version identity, while retaining exact revision
and clean-worktree checks. It reports three explicit fields:

- `uv_lock_git_blob_sha256` — committed version authority;
- `uv_lock_worktree_sha256` — checkout representation diagnostic;
- `uv_lock_worktree_representation_matches_git_blob` — whether raw bytes happen to
  match.

The ambiguous prior `uv_lock_sha256` field is removed. No non-Git fallback exists.

## Verification

Temporary local Git repositories establish that LF and Git-filtered CRLF worktrees share
one blob identity while their raw hashes differ; the CRLF checkout can remain clean.
Content tampering becomes dirty, the wrong blob hash is rejected, and a non-Git
directory fails instead of changing identity semantics.

Python 3.12.13 passed `12/12` focused tests and the complete M32 regression profile passed
`382/382`. The latter includes the existing pinned project-owned synthetic regression;
it is not a new M34 acceptance attempt. The public audit passed 295 files / 590
index-and-worktree snapshots with zero violations and `operate_enabled: false`. CI is
pending.

## Limits and compatibility

Only `tools/check_teammate_drill.py` changes outside tests/contracts. `.gitattributes`,
`uv.lock`, fixture, dependencies, product code, answer/trace semantics, and presentation
are unchanged. The checker receipt schema changes, but no stable external checker schema
had been promised. Source archives and installed wheels without Git remain unsupported.

M34 remains a normal STOP. M36 does not establish another platform or independent
teammate success, real-home transfer, CV gain, or operational authority. `OPERATE`
remains disabled.
