# M42 explicit uv cache-path preflight

## Outcome

M42 returns its frozen normal stop before the writability probe. In its sole no-build
attempt, uv 0.11.24 accepted the exact ignored repository-local path and returned that
same path with exit code 0 and no stderr. The command completed in `33.830 ms`.

`uv cache dir` did not create the requested directory. M42 required uv itself to perform
initialization, so the result is `CACHE_NOT_INITIALIZED`; the write probe was not allowed
to create the directory on uv's behalf.

## What this means

The attempt establishes only that the installed uv CLI accepts and reports the explicit
`--cache-dir` value under offline, no-config, and no-Python-download flags. It does not
establish that the target is unwritable. It also neither explains nor repairs M41's
separate default-cache error 183.

The checker forwarded only a small operating-system environment allowlist plus forced uv
offline settings. Proxy, index, token, and credential variables were not forwarded. No
OS-level network monitor was present, so zero network attempts are not claimed.

## Cleanup and limits

The target never existed. The empty ignored `.tmp` parent created for the attempt was
removed, and no cache or probe remains. No build, install, demo, dependency, product,
provider, media, device, action, or push occurred; `OPERATE` stayed disabled.

On result revision `a1c1de835a543747f006d01e8f8bc35de1022b4a`, all 13 M42
contract/checker/result tests and all 458 complete-regression tests passed in a Git-blob/
LF worktree; 39 existing optional-dependency tests were skipped. The Git-mode public
audit scanned 327 files / 654 index-and-worktree snapshots with zero violations. Public
CI was not run.

M42 is not a packaging authorization and may not be retried. A separate no-build gate
may decide whether the caller should create and probe an exact new cache directory before
passing it to uv. Such a gate must preserve the same path confinement, environment
sanitization, cleanup, and no-network claim limits.
