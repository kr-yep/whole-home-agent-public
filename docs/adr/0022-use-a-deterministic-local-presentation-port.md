# ADR 0022: use a deterministic local presentation port

- Status: Proposed — bounded M40 implementation, not adopted provider policy
- Date: 2026-09-02
- Decision authority: Unassigned
- Applicability: Closed B1 synthetic replay only

## Context

M39 selected a deterministic local default and kept any model or cloud presenter behind
a later, separately authorized boundary. The demo already had a hand-written summary in
its composition module, but that function was not a replaceable port, did not return a
failure receipt, and described temporal actions not represented in the M38 text packet.

## Proposed decision and implementation

Add one `LocationPresenter` protocol, one `DeterministicLocationPresenter`, and one
`present_location_context` use case in `presentation.py`. The use case accepts only the
exact `whole-home-agent.location-context.v1` mapping, creates a fresh minimized copy,
and validates the presenter's identity and bounded text output. Its receipt is
`whole-home-agent.presentation-result.v1` with explicit `PRESENTED` or `FALLBACK`
status, presenter identity, context schema, text, fallback flag, and fixed failure code.

`public_demo.py` is the sole composition root and selects only the deterministic local
presenter. It returns the exact context and receipt additively while retaining the
existing structured `answer` and `answer_summary` key. Streamlit displays that same
context rather than rebuilding it in the UI.

The successful key answer now says only that the key is inside the bag and the bag is at
the sofa. It no longer says the system observed a put-then-move sequence because those
temporal events are not present in the M38 presenter context. This changes prose, not
claims, relation state, query resolution, evidence, or epistemic status.

Malformed or extra context, hostile identifiers, invalid presenter identity, exception,
empty/overlong/control-character output, or other presentation failure yields fixed
fallback prose. Exception content is not copied into the receipt. The structured answer
and evidence remain available; no retry or side effect occurs.

## Alternatives

- Keep the helper inside `public_demo.py`: smaller file count, but no enforceable port,
  input contract, output receipt, or independently testable fallback.
- Let Streamlit call a presenter directly: rejected because UI code would choose
  concrete infrastructure and could drift from CLI output.
- Add provider/local-model adapters now: rejected by M39, current authority, and YAGNI.
- Let presentation failure erase the answer: rejected because prose is optional and
  must not become the truth or availability boundary.

## Consequences

The demo has one replaceable presentation seam without a model dependency. The seam is
larger than the previous helper because it validates both admission and output, but it
remains one module and one concrete implementation. No network, credential, provider,
model, storage, tool, or action capability exists. M41 may only verify packaging and
clean installed-demo behavior before any publication decision. `OPERATE` remains
disabled.
