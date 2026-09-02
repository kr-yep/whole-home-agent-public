# M39 language-presentation boundary decision

## Outcome

Select `A_LOCAL_DEFAULT_SEPARATE_CLOUD_AUTHORITY`. The demo keeps a deterministic,
no-model answer as its default; a local model and an explicit opt-in cloud presenter are
replaceable future adapters behind the same presentation-only boundary. A key can
authenticate a future request but cannot authorize household-data egress.

This is a proposed architecture decision recorded from repository evidence and current
official provider documentation. It is not adopted household policy and makes no API
request.

## Candidate matrix

| Candidate | Pass | Fail | Result |
|---|---:|---:|---|
| A — local default, separate cloud authority | 10 | 0 | selected for a separately frozen local M40 |
| B — API-key autostart cloud | 0 | 10 | rejected: conflates credential, control, and authority |
| C — permanent local only | 9 | 1 | rejected: removes the requested replaceable cloud route |

The ten fatal gates require a deterministic fallback, separate authority, exact data
allowlisting, presenter-only output, local/cloud truth parity, retention minimization,
least-privilege credentials, bounded network failure, minimal telemetry, and a fully
closed current runtime gate.

## Exact data classification

| M38 field | Future real-home meaning | Current egress |
|---|---|---|
| `schema`, `purpose` | fixed public protocol metadata | prohibited; no egress profile exists |
| `answer.subject_id` | object label or identifier | prohibited |
| `answer.status` | derived query result | prohibited |
| `answer.location_id` | zone label or identifier | prohibited |
| `answer.epistemic_status` | qualifier bound to a private answer | prohibited |
| relation subject/object IDs | object or zone labels/identifiers | prohibited |
| relation predicate | private derived relation when bound to entities | prohibited |
| relation epistemic status | qualifier bound to a private relation | prohibited |

The allowlist controls field names, not the sensitivity of future values. Before a real
cloud request, object and zone value constraints, recipient, purpose, retention,
telemetry, deletion, and affected-person scope must all be explicitly approved.

## Provider evidence and limits

As of the evidence date, [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)
state that API data is not used for model training by default unless the customer opts
in. They also distinguish default abuse-monitoring retention, which may keep customer
content for up to 30 days, from endpoint application state. For the Responses API,
`store=false` can reduce application-state storage but does not itself establish Zero
Data Retention. [OpenAI's API overview](https://developers.openai.com/api/reference/overview)
also treats API keys as secrets and recommends server-side environment or key-management
loading.

These facts bound one possible provider; they do not select OpenAI, approve a recipient,
guarantee deletion, or turn an API key into consent. Retention and endpoint behavior
must be rechecked when a provider implementation is actually proposed.

## Smallest authorized follow-up

M40 may add a narrow presentation port plus deterministic local presenter and keep the
composition root on that implementation. It may not add a cloud/local-model adapter,
provider SDK, endpoint, credential configuration, network path, policy broker,
household data, or operational capability. The existing structured answer remains the
fallback and source of truth.

Python 3.12.13 passes `12/12` focused M39 tests and `411/411` complete-regression tests.
The public audit scans 309 files / 618 index-and-worktree snapshots with zero violations
and `operate_enabled: false`. These are local-branch results; public CI was not run and
nothing was pushed.
