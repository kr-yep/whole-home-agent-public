# Market synthesis: the smallest useful whole-home memory demo

**Evidence date:** 2026-09-02

**Decision scope:** hackathon demo and future product direction

**Runtime:** `OPERATE DISABLED`

This is a representative comparison of current whole-home assistants and relevant
memory research, not a claim that every product has been exhaustively reviewed. Product
pages describe vendor claims; research pages describe their own evaluation envelopes.
Neither establishes that this repository has the same capability.

## Product cut

Our demo should be a **local visual object-memory layer**, not a smaller copy of a broad
home-automation suite:

```text
fixed prerecorded scene
  → small-object/container/location estimates
  → deterministic accepted-claim path
  → traceable key → bag → sofa answer
  → minimized text context for an optional language presenter
```

The deterministic path decides what the system may say. A future language model may
only verbalize that bounded result; it does not see media, commit claims, authorize an
action, or become the source of household truth.

## Adopt, defer, reject

| Market or research lesson | Decision for this project | Reason and concrete result |
|---|---|---|
| Miloco uses a staged perception pipeline and visual/audio gates before expensive multimodal inference. | **Adopt the concept, not its code.** | Keep motion/periodic selection and replaceable perception adapters. M38 does not add audio, live capture, or a VLM. |
| Miloco separates candidate household knowledge from promoted memory. | **Adopt the epistemic discipline.** | Our existing `ClaimCandidate → deterministic commit → projection → query` path remains the sole state path; a language model cannot promote observations. |
| Miloco retains meaningful events and diagnostic traces. | **Adopt only the traceable-event idea.** | Keep relation facts and evidence-bound answers; do not retain raw video, identity profiles, or long-term household history in the current gate. |
| Home Assistant supports local or cloud language models and uses a fast local intent path before an LLM fallback. | **Adopt provider replaceability later.** | First freeze a provider-neutral, minimal text packet. Do not add a provider, credential, network client, or fallback router in M38. |
| Google Home exposes natural-language search, event descriptions, and brief summaries over camera history. | **Adopt the query-and-summary UX.** | The demo leads with “Where is the key?” and a short answer, then reveals the relation trace. We do not implement video-history search. |
| Alexa+ combines many sensor signals for personalized, proactive assistance. | **Defer.** | Multi-sensor fusion and proactive suggestions increase consent, false-positive, and action risk without improving the three-day core demo. |
| Miloco includes identity recognition, audio, proactive tasks, alerts, and device control. | **Defer or exclude.** | Face/person identity and audio are excluded; task execution and device control stay blocked until roles, policy, consent, and enforcement exist. |
| Commercial camera products expose rich camera histories, while Miloco retains meaningful events with clips. | **Reject raw-media cloud egress and long-term raw-media storage for this slice.** | A future optional cloud presenter may receive only an explicitly authorized minimized text packet. M38 performs no egress or new media retention at all. |
| Samsung Ballie and LG CLOiD add mobile/robotic embodiment. | **Reject for the hackathon slice.** | Embodiment adds navigation, manipulation, hardware, and safety work unrelated to proving object memory. |
| SpotEM and Embodied VideoAgent study efficient video search and persistent memory. | **Use as prior art, not a novelty claim.** | We should not claim to be the first object-finding memory agent. Our narrower demo focus is fixed-camera small objects, container/location relations, local-first processing, and visible evidence limits. |

## What M38 adds to the demo

The Streamlit page now shows the exact JSON-like text context that an optional language
presenter could receive. The allowlist contains only:

- schema and purpose;
- answer subject, status, location, and epistemic status;
- relation facts with subject, predicate, object, and epistemic status.

It excludes frames, video, evidence references, claim IDs, source/run identifiers,
history, raw query text, credentials, endpoints, and action handles. This is data
minimization by construction for the synthetic demo, not approval to process a real
household or send anything to a cloud service.

## Boundaries that remain separate

| Boundary | M38 state |
|---|---|
| Data | Fixed synthetic replay; minimized text preview derived from the scoped answer |
| Control | Deterministic code chooses the allowlisted fields; no model controls admission |
| Action | None; no executor or generic command interface exists |
| Authority | Proposed governance and `ACTION_POLICY.md`; `OPERATE` remains disabled |
| Physical result | None; replay answers are estimates, not verified real-world outcomes |

## Sources

- [Xiaomi Miloco repository and feature summary](https://github.com/XiaoMi/xiaomi-miloco)
- [Miloco perception pipeline](https://github.com/XiaoMi/xiaomi-miloco/blob/main/knowledge/03-features/perception-pipeline.md)
- [Miloco home-profile candidate and promotion design](https://github.com/XiaoMi/xiaomi-miloco/blob/main/knowledge/03-features/home-profile.md)
- [Miloco license](https://github.com/XiaoMi/xiaomi-miloco/blob/main/LICENSE.md)
- [Home Assistant local and cloud AI architecture](https://www.home-assistant.io/blog/2025/09/11/ai-in-home-assistant/)
- [Home Assistant local intent with LLM fallback](https://www.home-assistant.io/blog/2025/02/05/release-20252/)
- [Google Home camera summaries and searchable history](https://blog.google/products-and-platforms/devices/google-nest/googe-home-premium-google-ai-pro-subscription/)
- [Alexa+ sensor fusion and agentic assistant overview](https://aws.amazon.com/solutions/amazon/one-amazon-lane/alexa/)
- [Samsung Ballie and Gemini](https://news.samsung.com/us/samsung-google-cloud-expand-partnership-bring-gemini-ballie-home-ai-companion-robot-by-samsung)
- [LG CLOiD home robot](https://www.lg.com/us/press-release/lg-cloid-home-robot)
- [SpotEM: Efficient Video Search for Episodic Memory](https://proceedings.mlr.press/v202/ramakrishnan23a.html)
- [Embodied VideoAgent](https://openaccess.thecvf.com/content/ICCV2025/papers/Fan_Embodied_VideoAgent_Persistent_Memory_from_Egocentric_Videos_and_Embodied_Sensors_ICCV_2025_paper.pdf)

## Next smallest task prepared

M39 now selects local default plus separately authorized cloud replaceability and keeps
API-key presence distinct from authority. M40 may add only one narrow presentation port
and deterministic local presenter over the existing M38 context. It must retain the
structured answer fallback and add no provider SDK, local-model adapter, key, endpoint,
network path, household data, policy broker, or action capability.
