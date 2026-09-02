# M43 caller-created uv cache semantics

## Outcome

M43 passes its bounded no-build gate. The correct responsibility split on this Windows
host is:

```text
closed preflight creates exact new ignored directory
  → exclusive fsync write/read/delete probe
  → uv confirms the selected existing path
  → non-recursive removal proves the directory stayed empty
```

The probe SHA-256 was
`fa1c6fde2dad49408d7d605ee73397ab22ca09d5c12898fc0ce52750cdbc87ae`.
uv 0.11.24 returned the exact path with exit code 0, no stderr, and `38.287 ms`
elapsed. The probe was removed before uv ran; uv left no entry; the checker removed the
target with non-recursive `rmdir`, and the outer harness removed the empty parent.

## Preserved pre-attempt launch failure

The first direct script launch at contract revision `9464c0c…` failed before the cache
attempt because the checker imported a sibling through a package path available to tests
but not to direct script execution. No target, probe, or uv process existed, so it did
not consume the one cache attempt. Revision `b86e2c0…` made the checker self-contained
and added a subprocess regression that launches `--help` outside the repository without
`PYTHONPATH`. This harness repair is retained rather than erased from the result.

## Evidence limits

The CLI ran with offline, no-config, no-Python-download settings and a small environment
allowlist; proxy, index, token, and credential variables were not forwarded. No OS-level
network monitor was present, so zero network attempts are not claimed.

This pass proves only directory ownership, local write/read/delete, uv path selection,
and cleanup on this host. It neither explains nor repairs M41's default-cache failure,
and it does not establish dependency-cache completeness, package build/install/demo,
teammate usability, or public CI. No product, dependency, provider, media, device,
action, or push occurred; `OPERATE` stayed disabled.

On result revision `94edd34cf05314d3515b27d3c33a8c6d91c2e8d1`, all 13 M43
contract/checker/result tests and all 471 complete-regression tests passed in a Git-blob/
LF worktree; 39 existing optional-dependency tests were skipped. The Git-mode public
audit scanned 333 files / 666 index-and-worktree snapshots with zero violations. Public
CI was not run.

M43 authorizes only preparation of a separately frozen M44 packaging gate that uses an
explicit caller-created cache. It does not itself authorize a package attempt or push.
