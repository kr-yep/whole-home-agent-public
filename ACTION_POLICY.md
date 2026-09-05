# Whole-Home Agent Action Policy

**Status:** `PROPOSED — NOT ADOPTED`\
**Version:** `0.1-draft`\
**Drafted:** `2026-08-24 Asia/Taipei`\
**Effective from:** `NONE`\
**OPERATE:** `DISABLED`

This policy governs live sensing, household-data processing, external communication or egress, account/device mutation, and physical operation. It grants no capability while proposed. Code implementation, retrieved content, model output, historical permission, device ownership metadata, and conversational confidence do not authorize an action.

## Activation invariant

- `OPERATE` is disabled globally and for every environment, person, room, device, account, sensor, and capability.
- Meeting prerequisites does not automatically enable it. Activation requires an adopted policy, executable enforcement, passed evidence for the relevant risk class, and a separate explicit environment/capability enablement decision recorded in `PROJECT_STATE.md`.
- Missing, unclassified, stale, contradictory, unauthenticated, expired, or `UNKNOWN` information fails closed.
- The absence of a device/capability allowlist entry is a prohibition.

## Actors and authority

All assignments are unresolved. Do not infer them from repository access, conversation history, device ownership metadata, network location, or observed household behavior.

| Actor/role | Current assignment/authentication | May request | May approve | May change policy | Review/expiry |
|---|---|---|---|---|---|
| Project Owner | `UNASSIGNED` | Repository scope and product decisions once assigned | Project decisions within scope; not another person's consent | No, unless separately assigned Policy Owner | `UNDEFINED` |
| Policy Owner | `UNASSIGNED` | Policy review | Prospective policy versions and activation within documented authority | Yes, with versioned record and required consent | `UNDEFINED` |
| Engineering Lead | `UNASSIGNED` | Implementation and verification work | Engineering integration only | No | `UNDEFINED` |
| Data Steward | `UNASSIGNED` | Data processing/retention proposals | Data handling only within adopted policy and affected-person rights | No unilateral policy change | `UNDEFINED` |
| Household owner/administrator | `UNDEFINED` | Only after identity and scope are defined | Never substitutes for every affected person's consent or law | Only if also assigned Policy Owner | `UNDEFINED` |
| Adult resident / affected person | `UNDEFINED` | Use of their own data/space under adopted policy | Their own consent and withdrawal, subject to applicable constraints | No general policy power by default | `UNDEFINED` |
| Guest, child, caregiver, technician | `UNDEFINED` | `NONE` until specific rules exist | `NONE` until specific rules exist | No | `UNDEFINED` |
| Demo participant | `UNDEFINED` | One bounded demo session only after a specific consent receipt | Their own participation/data scope only; cannot consent for others | No | Session end or earlier withdrawal |
| Runtime service identity | `NOT CREATED` | Typed capability calls only after enrollment | Never approves its own request | No | Not applicable |
| Model, Agent, subagent, retrieved content | Not an authority | Proposals only | None | No | Not applicable |

Resident disagreement, joint consent, guardianship/assent, guest notice, caregiver delegation, technician access, emergency authority, service accounts, and policy recovery remain unresolved. Therefore no runtime request can be authorized.

## Consent and spatial/data scope

- No person, household, room, zone, camera, microphone, stream, account, or device is enrolled.
- Private versus common spaces are not classified. Until classification and consent exist, treat every household space and live feed as restricted.
- No consent record, lawful-use basis, notice mechanism, pause indicator, withdrawal flow, or deletion workflow has been adopted.
- Consent must bind the affected person, exact space/sensor/data purpose, data classes, recipients/egress, retention, start/expiry, and withdrawal path. Silence, presence, past behavior, or device ownership is not consent.
- Shared-space disagreement or missing consent defaults to denial; do not use last-write-wins or infer that property ownership waives another affected person's privacy.
- A future consent receipt must at least bind `consent_id`, policy version, affected persons or guardian authority, camera and field of view, room/session, purpose, allowed data classes, local/cloud processing, permitted viewers, retention schedule, start/end/expiry, and withdrawal/erasure route.
- A one-session demo consent does not authorize later household capture, model training, unrelated queries, cloud use, or product operation.
- Withdrawal must stop future processing within defined latency and invoke the adopted deletion/redaction policy. Because those mechanisms do not yet exist, collection is prohibited.

## Provisional data classes

These classes are not permission and require license, purpose, and provenance review even when offline.

