# ADR 0018: separate static, regression, and experiment verification

**Status:** `PROPOSED — bounded M32 selection, not governance adoption`

## Context

M31 required both a complete regression suite and zero media/demo execution. The
current complete suite intentionally verifies a committed synthetic clip, so both
requirements could not be true at once.

## Proposed decision

Future gates must name an explicit verification profile. Static contracts read no
media and execute no application/demo. Complete regression may use only an exact,
manifest-backed, repository-committed, project-owned `D0_SYNTHETIC` fixture, and its
result means regression/conformance only. Ad-hoc acceptance or experiment work always
requires a separately frozen gate.

## Alternatives

- Zero media for every verification: simple wording, but it prevents the current
  decoder and closed-demo conformance path from being verified.
- Allow any D0 or public media: easier to extend, but loses exact identity, purpose,
  provenance, and fail-closed extension boundaries.

## Consequences

Contracts become slightly more explicit but no longer hide incompatible verification
requirements. Fixture identity, workflow revision, result, and evidence limits must be
receipted. M31 remains a normal stop. This ADR grants no new fixture, model, private or
live data, action, M29 retry, or `OPERATE` authority.

