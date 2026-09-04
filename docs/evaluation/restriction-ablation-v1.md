# Restriction ablation v1

**Date:** 2026-09-04

**Scope:** whole repository, with executable treatments limited to public/synthetic D0/B1

**Verdict:** `EVIDENCE-BOUNDED REFACTOR`

**Operation:** `DISABLED`

This review separates usability constraints from boundaries that prevent a model from
changing evidence, authority, devices, or private household state. Passing tests below
does not authorize live sensing, household-data use, public-cloud egress, or action.

## Project-wide experiment design

The unit of comparison is a restriction, not a feature wish. A restriction is removed
only when the relaxed treatment preserves the same observable product contract and does
not add a new data, authority, mutation, or action path. The baseline is public revision
`34b47d45c12886a43afce9b4218cc07df43cefc7`; the treatment is the unpushed local
`restriction-ablation-v1` branch.

The executable envelope contains only repository code, generated media, fake model
responses, and temporary databases. It contains no camera, household recording, remote
endpoint, credential, device, or physical action. Consequently, those capabilities are
classified `UNDECIDED`, not rejected and not proven safe.

## Repository-level results

| Area | Treatment and evidence | Decision |
|---|---|---|
| Historical source hashes | A comment-only edit to `presentation.py` left all 103 current-product cases passing but failed 2 of 47 M40/M41/M44 cases solely because today's bytes no longer equaled a historical digest. Separately, regrouping CI without changing product behavior failed M32 for the same reason | Remove current-worktree-to-historical-result coupling; retain recorded paths/digests as receipts and exact comparisons inside explicitly rerun versioned gates |
| CI compatibility matrix | Baseline runs all 518 cases on four Python versions (2,072 case executions before separate video/demo jobs). Treatment runs the 103 current MVP cases on four versions and the full 518-case suite once on Python 3.12 (930 executions), a 55.1% reduction while retaining current cross-version and full-history coverage | Narrow the matrix; do not delete historical tests |
| Product versus research verification | Local profiles passed: current product 103, M13–M19 71, M20–M29 141, M30–M39 91, M40–M44 77, and supporting perception research 23. The full suite passed 518 with 33 optional skips | Keep separate profiles; stop treating every historical gate as a current product acceptance criterion |
| Governance/document volume | The repository contains 45 source files, 54 test files, 87 documentation files, 72 config files, 24 ADRs, and a 364-line state checkpoint | Narrow future editing to one concise current-MVP page plus immutable history; no historical deletion was tested or performed |
| Claim admission and projection | Existing tests cover duplicate identity, conflicts, containment cycles, unknown/occluded states, and `key -> bag -> sofa` inference | Keep; these checks prevent internally inconsistent answers and are not the demonstrated source of friction |
| Model authority | Fake-translator and presenter tests broaden phrasing while the typed answer remains deterministic; action-shaped and unknown-entity output is rejected | Keep the model outside claim commit and action; this preserves replaceability and prevents generated prose becoming state |
| Model endpoint ergonomics | `localhost`, common Chat Completions fields, one-time typed configuration parsing, and a 120-second cold-start bound pass focused tests | Remove the four engineering restrictions listed below |
| Public-release hygiene | The existing audit rejects secrets, private/runtime artifacts, unmanifested media, and oversized files; no product limitation was attributable to these checks | Keep |
| Fixed evaluation manifests and splits | Existing experiment records show that model/slicing candidates can improve one metric while failing cost or transfer gates | Keep comparable splits, hashes, and before/after reporting; these are what make an ablation interpretable |
| Modular monolith / no graph / no multi-agent runtime | The current relation chain and replay fit one process and typed tables; no measured workload requires distribution | Keep the small implementation, but describe these as present design choices rather than permanent prohibitions |
| Live camera, private persistence, cloud API, actions | No executable treatment used consenting subjects, a retention path, a real provider, or an enrolled device | Undecided by this experiment; each needs its own bounded prototype and evidence |

The case-execution reduction is a static count, not a claim of a 55.1% CI wall-clock or
cost reduction. CI setup, dependency installation, and parallel scheduling were not
measured locally.

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
| Single automatic model retry | Fake responses cannot estimate transient failure frequency or user-visible latency | Collect local endpoint failure/latency traces, then compare zero versus one idempotent retry |
| Question length and output-size bounds | Current tests prove rejection behavior, not whether users hit the limits | Observe sanitized local demo telemetry or run a scripted prompt corpus before changing them |

## Reproduction

```powershell
python -m unittest tests.test_offline_memory tests.test_m40_local_presentation -v
python -m unittest discover -s tests -v
python tools/audit_public_release.py
```

For the comment-only historical-coupling probe, insert a non-semantic comment in
`src/whole_home_agent/presentation.py`, run the 103 current-product tests and the M40,
M41, and M44 tests, then restore the file. The observed result was 103 current cases
passing and two historical failures. After decoupling, the same probe passed all 103
current cases and all 54 selected historical cases (one optional skip). With the probe
restored, the full suite passed 518 cases with 33 optional skips; the public-release
audit scanned 352 files across 704 snapshots with zero violations.
