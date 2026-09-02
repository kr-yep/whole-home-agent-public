# Current capability status

**Checkpoint:** M41 packaging pre-artifact stop · **Runtime:** `OPERATE DISABLED` · **Production ready:** no

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
- Receive deterministic relation-only prose plus a typed receipt from the same exact
  M38 context; malformed context or presenter failure produces fixed fallback prose and
  leaves the structured answer available.

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
- A clean installed-wheel receipt proving the new M40 presentation module and compact
  demo work outside the checkout. M41 stopped before artifact creation during default
  `uv` cache initialization, so this remains unverified.

## Deliberately not available

- Live camera, RTSP, background recording, multi-camera identity, face recognition, or
  audio capture.
- Durable household memory, private-data search, retention/deletion controls, cloud
  inference, device control, purchases, messages, or physical action.
- Any claim of 24/7 readiness, real-home accuracy, general home understanding, or
  safety-critical behavior.

These remain blocked by proposed governance, unassigned roles, absent consent and data
policy, and `OPERATE DISABLED`.

## Latest local milestone: M41 packaging pre-artifact stop

The [M41 result](evaluation/m41-release-candidate-packaging-v1.md) records the sole
exact-revision attempt. Source identity passed, but `uv build --offline` returned Windows
error 183 while initializing its default cache path. The path was observed as a directory
afterward, so the exact root cause is not claimed. Zero package artifacts were produced;
installation and the installed demo never started.

The disposable worktree and empty output/run directories were removed. No retry,
alternate cache, dependency change, provider, key, model, endpoint, request, or product
change was introduced. Public CI was not run, nothing was pushed, and `OPERATE` remains
disabled. The stopped result and unchanged code pass all 445 local regression tests;
the 321-file / 642-snapshot Git audit reports zero violations.
