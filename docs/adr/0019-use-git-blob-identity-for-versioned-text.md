# ADR 0019: use Git-blob identity for versioned text in clone drills

**Status:** `PROPOSED — bounded M35 selection, not governance adoption`

## Context

M34's Windows clean checkout changed `uv.lock` LF bytes to CRLF under
`core.autocrlf=true`. The committed blob and dependency resolution remained exact, but
the checker compared raw checkout bytes and stopped.

## Proposed decision

For exact-Git-clone teammate drills, SHA-256 the `HEAD:uv.lock` Git blob and separately
require the expected revision and a clean worktree. Report the raw worktree hash only as
checkout-representation diagnostics. Fail closed when Git is unavailable.

## Alternatives

- Normalize worktree text to LF: portable, but creates checker-derived identity and an
  implicit fallback mode.
- Keep raw worktree hashing: simplest code but not stable under Git EOL filters.

## Consequences

Receipts distinguish version authority from checkout representation without changing
the lockfile, dependency resolution, or product. Archive/wheel-only environments are not
covered by this checker. M34 remains a normal STOP, and this ADR grants no demo retry,
data, model, action, or `OPERATE` authority.
