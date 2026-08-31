# Whole Home Agent — Public Repository State

**Checkpoint:** `PUBLIC-B1-M6-001`

**As of:** `2026-09-01 Asia/Taipei`

**Governance:** `PROPOSED — NOT ADOPTED`

**Runtime operation:** `OPERATE DISABLED`

This file is the live checkpoint for the clean public repository. It records current scope and evidence; it grants no household, data, device, account, or operational authority.

## Current direction

- Publish and collaborate on the smallest viable offline B0 semantic replay baseline plus one bounded B1 prerecorded replay.
- Keep B0/B1 inputs limited to synthetic or lawfully reusable public fixtures.
- Keep B1 limited to a fixed, hash-pinned, prerecorded project-generated clip behind a narrow adapter.
- Reuse the implemented B0 `ClaimCandidate` → commit → projection → query path as the only semantic state path for B1.
- Exclude live/private sensing and all physical or external action from the current scope.
- Do not assume a graph, Memory Core, multi-agent runtime, or durable database is necessary.

## Authority and roles

| Role | Assignment | Current authority |
|---|---|---|
| Repository owner | GitHub account `kr-yep` controls repository settings | Repository administration only; not household or policy authority |
| Project Owner | `UNASSIGNED` | None until explicitly assigned |
| Policy Owner | `UNASSIGNED` | None until explicitly assigned |
| Engineering Lead | `UNASSIGNED` | None until explicitly assigned |
| Data Steward | `UNASSIGNED` | None until explicitly assigned |
| Household roles / affected persons | `UNDEFINED` | No consent or operational authority exists |
| Runtime identity | `NOT CREATED` | No capability or credential exists |

## Document status

| Artifact | Status | Meaning |
|---|---|---|
| `AGENTS.md` | `PROPOSED` | Conservative interim repository instructions |
| `ACTION_POLICY.md` | `PROPOSED — NOT ADOPTED` | All sensing, private-data, egress, device, and physical operation disabled |
| ADR 0001–0004 | `PROPOSED` | Design candidates, not automatically adopted requirements |
| B0 implementation and fixtures | `IMPLEMENTED / VERIFIED IN DECLARED TEST ENVELOPE` | A bounded semantic replay slice exists; its frozen golden semantic hash is unchanged |
| B1 candidate-source seam and run receipt | `IMPLEMENTED / VERIFIED WITH SYNTHETIC CONTRACT TESTS` | Generic finite source contract, provenance types, fail-closed run outcome, and B0 compatibility remain the sole semantic admission path used by the later prerecorded adapter |
| B1 generated-video manifest, PTS decoder, and scheduler | `IMPLEMENTED / VERIFIED ON ONE SYNTHETIC REPLAY` | Hash-pinned allowlisted H.264 source revision 2, exact PTS/time-base decode, and motion-plus-periodic frame selection feed the later bounded perception source; revision 1 remains in Git history |
| B1 perception/tracking/evaluation baseline | `IMPLEMENTED / VERIFIED ON ONE SYNTHETIC REPLAY` | Canonical detections, test-only annotation ceiling, RGB pixel smoke detector, clip-local IoU tracker, fixed quality/cost evaluator, and hash-pinned RF-DETR translation seam exist; no real indoor model evidence exists |
| B1 binding/relation/query slice | `IMPLEMENTED / VERIFIED ON ONE SYNTHETIC REPLAY` | One-instance binding, conservative containment/zone assertion and retraction rules, typed abstentions, estimated candidates through the unchanged committer, relation evaluation, and evidence-traceable `key → bag → sofa` query exist; no real indoor transfer evidence exists |
| B1 CLI and Streamlit presentation | `IMPLEMENTED / VERIFIED ON ONE SYNTHETIC REPLAY` | A closed composition/presentation boundary exposes the fixed clip, scoped answer, evidence, abstentions, metrics, diagnostics, and receipt; it accepts no upload, camera, arbitrary path, free-form query, credential, or action handle |
| Python package distribution | `IMPLEMENTED / VERIFIED BY LOCAL CLEAN INSTALL` | The wheel contains only the fixed D0 replay, its configs, and generator provenance; a fresh Python 3.12 environment ran the CLI from outside the checkout |
| `docs/b0-b1-architecture-plan.md` | `PROPOSED — NOT ADOPTED` | Smallest B0 → B1 boundary, quality scenarios, gates, and deferred complexity |
| B0 → B1 Archify diagrams | `VERIFIED RENDERING OF THE IMPLEMENTED BOUNDED SLICE` | 9/9 showcase and visual delivery passed; rendering evidence does not adopt governance or expand the implementation envelope |
| MIT `LICENSE` | `SELECTED FOR PUBLIC RELEASE` | Applies to original repository code and documentation |

## Evidence envelope

