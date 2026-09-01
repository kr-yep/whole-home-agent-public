# M33 teammate clean-install demo drill

## Outcome

M33 returns the normal stop `STOP_M33_TEAMMATE_HANDOFF_DRILL` before dependency
installation. The one public clone completed at exact revision
`dc2b6fd2a51e8ea09ef199d7f4076ac74c9183b2` with a clean worktree in 1,607.584 ms.

The install preflight then observed:

```text
uv 0.11.24 (5e04460c0 2026-06-23 x86_64-pc-windows-msvc)
```

The outer PowerShell orchestration compared that entire string with `uv 0.11.24`.
Although the semantic version matches, the extra build metadata caused the preflight to
stop. `uv sync` never started, so dependency compatibility was not evaluated. The demo,
network guard, media decoding, structured-output check, and timing gate likewise never
ran.

## Evidence meaning

This is an `INSTALL / UV_VERSION_OUTPUT_FORMAT` harness failure, not evidence that the
repository cannot install, that dependencies are incompatible, or that the demo fails.
The frozen one-attempt limit prevents an unrecorded retry inside M33. The contract
revision itself passed [public CI run 33523229011](https://github.com/kr-yep/whole-home-agent-public/actions/runs/33523229011).

The disposable clone and its new empty uv cache were both removed after exact path
validation. They contained only recoverable public-repository/package-install staging;
no retained runtime artifact remains.

Python 3.12.13 passed all `9/9` focused M33 contract/result tests. The staged public
audit scanned 282 files / 564 index-and-worktree snapshots with zero violations and
`operate_enabled: false`. The result revision passed
[public CI run 33523965487](https://github.com/kr-yep/whole-home-agent-public/actions/runs/33523965487).

## What is usable and what is missing

The previously verified local/CI demo remains usable. M33 does not establish a new
teammate clean-install path because installation did not run. That item stays open.

M34 may authorize exactly one infrastructure retry whose only change is parsing the
semantic uv version token or accepted prefix. It must reuse the same repository
revision, lockfile, source fixture, expected answer/trace, time budgets, failure classes,
network boundary, cleanup, and no-second-retry rule. `OPERATE` remains disabled.
