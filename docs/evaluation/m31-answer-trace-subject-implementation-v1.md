# M31 answer-trace subject implementation

## Outcome

The bounded implementation is mechanically correct, but M31 returns the normal stop
`STOP_M31_ANSWER_SUBJECT_IMPLEMENTATION` because its own verification constraints were
contradictory.

The additive implementation at
`5c08ea65154cc607c510c5eb65b16657632fd769` does exactly four production edits:

- required immutable `AnswerTrace.subject_id`;
- the sole `_trace` constructor copies `QueryRequest.subject_id`;
- B0 CLI answer serialization exposes it;
- B1 public-demo answer serialization exposes it.

FOUND, UNKNOWN, CONFLICT, SCOPE_REQUIRED, OUT_OF_SCOPE, and FRONTIER_MISMATCH all retain
the exact requested subject, including empty-path non-FOUND answers. No existing answer
field was removed or renamed. The frozen B0 session semantic SHA-256 remains
`226d30a5b826720d607d0b9a29bf3dfb9f5429eeedbbd70ffd1ff23c21233c8f`;
accepted claim IDs and projection frontier remain unchanged.

## Why the Goal stops

The contract required both a complete regression suite and zero media/demo execution.
This repository's complete suite contains hash-pinned project-owned D0 prerecorded demo
regressions. A focused public-demo regression and then the complete suite read that
committed synthetic clip. No third-party/private media or model was used, and the M29
checker was not executed, but the literal no-media assertion is false. It cannot be
reinterpreted after observation, so M31 records a normal contract stop rather than a
PASS.

Python 3.12.13 passed all `338/338` tests, including `14/14` M31 contract,
implementation, and result tests. This supports the additive field and frozen
regression envelope, not compliance with the contradictory no-media clause.
The staged public-release audit scanned 272 files / 544 index-and-worktree snapshots
with zero violations and `operate_enabled: false`.
Public CI run
[`33520669687`](https://github.com/kr-yep/whole-home-agent-public/actions/runs/33520669687)
succeeded for result/handoff revision `ad8e78dbbb24315ecf16926b2dec2209343881c4`.

## Next bounded decision

M32 may use repository evidence only to distinguish mandatory, hash-pinned,
project-owned D0 synthetic fixture reads inside regression tests from ad-hoc demo
acceptance or external/private media experiments. It may not change code, schema,
presentation, replay M29, read media/model, or enable operation.

The serialized response gains one required field. Manual/positional `AnswerTrace`
construction and strict external JSON consumers may need adjustment. This establishes
no CV gain, real-home transfer, physical truth, or runtime authority. `OPERATE` remains
disabled.