- The public export contains the B0 package, synthetic semantic fixtures, one project-generated CC0 prerecorded clip with manifests/annotations, B1 adapters, tests, presentation code, architecture documents, and proposed governance.
- It intentionally excludes prior private Git history, coursework/competition experiments, third-party datasets, household/private media, model weights, run outputs, local databases, environment files, and credentials.
- Existing tests exercise semantic replay, provenance, idempotency, conflict/unknown handling, malformed input, boundary restrictions, media allowlisting and timing, detector/tracker/evaluator contracts, conservative relation inference, partial-source failure without a queryable session, and the fixed CLI/Streamlit presentation.
- Local verification on 2026-09-01 used Python 3.12.13 with bytecode writes disabled: `72/72` unit, contract, integration, audit, CLI, and Streamlit smoke tests passed. The frozen B0 semantic hash remained `226d30a5b826720d607d0b9a29bf3dfb9f5429eeedbbd70ffd1ff23c21233c8f`.
- Source revision 2 is an 80-frame H.264/yuv420p generated replay with SHA-256 `b9cc79476d77f8d45acd1803c924de73914ffc4790f4da271f77cc8d4742eb43`. It was versioned because revision 1's encoding failed Chromium playback. Two consecutive local generations matched; browser QA then showed duration 8 seconds, ready state 4, scoped revision-2 content, and zero console errors.
- The source-revision-2 RGB smoke baseline measured AP50/key recall `1.0`, mAP50:95 about `0.7293`, zero false positives, zero clip-local ID switches/fragmentations, relation event F1 `1.0`, and the expected two-step answer. These are generated-artwork measurements only.
- `uv build` produced a source archive and universal wheel. A new Python 3.12 environment installed `whole_home_agent-0.1.0-py3-none-any.whl[demo]`, then ran `demo-recorded` outside the checkout with a `COMPLETE` receipt, two accepted estimated claims, and `FOUND sofa` under `source:b1-key-bag-sofa@2`.
- GitHub verified `kr-yep/whole-home-agent-public` as public with `main` as its default branch. Seed commit `21d057569073e7f2e16631780a8ab1150c2920f9` contains the clean release history.
- GitHub Actions run [32803963091](https://github.com/kr-yep/whole-home-agent-public/actions/runs/32803963091) completed successfully for the seed commit across configured Python 3.11–3.14 jobs.
- M2 through the first M6 push had green B0 jobs but failed the Linux video/demo jobs because Windows-generated annotation bytes used CRLF before Git normalized them to LF, invalidating the manifest hash in CI. Run [33447377312](https://github.com/kr-yep/whole-home-agent-public/actions/runs/33447377312) exposed the same failure after the M6 push. The generator now emits canonical LF, and a regression test checks both generated text artifacts.
- GitHub Actions run [33447921546](https://github.com/kr-yep/whole-home-agent-public/actions/runs/33447921546) completed successfully for canonical-LF commit `4117e933b4b6076a5cda9130f61ea09ec998934b`: Python 3.11–3.14 B0 jobs, the prerecorded-video contract job, and the closed-demo job all passed.
- Archify v2.16.0 produced the proposed system and data-flow diagrams. Both passed 9/9 showcase checks with zero composition errors/warnings, desktop containment at 1440×900 through 2048×1320, and human inspection of light/dark captures. Exact source/artifact hashes and evidence limits are recorded in `docs/b0-b1-architecture-plan.md`.
- Passing tests supports only the tested code, fixtures, interpreter, and environment. It does not support CV accuracy, household transfer, real-time performance, privacy compliance, production readiness, or physical truth.

## Recorded directions

| ID | Direction | Status |
|---|---|---|
| `PUB-DIR-001` | Create a separate clean public repository; do not expose or rewrite the private repository's history | Active |
| `PUB-DIR-002` | Keep `OPERATE` disabled until roles, consent, risk classification, safety boundaries, enforcement, and separate activation are complete | Active |
| `PUB-DIR-003` | Start from a minimal B0 baseline; separate data, control, action, authority, and physical outcome | Active |
| `PUB-DIR-004` | Use MIT for original public repository code/docs; review third-party artifacts separately | Active |
| `PUB-DIR-005` | Keep B0 as the only claim-commit/query core; make prerecorded perception a replaceable candidate-producing adapter | Implemented and locally verified on one project-generated synthetic replay; no real indoor transfer claim |
| `PUB-DIR-006` | Deliver a reproducible public demo, installable package, implemented-code diagrams, and release audit without widening sensing or action scope | Implemented, locally verified, and verified by public CI within the recorded envelope |

## Open gates and blockers

- Named project, policy, engineering, and data roles remain unassigned.
- The full B0 conformance, recovery, runtime-path, performance, and independent maintainer exercise gates are incomplete.
- The B1 candidate-source seam, one project-generated video/decoder/scheduler slice, a synthetic-only detector/tracker/evaluator, conservative binding/relation/query rules, and a closed CLI/Streamlit presentation are implemented under the explicit bounded implementation direction. The RGB and relation results measure the generated artwork only. The annotation oracle is test-only. RF-DETR has only a hash-pinned adapter translation contract; no real checkpoint was downloaded or benchmarked. No frozen real indoor evaluation set, live source, or operational capability exists.
- No household data class, person, room, camera, credential, endpoint, device, or capability is enrolled.
- Consent, retention, deletion, access, incident, kill-switch, and independent enforcement mechanisms do not exist.

## Next safe action

Establish a separately licensed, frozen indoor prerecorded D0 evaluation set split by source video/scene, then run paired real-detector baselines under the recorded quality/cost gate. Do not add live capture, private household data, cloud egress, credentials, device control, or action capability; each requires its own authority and activation path.
