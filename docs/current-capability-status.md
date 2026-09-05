# Current capability status

## Current integration checkpoint — 2026-09-05

Local hardening, character and ablation verification: 570 tests passed in the locked demo environment,
zero skips. Eight added regression tests cover malformed HTTP input, cross-origin
commands, negation/questions, temperature parsing, per-device operations, and a
temporary local HTTP query/mock-actuation round trip. No real endpoint or device
was tested. These edits are local and have not been committed or pushed.

V2 ablation completed 24 synthetic clips, 60 development and 180 evaluation runs.
Burst + confirmation passed the fixed synthetic quality/cost criteria: 27.5% fewer
detector calls and 25.0% paired replay-time saving. It remains experimental, not a
production default or proof of indoor readiness. See
[v2 results](evaluation/perception-ablation-v2.md).

Teammate changes from main `40dab4b` and character branch `4fec8b5` are now
integrated locally: asset help, Rem/Nailong character registry, 3D/flat renderers,
and character-aware prose. Local error handling, mock labels, initialization,
fallback avatar and ablations remain intact. Node controller checks passed for
failed loads, preserving the old avatar, stale async loads and invalid IDs.
The asset inventory reports all three character artwork entries missing; no
download, real-artwork animation verification or browser visual QA was performed.

Four perception/memory ablations plus baseline completed 15 synthetic replays.
The existing motion scheduler is not compatible with the temporal confirmation
defaults on this clip; it saved detector calls but lost both events. Chain memory
remains necessary for the demonstrated hidden-key answer. Tracking/confirmation
removal has not been validated on negative indoor footage. See the
[ablation report](evaluation/perception-ablation-v1.md); runtime defaults are unchanged.

The checkout now includes a Web UI, deterministic persona, browser TTS, and four
mock devices. Start with the README's Web command. Missing Live2D assets show a
house avatar. The Home Assistant adapter exists but is not selected by either UI;
setting HASS variables alone does not enable it. Real device integration and indoor
perception remain unverified. The historical checkpoint below predates these additions.

The new component benchmark measures actual outcomes and latency on temporary
synthetic memory and mock devices. It does not compare real LLMs or measure user
preference. The v2 claims of guaranteed zero hallucinations have been withdrawn.

**Checkpoint:** offline memory + bounded questions · **Runtime:** `OPERATE DISABLED` · **Production ready:** no

This page is updated with every milestone push so a teammate can see what is usable and
what is still missing without reconstructing the full experiment history.

## Usable now

- Clone the repository and run its locked demo environment on Python 3.11–3.14.
- Run deterministic B0 semantic fixtures and receive scoped, evidence-bound answers.
- Run one closed, project-owned, prerecorded synthetic key→bag→sofa replay locally.
- Use either compact JSON CLI output or the closed Streamlit demo; neither accepts an
  upload, camera, arbitrary path, chat prompt, credential, or action handle.
- Inspect top-level answer `subject_id`, status, location, epistemic state, replay scope,
  as-of sequence, claim IDs, and relation path.
- Rebuild the same B0 claim ledger/projection; the golden semantic SHA-256 remains
  `226d30a5b826720d607d0b9a29bf3dfb9f5429eeedbbd70ffd1ff23c21233c8f`.
- Run the public test/CI matrix and mechanical release audit.
- Use one cross-platform `uv run --frozen --extra demo ...` path for both the compact CLI
  and Streamlit UI.
- Inspect the exact `whole-home-agent.location-context.v1` text packet that a future
  language presenter could receive. It is generated locally from the public answer and
  excludes media, evidence/run history, raw queries, credentials, and action handles.
- Inspect a machine-checked comparison that keeps deterministic local presentation as
  the default, treats API-key presence as credential only, and separates pure local
  deployment from a future local-first hybrid cloud option.
- Receive deterministic relation-only prose plus a typed receipt from the same exact
  M38 context; malformed context or presenter failure produces fixed fallback prose and
  leaves the structured answer available.
- Explicitly archive a completed synthetic/public D0 replay in SQLite, reopen it in a
  second process, verify its hashes, rebuild the projection, and query it without
  retaining video, frames, question text, answer prose, or credentials.
