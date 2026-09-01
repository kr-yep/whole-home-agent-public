# M37 teammate handoff runbook

## Outcome

M37 passes its document-only gate. The public repository now contains one exact
[teammate handoff runbook](../teammate-handoff-runbook.md) for a real teammate to clone
the pinned M36 revision, create the locked demo environment, run the offline checker,
interpret its receipt, present the 90-second demo or CLI fallback, and safely remove the
disposable clone.

The runbook gives separate PowerShell and Bash/Zsh procedures, records clone/install
milliseconds, distinguishes committed Git-blob identity from local checkout bytes,
maps every checker failure class to a bounded next action, and includes Git/uv/Windows
ACL troubleshooting plus a sanitized result template.

## Verification

Python 3.12.13 passed `11/11` focused static/document tests and `393/393` complete M32
regression tests. The public audit passed 300 files / 600 index-and-worktree snapshots
with zero violations and `operate_enabled: false`; public CI is pending. PowerShell
fenced blocks parsed without syntax errors. No command block from the runbook was
executed as an acceptance drill.

First public CI run
[33529559775](https://github.com/kr-yep/whole-home-agent-public/actions/runs/33529559775)
passed the prerecorded-video and closed-demo jobs but failed Python 3.11–3.14. The new
static test requested `f16a0a4…:uv.lock`, while `actions/checkout` defaults to a
single-commit checkout; the historical object was therefore unavailable. Revision
`554757de905bae1a492a47f87b13e1827ae1e2d6` keeps the exact handoff revision assertion
but checks the retained lock identity at `HEAD`, avoiding an unnecessary full-history
CI checkout. This is verification-harness portability only; the runbook, lock, fixture,
product, and acceptance boundaries are unchanged. Follow-up CI is pending.

## Evidence boundary

This is runbook usability evidence only. No clone, locked install, demo, checker
acceptance, live sensing, private media, model load, or action occurred in M37. No real
teammate receipt exists yet, so independent teammate and cross-platform success remain
unestablished. M34 remains its historical normal STOP and `OPERATE` remains disabled.

Per the user's current direction, work stops after M37 is pushed and public CI is
confirmed. A later receipt-intake or Miloco-informed object-memory positioning decision
requires a new user direction; it is not auto-started.