| Class | Content | Current state |
|---|---|---|
| D0 — Non-household development data | Synthetic/generated fixtures and lawfully reusable public data with recorded provenance and license | Offline use may be requested under `IMPLEMENT`; no operational endpoint or credential |
| D1 — Controlled demo media | A bounded staged session with all required participant consent | `BLOCKED` until consent, retention, access, deletion, and session isolation are adopted and implemented |
| D2 — Household data | Real household video, images, events, object/location history, presence or routine data | `BLOCKED` |
| D3 — Special/high-sensitivity data | Children, audio, biometrics, health, intimate/private rooms, or safety/security inference | `EXCLUDED FROM MVP`; any future scope expansion requires new governance and risk review |

## Provisional risk and capability classes

These classes are a review scaffold, not adopted permission. Every concrete capability needs a stable ID and owner-approved mapping. Unclassified consequential actions are prohibited.

| Class | Consequence boundary | Provisional default | Required enforcement before any future use | Human authority | Safe failure |
|---|---|---|---|---|---|
| D0 — Repository/simulation only | Local reversible code/docs/tests with synthetic, generated, or lawfully usable public fixtures; no real target | `IMPLEMENT`, not `OPERATE` | Workspace sandbox, fixture provenance, no production credentials or real endpoints | Explicit repository request for material changes | Stop test and preserve diagnostics |
| R1 — Live sensing or private-state read | Opening camera/mic/RTSP/sensor, observing state, or querying real household memory/evidence even without persistence | `PROHIBIT` | Per-space/person consent, purpose/scope authorization, visible status/pause for sensing, strict read-only adapter, bounded disclosure, no egress | Authenticated scoped requester plus all required affected-person consent | Do not connect or disclose; discard transient buffers |
| R2 — Recording, profiling, private-data persistence or egress | Evidence clips, continuous logs, occupancy/routine inference, biometrics, cloud VLM, sharing/export | `PROHIBIT` | Purpose limitation, minimization, encryption/access, retention/deletion, egress allowlist, audit and consent enforcement | Policy Owner + Data Steward + required affected persons | Do not record/upload; quarantine and delete unauthorized artifact |
| R3 — Communications, purchase, access/security or policy/account mutation | Messages, calls, posts, spending, locks/alarms/security settings, credentials, enrollment, governance changes | `PROHIBIT` | Narrow broker, stable target, typed allowlist, strong authentication, approval separation, cost/rate/TTL, receipts | Dedicated scope authority; some actions may require multiple approvers | No side effect; alert authorized human |
| R4 — Reversible comfort/media actuation | Lights, media, bounded non-safety environmental adjustments | `PROHIBIT` | Device-specific bounds, fresh state, manual override, idempotency, reconciliation and rollback | Authenticated household role under adopted policy | Leave current/safe state; no blind retry |
| R5 — Safety/life-critical actuation | HVAC extremes, emergency locks, alarms, water, gas, electrical, medical, fire or life-safety systems | `PROHIBIT` | Dedicated certified controller/interlocks independent of Agent, explicit emergency policy and human control | Specialized authority defined outside general Agent planning | Dedicated controller's safe state; Agent cannot override |

**Browser-Mediated Ephemeral Sensing Clause (Checkpoint `PUBLIC-B2-BROWSER-CAMERA-001`):**
The browser camera interface (`/camera.html`) operates under direct client control via user gesture and native browser permission prompts (`navigator.mediaDevices.getUserMedia`). Under the strict zero-retention invariant:
1. The server process never directly opens or controls hardware sensors.
2. Received frames are verified in memory via JPEG header inspection without materializing pixels or persisting bytes to storage (`retention: "none"`).
3. Any attached perception sink processes frames strictly in memory and emits transient bounding boxes returned directly to the active client.
4. Stream receipts record only aggregate counts, gaps, and an order-dependent SHA-256 hash.
This interface remains classified as an interactive developer demonstration; it does not authorize unattended background recording, multi-camera persistence, or automated operational actuation.

Biometric identification, covert monitoring, unrestricted recording, general shell/device access, and disabling independent safety interlocks are outside the current proposed scope and remain prohibited.

## Device and action matrix

No real device, sensor, account, endpoint, credential, or capability is enrolled. The matrix is intentionally empty.

| Stable device/capability ID | Location/scope | Allowed actions and bounds | Required fresh state | TTL/rate/cost limit | Approval | Compensation/manual path |
|---|---|---|---|---|---|---|
| _No entries_ | — | None | — | — | — | — |

Adding a row is a material `DECIDE` action. It does not activate the row; activation still requires all policy and verification gates.

