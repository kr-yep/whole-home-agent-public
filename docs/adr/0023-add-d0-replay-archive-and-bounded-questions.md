# ADR 0023: add a D0 replay archive and bounded natural-language questions

- Status: Proposed — bounded implementation requested for the public hackathon demo
- Date: 2026-09-02
- Decision authority: Current user direction for local repository implementation only
- Applicability: Synthetic/public D0 completed replays; `OPERATE DISABLED`

## Context

The closed demo already produces a traceable `AnswerTrace`, but session state disappears
when the process exits and the Streamlit question is fixed. The user requested durable
memory, free-text questions, and an optional LLM API before teammates perform real-world
testing. Current governance still prohibits private household persistence and cloud
egress, so the implementation must demonstrate the seams without silently activating
those capabilities.

## Decision

Add the smallest three-part extension:

1. `SQLiteReplayArchive` atomically stores one canonical document for each completed D0
   replay identity. It preserves the source descriptor and accepted claims, stores no
   media or query text, is idempotent for identical content, conflicts on identity reuse,
   and verifies both payload and semantic hashes before rebuilding the projection.
2. A deterministic parser accepts only bounded Chinese/English location questions that
   name exactly one entity present in the restored claims. It returns a subject ID, not
   an SQL expression, model prompt, command, or authority decision.
3. The existing `LocationPresenter` remains the only language seam. Deterministic prose
   stays the default. A no-dependency OpenAI-compatible adapter is available only for an
   explicitly selected literal loopback endpoint, with proxies and redirects disabled,
   one bounded request, no retry, and the existing sanitized fallback.

The SQLite record is durable accepted-claim history, not physical truth. Its projection
is rebuilt on read and remains derived. The LLM sees only
`whole-home-agent.location-context.v1`; it never receives the database, question,
evidence history, media, credential handle, or action capability, and its prose cannot
change the structured answer.

## Boundary map

```text
completed synthetic/public replay
  → sole deterministic claim commit
  → canonical ReplaySession
  → SQLiteReplayArchive (durable accepted-claim document)
  → verify hash + rebuild projection
  → bounded question parser (text → one subject ID)
  → StateQuery.locate
  → minimized location context
  → deterministic presenter [default]
     or literal-loopback chat presenter [explicit, optional]
```

- Data: D0 descriptor, accepted claims, derived answer, minimized text context.
- Control: fixed archive schema, parser vocabulary, local endpoint rules, timeout.
- Authority: no household/policy/egress authority is created.
- Action: absent.
- Physical outcome: absent; replay answers remain estimates.

## Failure contracts

- Partial/failed runs are never written through the completed-session interface.
- Missing, incompatible, corrupted, or hash-mismatched archives fail closed.
- Duplicate identical replay identity is `UNCHANGED`; different content is a conflict.
- Unsupported or ambiguous questions fail before storage query presentation.
- Remote hostname/IP, URL credential, redirect, proxy, malformed response, timeout, or
  overlong output cannot become a location result; presentation falls back while the
  structured answer remains available.

## Alternatives

- Store a mutable current-location table only: rejected because it loses accepted-claim
  history and makes a projection look authoritative.
- Add a graph/vector/Memory Core platform: rejected because the current exact lookup and
  two-edge traversal do not justify the dependency or migration burden.
- Use an LLM to interpret every question: rejected because the closed vocabulary is
  deterministic and the model would gain unnecessary query/control influence.
- Enable OpenAI or another cloud endpoint when an API key exists: prohibited because a
  credential is not consent, policy adoption, or runtime authority.

## Consequences and reconsideration triggers

SQLite adds a durable artifact that must remain ignored by Git and cannot be used for
real household data under the current policy. There is one writer per command and no
multi-process throughput claim. Revisit the schema only when a retained compatibility,
retention/erasure, multi-writer, or real authorized household requirement is defined.
Revisit remote presentation only after data-egress policy adoption, credential ownership,
endpoint/model pinning, provider retention review, and separate runtime activation.
