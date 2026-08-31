# Whole Home Agent — Public Repository State

**Checkpoint:** `PUBLIC-B1-M1-001`

**As of:** `2026-09-01 Asia/Taipei`

**Governance:** `PROPOSED — NOT ADOPTED`

**Runtime operation:** `OPERATE DISABLED`

This file is the live checkpoint for the clean public repository. It records current scope and evidence; it grants no household, data, device, account, or operational authority.

## Current direction

- Publish and collaborate on the smallest viable offline B0 semantic replay baseline.
- Keep B0 limited to synthetic or lawfully reusable public fixtures.
- Keep B1 as a proposal for prerecorded public/synthetic visual replay behind a narrow adapter.
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
| B1 candidate-source seam and run receipt | `IMPLEMENTED / VERIFIED WITH SYNTHETIC CONTRACT TESTS` | Generic finite source contract, provenance types, fail-closed run outcome, and B0 compatibility exist; no video/CV exists yet |
| `docs/b0-b1-architecture-plan.md` | `PROPOSED — NOT ADOPTED` | Smallest B0 → B1 boundary, quality scenarios, gates, and deferred complexity |
| B0 → B1 Archify diagrams | `VERIFIED RENDERING OF A PROPOSED DESIGN` | 9/9 showcase and visual delivery passed; this does not adopt or implement B1 |
| MIT `LICENSE` | `SELECTED FOR PUBLIC RELEASE` | Applies to original repository code and documentation |

## Evidence envelope

- The public export contains the B0 package, synthetic fixtures, tests, architecture documents, and proposed governance only.
- It intentionally excludes prior private Git history, coursework/competition experiments, datasets, raw media, model weights, generated outputs, local databases, environment files, and credentials.
- Existing tests exercise semantic replay, provenance, idempotency, conflict/unknown handling, malformed input, boundary restrictions, the generic candidate-source seam, and partial-source failure without a queryable session.
- Local verification on 2026-08-31 used Python 3.12.13 with bytecode writes disabled: `23/23` unit tests passed; this architecture-only change did not modify product source code.
- GitHub verified `kr-yep/whole-home-agent-public` as public with `main` as its default branch. Seed commit `21d057569073e7f2e16631780a8ab1150c2920f9` contains the clean release history.
- GitHub Actions run [32803963091](https://github.com/kr-yep/whole-home-agent-public/actions/runs/32803963091) completed successfully for the seed commit across configured Python 3.11–3.14 jobs.
- Archify v2.16.0 produced the proposed system and data-flow diagrams. Both passed 9/9 showcase checks with zero composition errors/warnings, desktop containment at 1440×900 through 2048×1320, and human inspection of light/dark captures. Exact source/artifact hashes and evidence limits are recorded in `docs/b0-b1-architecture-plan.md`.
- Passing tests supports only the tested code, fixtures, interpreter, and environment. It does not support CV accuracy, household transfer, real-time performance, privacy compliance, production readiness, or physical truth.

## Recorded directions

| ID | Direction | Status |
|---|---|---|
| `PUB-DIR-001` | Create a separate clean public repository; do not expose or rewrite the private repository's history | Active |
| `PUB-DIR-002` | Keep `OPERATE` disabled until roles, consent, risk classification, safety boundaries, enforcement, and separate activation are complete | Active |
| `PUB-DIR-003` | Start from a minimal B0 baseline; separate data, control, action, authority, and physical outcome | Active |
| `PUB-DIR-004` | Use MIT for original public repository code/docs; review third-party artifacts separately | Active |
| `PUB-DIR-005` | Keep B0 as the only claim-commit/query core; make prerecorded perception a replaceable candidate-producing adapter | Candidate-source seam implemented; prerecorded perception remains unimplemented |

## Open gates and blockers

- Named project, policy, engineering, and data roles remain unassigned.
- The full B0 conformance, recovery, runtime-path, performance, and independent maintainer exercise gates are incomplete.
- The B1 candidate-source seam is implemented under the explicit bounded implementation direction. No video decoder, perception adapter, frozen indoor media evaluation set, live source, or operational capability exists.
- No household data class, person, room, camera, credential, endpoint, device, or capability is enrolled.
- Consent, retention, deletion, access, incident, kill-switch, and independent enforcement mechanisms do not exist.

## Next safe action

Implement M2 only with D0 synthetic/generated prerecorded media: a closed manifest, deterministic media-time contract, synthetic replay, and motion-plus-periodic scheduling behind the candidate-source adapter. Do not connect a live camera, accept arbitrary media paths, process household data, add credentials, or implement device action under this checkpoint.
