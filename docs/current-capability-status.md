# Current capability status

**Checkpoint:** M44 packaging normal stop · **Runtime:** `OPERATE DISABLED` · **Production ready:** no

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
  `uv` cache initialization; M42 only proved that uv accepts an explicit path, not that
  it creates or can use it. M43 proves a caller-created empty cache is locally writable
  and selected by uv. M44 reached a partial sdist, but output decoding broke the runner,
  no wheel existed, and the sdist lacked required `uv.lock`; packaging remains unverified.

## Deliberately not available

- Live camera, RTSP, background recording, multi-camera identity, face recognition, or
  audio capture.
- Durable household memory, private-data search, retention/deletion controls, cloud
  inference, device control, purchases, messages, or physical action.
- Any claim of 24/7 readiness, real-home accuracy, general home understanding, or
  safety-critical behavior.

These remain blocked by proposed governance, unassigned roles, absent consent and data
policy, and `OPERATE DISABLED`.

## Latest local milestone: M44 explicit-cache packaging stop

The [M44 result](evaluation/m44-explicit-cache-packaging-v1.md) preserves its sole
package attempt exactly. The build subprocess started with the frozen caller-created
cache, but implicit CP950 decoding failed before the runner could retain a receipt.
Read-only inspection found one partial source archive containing the correct M40 module,
no wheel, and no required `uv.lock`. Install and demo never started.

The 628 MB copied cache, detached worktree, partial archive, and output directories were
removed. No dependency change, provider, key, model, endpoint, request, private media,
or product change was introduced. Public CI was not run, nothing was pushed, and
`OPERATE` remains disabled. A future runner/content repair and any new package attempt
must be separately frozen. All 485 local regression tests pass with 30 optional skips;
the 340-file / 680-snapshot Git audit reports zero violations.