- Ask where an item is, whether it is at a proposed place, or what a container/zone
  holds. The UI exposes the known vocabulary; deterministic parsing runs first and an
  optional translator can return only a closed query over existing entity IDs.
- Optionally present minimized text through an explicitly selected `localhost`, literal
  loopback, or existing literal CGNAT/tailnet OpenAI-compatible profile. Deterministic
  output remains the default; redirects, ambient proxies and automatic retries are absent.
- Use the calibrated D0 restriction profile: `localhost` is accepted, provider-specific
  reasoning fields are not forced, cold-start timeout may be configured up to 120 seconds,
  and malformed numeric environment settings degrade to deterministic output.
- Run a separate local-memory Streamlit page while retaining the original closed demo.

## Still missing before a credible hackathon handoff

- An independent teammate/platform clean-install and 90-second/CLI-fallback demo drill;
  one agent-run Windows clean clone/install/offline CLI path now works mechanically.
- Protected-group development plus untouched-test evidence for real indoor small-object
  detection; one synthetic fixture and one tiny YCB-V smoke target are insufficient.
- A tracker that survives occlusion and camera motion strongly enough for movement-event
  work; the current VOST target path was rejected on development.
- A product-level recorded indoor relation replay beyond project-generated artwork.
- One real teammate execution of the README quick start on their own platform.
- A decision for public-cloud language egress, including exact sent data, credential
  owner, provider retention review and cost bounds.
- Retention, deletion, access control, migration, backup, concurrency, and capacity
  requirements for any future real household memory.
- A published wheel only if the team later decides installation without a Git checkout
  is a hackathon requirement. It is not required for the current repository demo.

## Deliberately not available

- Live camera, RTSP, background recording, multi-camera identity, face recognition, or
  audio capture.
- Durable household memory, private-data search, retention/deletion controls, cloud
  inference, device control, purchases, messages, or physical action.
- Any assumption that an API key authorizes public-cloud or private-household egress;
  current real-endpoint tests remain unperformed.
- Any claim of 24/7 readiness, real-home accuracy, general home understanding, or
  safety-critical behavior.

These remain blocked by proposed governance, unassigned roles, absent consent and data
policy, and `OPERATE DISABLED`.

## Latest local verification: repository checkout demo

At local revision `c28fbdb`, a clean detached checkout synchronized the locked `demo`
extra into a new Python 3.12 environment in 2.47 seconds using an existing workspace
dependency cache. All seven public-demo tests passed. The installed project command then
returned `COMPLETE`, `FOUND`, subject `key`, location `sofa`, two relation steps,
`PRESENTED`, and `OPERATE DISABLED`.

Codex could not use the normal AppData uv cache because its sandbox service identity has
no access to that user directory; this is a local sandbox restriction, not a repository
failure. Public CI already uses the normal `uv sync --frozen` path. M41–M44 remain
historical packaging diagnostics and no longer block the Git-checkout hackathon demo.
After aligning the remaining historical lock checks with Git-blob identity, all 485
tests also pass from the normal Windows CRLF checkout. The public audit scanned 340
files / 680 snapshots with zero violations. No provider, key, private media, device, or
action was added in that recovery checkpoint.

## Latest local verification: offline memory slice

Restriction ablation v1 passed `55` focused tests with four optional video/UI skips in
the minimal runner. The complete suite ran `518` tests with 33 optional dependency skips,
and the staged public audit passed across 352 files / 704 snapshots with zero violations.
The run used fake model responses and no real endpoint, camera, household data, device,
or action. Details and retained boundaries are in
[`restriction-ablation-v1.md`](evaluation/restriction-ablation-v1.md).

Python 3.12.13 passed `16/16` focused tests and `501/501` full-regression tests. The
staged public audit scanned 349 files / 698 index-and-worktree snapshots with zero
violations and `operate_enabled: false`. Coverage includes SQLite restart/rebuild,
identical-write idempotency, identity conflict, corruption, missing-store behavior,
query minimization, Chinese/English parsing, hostile questions, loopback-only endpoint
validation, minimized request content, sanitized fallback, two-process CLI use, and the
separate Streamlit interaction. This remains synthetic/public D0 implementation
evidence only; teammates have not tested a real indoor recording, real local model,
cloud provider, or live camera. Public CI for this checkpoint is still pending.