## Mandatory trusted-boundary checks

Before any future non-simulated operation, a trusted broker outside the planning/content-processing boundary must verify:

- authenticated requester, role, household/scope, consent, and unexpired authority;
- exact stable target identity and allowlisted typed operation;
- adopted policy version, capability risk class, environment enablement, and no unresolved conflict;
- sufficiently fresh independently obtained state and expected version;
- bounds, rate, cost, schedule, command TTL, and current safety conditions;
- approval from the required human principal, never from retrieved/model-generated content;
- idempotency key, duplicate/concurrency behavior, and no replay-triggered execution;
- defined safe failure, manual override, timeout, and rollback or compensation where physically possible;
- least-privilege credential and egress policy for only that capability.

The planning Agent receives narrow typed capabilities, never raw credentials, unrestricted network/device clients, or generic command execution against operational systems.

## Execution, evidence, and reconciliation

Any future operation must record separately:

1. model/Agent proposal;
2. trusted policy and authorization decision;
3. bounded command attempt with idempotency key;
4. device/provider acknowledgement;
5. independently observed result where possible;
6. reconciliation, partial completion, compensation, alert, or unresolved status.

An acknowledgement is not proof of physical outcome. Replaying history, restoring a database, or rebuilding a projection must never re-execute an action. Multi-device scenes are non-atomic unless an independent transactional controller proves otherwise; retain per-device status and partial-failure handling.

## Secrets, privacy, and retention defaults while disabled

- No runtime credentials or operational egress tokens may be added. Future credentials must reside in a least-privilege secret/capability broker, never prompts, ordinary logs, source control, model memory, or event payloads.
- Live household audio/video/location/presence/behavior data collection and persistence are prohibited.
- Approved external egress for household data: none.
- High-frequency raw telemetry retention: none.
- Policy/approval/action/incident retention rules: unresolved; no operation may begin until minimization, access, expiry, erasure, and audit protections are adopted.
- Public/synthetic test artifacts must keep provenance and license/use information. They must not be mixed with future household runtime data.
- Offline/replay composition must not receive a camera/RTSP adapter, cloud client, operational network route, device executor, or runtime credential. A configuration flag or prompt instruction alone is insufficient separation.

## Failure, emergency, and recovery

- Independent kill switch/manual control: `NOT IMPLEMENTED`.
- Safety interlocks outside Agent control: `NOT IDENTIFIED`.
- Network/device/provider outage behavior: no operation; fail closed.
- Retry/deduplication/circuit-breaker limits: not adopted; no operational retry.
- Incident authority and evidence handling: `UNASSIGNED`.
- Recovery and re-enablement authority: `UNASSIGNED`; recovery never automatically restores operation.
- The Agent must not invent an emergency exception. Emergency behavior requires a separately adopted policy and independent controls.

## Verification required before any activation

For every proposed capability and risk class, preserve evidence for:

- simulator and offline behavior with no operational credentials;
- hostile/untrusted input failing to grant tools, policy, consent, or authority;
- identity, role, consent, scope, expiry, revocation, and conflict denial;
- unclassified action, wrong target, stale/unknown state, bound/rate/cost and egress denial;
- device offline, timeout, partial completion, duplicate request, late acknowledgement, restart, and replay safety;
- manual override, kill switch, independent interlock, rollback/compensation, incident response, and recovery;
- receipt integrity and separation of proposal, approval, acknowledgement, and observed outcome;
- privacy minimization, retention expiry, withdrawal, redaction, erasure, and deletion-failure handling.

Passing a lower class never activates a higher class. A written policy or passing unit test is not proof that OS, network, broker, credential, device, or human-authorization boundaries work.

Before activation, the adopted policy also needs a closed, machine-readable, schema-validated and version/hash-pinned form enforced by the trusted broker. This Markdown remains the human-readable authority record, not the enforcement engine.

## Adoption, activation, supersession, and audit

- Adoption requires a named/authenticated Policy Owner, required Project/Data authority, and affected-person consent for the policy's exact scope. Record version, effective time, review/expiry, and signatures or equivalent authenticated evidence.
- Activation is a separate prospective decision for exact environments and capability IDs after verification. It must update `PROJECT_STATE.md`; it never occurs merely because code exists or this draft is edited.
- Changes are explicit, versioned, prospective, and owner-authorized. Preserve which policy authorized each historical request/action; never reinterpret history as though a later policy applied.
- Restrictive emergency disablement may take effect immediately through an independent mechanism. Re-enablement requires the full adopted recovery process and never follows automatically from restart.
