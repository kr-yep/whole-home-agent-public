# ADR 0020: preview minimized text before adding a language provider

- Status: Proposed — bounded M38 offline implementation, not adopted policy
- Date: 2026-09-02
- Decision authority: Unassigned
- Applicability: Explicitly requested hackathon demo refinement

## Context

The current demo already produces a scoped, evidence-bound `AnswerTrace`. A language
model could make that answer more conversational, but accepting media, history,
credentials, or a generic state interface would couple presentation to private data and
authority that the current project does not have. `ACTION_POLICY.md` also prohibits
cloud egress and runtime credentials in B0/B1.

## Proposed decision

Implement one pure, local allowlist projection from the existing public answer mapping
to `whole-home-agent.location-context.v1`, and show it in the closed Streamlit demo.
The context contains only answer identity/status/location/epistemic state and the
subject-predicate-object relation facts required to verbalize that answer.

Do not add a language provider, network client, credential, free-form prompt, memory
reader, action interface, or runtime toggle. The projection is data, not authority or a
command. Its construction performs no I/O.

## Alternatives

- Send the full answer trace: easier, but unnecessarily exposes run, claim, evidence,
  and internal diagnostic identifiers.
- Send images or clips to a vision-language provider: broader scene understanding, but
  violates the current local-only and no-egress boundary.
- Add a provider abstraction immediately: premature while provider, retention,
  credential, network, and policy decisions are unresolved.
- Keep only the hand-written answer: smallest runtime, but does not make the intended
  future privacy boundary visible to judges or teammates.

## Consequences

The demo can show exactly what a future text presenter would and would not receive, and
tests can freeze the allowlist independently of any vendor. This does not establish that
real household text is harmless, anonymous, or approved for cloud use. A later provider
requires a separate data/egress decision, authority, configuration, failure contract,
and verification. `OPERATE` remains disabled.
