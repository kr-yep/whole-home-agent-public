# Restriction ablation v1

**Date:** 2026-09-04

**Scope:** public/synthetic D0 memory demo only

**Verdict:** `BOUNDED REFACTOR`

**Operation:** `DISABLED`

This review separates usability constraints from boundaries that prevent a model from
changing evidence, authority, devices, or private household state. Passing tests below
does not authorize live sensing, household-data use, public-cloud egress, or action.

## Ablation results

| Restriction | Baseline evidence | Ablation | Result | Decision |
|---|---|---|---|---|
| Local endpoint must be a literal IP | `localhost` was rejected even though it resolves to the same local-machine use case | Accept `localhost` while retaining literal loopback and the existing tailnet case | Focused endpoint tests pass; public HTTP, LAN, userinfo, HTTPS and redirects remain rejected | Remove literal-IP-only rule |
| Every request forces `reasoning_effort=none` | The field is a provider extension, not part of the common Chat Completions request needed by this adapter | Omit it and keep only model/messages/temperature/max_tokens/stream | Fake OpenAI-compatible contract passes with a smaller request | Remove forced extension |
| Timeout cannot exceed 30 seconds | A local model can spend longer than 30 seconds on cold load; the limit was not backed by a benchmark | Permit a configured timeout up to 120 seconds while keeping one request and no retry | 60-second configuration is accepted; invalid values fail as typed configuration errors | Raise bound to 120 seconds |
| Environment values are parsed repeatedly in the UI | A malformed numeric value could raise outside the answer error boundary and the same clients were rebuilt more than once per rerun | Parse once, catch the typed configuration error, and use deterministic fallback | Unit contract passes; no network or real model was used | Remove duplicate parsing and page-level failure |
| Only one hand-written location phrasing is useful | The prior public revision exposed only one query shape | Keep deterministic-first routing, then support location, yes/no verification and container contents; an optional translator returns only a closed operation and known IDs | Current public suite exercises all three shapes and action-shaped rejection | Keep broader query surface |

The focused ablation run executed 55 tests successfully with four optional video/UI
tests skipped in the minimal runner. It used fake responses and opened no real endpoint.

## Restrictions retained because they protect a real boundary

- A model cannot append accepted claims, write SQLite, change a structured answer,
  authorize an action, or receive a device/general tool handle.
- Unknown, conflicting and out-of-scope evidence remains distinguishable; generated
  prose cannot turn abstention into a fact.
- Translator output is limited to `locate`, `verify`, `contents`, or `reject`, and all
  referenced IDs must already exist in the restored replay.
- Credentials, full archive contents, media, claim IDs and run IDs do not enter the
  model request or persistent memory.
- Requests remain bounded to one attempt, a finite timeout and response size, with
  deterministic fallback.
- Live cameras, household media, private-memory egress and physical/device action stay
  outside this ablation because no consenting household, device or enforcement boundary
  was part of the experiment.

## Candidate restrictions not decided by this experiment

| Candidate | Why this experiment cannot decide it | Required next evidence/decision |
|---|---|---|
| Public HTTPS language APIs | Would transmit question/context and may incur retention or cost | Explicit data classes, provider/retention review, credential owner, cost bound and exact egress authorization |
| Shared-LAN model endpoint | Another machine can observe the text and LAN identity is not authenticated by this adapter | Exact host trust model and authenticated transport |
| Live camera and real household memory | Introduces affected-person privacy, retention and access questions absent from D0 | Bounded demo consent/session policy and deletion path |
| Device actions | Changes external state; query tests provide no action-safety evidence | Typed broker, allowlist, requester authority, receipt and manual override |
| Historical module SHA gates in active regression | The latest feature commit changed four chained records only to follow one source edit, demonstrating maintenance cost | Preserve historical records, then version a current package contract that compares built artifacts to the selected source revision instead of today's worktree |

## Reproduction

```powershell
python -m unittest tests.test_offline_memory tests.test_m40_local_presentation -v
python -m unittest discover -s tests -v
python tools/audit_public_release.py
```

The full suite and public audit must be rerun after this document and code change. Their
final counts belong in the live project checkpoint, not retroactively in this report.
