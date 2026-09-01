# ADR 0017: expose query subject in `AnswerTrace`

**Status:** `PROPOSED — bounded M31 implementation selected, not governance adoption`

## Context

M29 showed that the public answer object can report status, location, scope, frontier,
and relation evidence without identifying the subject of the query at its top level.
Relation steps happen to retain `key` in the golden FOUND case, but non-FOUND answers
can have no path. Presentation prose is not the canonical answer contract.

## Proposed decision

For the bounded M31 experiment, add required query-scope `subject_id` to immutable
`AnswerTrace`, populate it from `QueryRequest` at the sole `_trace` constructor, and
project it through both existing answer serializers. Do not infer it from claims or
relations and do not change query resolution or epistemic semantics.

## Alternatives

- Public-demo DTO only: smaller locally, but duplicates query context and leaves B0 and
  the canonical answer inconsistent.
- No change: preserves bytes but cannot identify empty-path UNKNOWN/CONFLICT answers.

## Consequences

The response becomes self-describing and B0/B1 stay aligned. The JSON change is
additive, while direct or positional construction may require updates. Session claim,
projection, and canonical semantic hashes must remain unchanged. This ADR grants no
M29 retry, sensing, model, data, action, or `OPERATE` authority.
