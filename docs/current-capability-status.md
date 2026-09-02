# Current capability status

**Checkpoint:** hackathon demo recovery · **Runtime:** `OPERATE DISABLED` · **Production ready:** no

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

## Still missing before a credible hackathon handoff

- An independent teammate/platform clean-install and 90-second/CLI-fallback demo drill;
  one agent-run Windows clean clone/install/offline CLI path now works mechanically.
- Protected-group development plus untouched-test evidence for real indoor small-object
  detection; one synthetic fixture and one tiny YCB-V smoke target are insufficient.
- A tracker that survives occlusion and camera motion strongly enough for movement-event
  work; the current VOST target path was rejected on development.
- A product-level recorded indoor relation replay beyond project-generated artwork.
- One real teammate execution of the README quick start on their own platform.
- An adopted language-provider and data-egress policy, assigned credential owner,
  provider or local-model implementation, and runtime verification of failure fallback.
- A published wheel only if the team later decides installation without a Git checkout
  is a hackathon requirement. It is not required for the current repository demo.

## Deliberately not available

- Live camera, RTSP, background recording, multi-camera identity, face recognition, or
  audio capture.
- Durable household memory, private-data search, retention/deletion controls, cloud
  inference, device control, purchases, messages, or physical action.
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
action was added, and nothing was pushed.
