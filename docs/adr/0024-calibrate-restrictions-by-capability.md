# ADR 0024: Calibrate restrictions by capability and data class

- Status: `PROPOSED / BOUNDED IMPLEMENTATION`
- Date: 2026-09-04
- Scope: public/synthetic D0 query and language presentation

## Context

The prototype accumulated restrictions from several different concerns: deterministic
replay, public-release hygiene, private household operation, and model-provider safety.
Applying every restriction to every path caused ordinary local configuration failures
without reducing the model's authority, because the model already receives only a
minimized derived packet and owns no mutation or action capability.

## Decision

For the bounded D0 implementation experiment:

- remove restrictions only when an ablation shows lower configuration or compatibility
  cost without expanding data, mutation, authority, or action capability;
- accept `localhost` as equivalent to literal local loopback;
- use the common Chat Completions request fields instead of forcing provider extensions;
- allow a bounded 120-second cold-start timeout with no retry;
- validate environment configuration once and degrade to deterministic output;
- retain closed typed queries, known-entity validation, minimized context, deterministic
  answers, bounded I/O, credential hygiene and the absence of action/storage handles;
- do not infer authorization for public-cloud egress, private data, live sensing or
  physical/device action from this D0 experiment.

## Alternatives

- Remove every guard at once: rejected because failures could not be attributed and it
  would mix usability with new data/action authority.
- Keep every existing guard: rejected because `localhost`, provider-specific request
  fields and cold-start timing add friction without strengthening the core boundary.
- Add a policy engine or plugin framework: rejected as unnecessary for this slice.

## Consequences

The local demo is easier to configure and more compatible while the important boundary
remains structural: the model can interpret or verbalize but cannot establish facts or
cause effects. Broader endpoints and real household operation remain separate decisions,
not hidden extensions of this ADR.
