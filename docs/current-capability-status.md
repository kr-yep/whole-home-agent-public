# Current capability status

**Checkpoint:** M39 local-first language boundary · **Runtime:** `OPERATE DISABLED` · **Production ready:** no

This page is updated with every milestone push so a teammate can see what is usable and
what is still missing without reconstructing the full experiment history.

## Usable now

- Install the public Python package from this repository on Python 3.11–3.14.
- Run deterministic B0 semantic fixtures and receive scoped, evidence-bound answers.
- Run one closed, project-owned, prerecorded synthetic key→bag→sofa replay locally.
- Use either compact JSON CLI output or the closed Streamlit demo; neither accepts an
  upload, camera, arbitrary path, chat prompt, credential, or action handle.
- Inspect top-level answer `subject_id`, status, location, epistemic state, replay scope,
  as-of sequence, claim IDs, and relation path.
- Rebuild the same B0 claim ledger/projection; the golden semantic SHA-256 remains
  `226d30a5b826720d607d0b9a29bf3dfb9f5429eeedbbd70ffd1ff23c21233c8f`.
- Run the public test/CI matrix and mechanical release audit.
- Use the teammate checker without false `uv.lock` failures from Git LF/CRLF checkout
  representation; exact revision, clean worktree, and committed blob identity remain
  fail-closed.
- Follow one exact Windows PowerShell or macOS/Linux teammate procedure for clone,
  locked install, offline receipt, 90-second presentation or CLI fallback, and guarded
  cleanup.
- Inspect the exact `whole-home-agent.location-context.v1` text packet that a future
  language presenter could receive. It is generated locally from the public answer and
  excludes media, evidence/run history, raw queries, credentials, and action handles.
- Inspect a machine-checked comparison that keeps deterministic local presentation as
  the default, treats API-key presence as credential only, and separates pure local
  deployment from a future local-first hybrid cloud option.

## Still missing before a credible hackathon handoff

- An independent teammate/platform clean-install and 90-second/CLI-fallback demo drill;
  one agent-run Windows clean clone/install/offline CLI path now works mechanically.
- Protected-group development plus untouched-test evidence for real indoor small-object
  detection; one synthetic fixture and one tiny YCB-V smoke target are insufficient.
- A tracker that survives occlusion and camera motion strongly enough for movement-event
  work; the current VOST target path was rejected on development.
- A product-level recorded indoor relation replay beyond project-generated artwork.
- Clear packaging/recovery evidence on each teammate platform.
- An adopted language-provider and data-egress policy, assigned credential owner,
  provider or local-model implementation, and runtime verification of failure fallback.

## Deliberately not available

- Live camera, RTSP, background recording, multi-camera identity, face recognition, or
  audio capture.
- Durable household memory, private-data search, retention/deletion controls, cloud
  inference, device control, purchases, messages, or physical action.
- Any claim of 24/7 readiness, real-home accuracy, general home understanding, or
  safety-critical behavior.

These remain blocked by proposed governance, unassigned roles, absent consent and data
policy, and `OPERATE DISABLED`.

## Latest local milestone: M39 language-presentation boundary

Added the [M39 decision](evaluation/m39-language-presentation-boundary-v1.md) and
[ADR 0021](adr/0021-keep-language-presentation-local-by-default.md). Three candidates
were checked against ten gates. The selected architecture always retains the existing
deterministic answer, permits a separately validated local model later, and keeps any
cloud text presenter blocked until explicit data/egress and runtime authority exists.

The decision classifies every M38 field, records why text can still expose private
household state, and defines future retention, credential, telemetry, timeout, failure,
and fallback constraints. It adds no provider, key, model, endpoint, or request. All 411
local regression tests and the 309-file / 618-snapshot public audit pass with zero
violations; public CI was not run, nothing was pushed, and `OPERATE` remains disabled.
