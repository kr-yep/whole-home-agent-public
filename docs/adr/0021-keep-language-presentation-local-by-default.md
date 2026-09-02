# ADR 0021: keep language presentation local by default

- Status: Proposed — M39 repository decision, not adopted data/egress policy
- Date: 2026-09-02
- Decision authority: Unassigned
- Applicability: B1 synthetic replay and a separately frozen local M40 implementation

## Context

M38 exposes an exact minimized text packet for verbalizing one scoped location answer.
The packet is smaller than media, but its future values can still identify household
objects, zones, query outcomes, and relations. Text-only processing therefore reduces
disclosure; it does not make real-home data public, anonymous, or authorized for cloud
use.

The product should work without a provider and remain replaceable. It should also leave
a safe route for an explicitly authorized bring-your-own-key cloud presenter. Those
goals conflict if the mere presence of a key silently turns on egress.

## Proposed decision

Select a local-first presentation boundary with three deliberately separate states:

1. The default is the existing deterministic evidence-bound answer. It needs no model,
   account, credential, or network.
2. A future local model may implement the same narrow presentation port after its
   weights, license, resource cost, output behavior, and no-egress boundary are
   separately verified.
3. A future cloud text presenter may implement that port only after a separate policy
   adoption and runtime authorization. Adding a key or configuration value never
   activates it.

Only `whole-home-agent.location-context.v1` may enter a presenter. A model receives no
ledger, evidence store, media, full query, history, credential, tool, or action handle.
Its response is untrusted prose: it cannot commit a claim, alter projected state,
change the scoped answer, authorize operation, or prove a physical outcome.

If a cloud implementation is later authorized, it must be stateless and text-only,
with no files, tools, conversation, or background processing; use a project-scoped
least-privilege secret outside Git, UI inputs, prompts, events, and ordinary logs; pin
the exact host, path, model, timeout, and cost bound; make no automatic retry; and use
the deterministic answer on denial, timeout, invalid output, or provider failure.

For an OpenAI implementation specifically, a later gate would have to select and pin
the request behavior. Official documentation says API data is not used to train models
by default, while abuse-monitoring content may be retained for up to 30 days. The
Responses API also has separate application-state retention behavior. Requesting
`store=false` would minimize that application state, but must not be described as zero
retention. See [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)
and [API authentication](https://developers.openai.com/api/reference/overview).

## Boundary separation

| Boundary | M39 decision |
|---|---|
| Data | Exact M38 text allowlist; real household values remain private derived state |
| Control | A future composition root selects one presenter; models cannot select themselves |
| Action | None; there is no executor, tool surface, or generic command interface |
| Authority | Current profile is deterministic only; future cloud use needs separate data/egress and runtime authorization |
| Credential | Authenticates to a provider only; never supplies consent or policy authority |
| Physical result | None; prose does not prove the location estimate or any world change |

Pure local deployment means deterministic or locally hosted generation with external
network egress disabled. Once a cloud text presenter is used, the accurate label is
**local-first hybrid**, even if perception and memory remain local.

## Alternatives

- Enable cloud whenever an API key exists: rejected because credentials are not
  consent, policy, or runtime authority and because failure could remove the demo.
- Permanently forbid cloud: safer in one dimension, but needlessly removes an optional
  future route that can be bounded and explicitly authorized.
- Give every presenter the full answer trace or memory reader: rejected because it
  expands private data, coupling, and authority without improving the narrow task.
- Let the model decide whether to use local or cloud execution: rejected because
  untrusted presentation output cannot control egress or credentials.

## Consequences

M39 does not add a presenter implementation, dependency, endpoint, environment
variable, secret, model, or request. It does not adopt `ACTION_POLICY.md` or enable
`OPERATE`. M40 may add only one narrow presentation port and a deterministic local
implementation while keeping cloud and local-model adapters absent. Any real provider
remains a later, separately authorized gate.
