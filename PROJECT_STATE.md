# Whole Home Agent — Public Repository State

**Checkpoint:** `PUBLIC-B0-001`

**As of:** `2026-08-25 Asia/Taipei`

**Governance:** `PROPOSED — NOT ADOPTED`

**Runtime operation:** `OPERATE DISABLED`

This file is the live checkpoint for the clean public repository. It records current scope and evidence; it grants no household, data, device, account, or operational authority.

## Current direction

- Publish and collaborate on the smallest viable offline B0 semantic replay baseline.
- Keep B0 limited to synthetic or lawfully reusable public fixtures.
- Keep B1 as a proposal for prerecorded public/synthetic visual replay behind a narrow adapter.
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
| ADR 0001–0003 | `PROPOSED` | Design candidates, not automatically adopted requirements |
| B0 implementation and fixtures | `IMPLEMENTED` | A bounded semantic replay slice exists |
| MIT `LICENSE` | `SELECTED FOR PUBLIC RELEASE` | Applies to original repository code and documentation |

## Evidence envelope

- The public export contains the B0 package, synthetic fixtures, tests, architecture documents, and proposed governance only.
- It intentionally excludes prior private Git history, coursework/competition experiments, datasets, raw media, model weights, generated outputs, local databases, environment files, and credentials.
- Existing tests exercise semantic replay, provenance, idempotency, conflict/unknown handling, malformed input, and boundary restrictions.
- Local verification on 2026-08-25 used Python 3.12 in the existing isolated workspace environment: `23/23` unit tests passed and `compileall` passed.
- GitHub CI has not yet run for this public repository; configured jobs are not evidence until the remote workflow reports a result.
- Passing tests supports only the tested code, fixtures, interpreter, and environment. It does not support CV accuracy, household transfer, real-time performance, privacy compliance, production readiness, or physical truth.

## Recorded directions

| ID | Direction | Status |
|---|---|---|
| `PUB-DIR-001` | Create a separate clean public repository; do not expose or rewrite the private repository's history | Active |
| `PUB-DIR-002` | Keep `OPERATE` disabled until roles, consent, risk classification, safety boundaries, enforcement, and separate activation are complete | Active |
| `PUB-DIR-003` | Start from a minimal B0 baseline; separate data, control, action, authority, and physical outcome | Active |
| `PUB-DIR-004` | Use MIT for original public repository code/docs; review third-party artifacts separately | Active |

## Open gates and blockers

- Named project, policy, engineering, and data roles remain unassigned.
- The full B0 conformance, recovery, runtime-path, performance, and independent maintainer exercise gates are incomplete.
- No B1 video-source/perception adapter or frozen indoor evaluation set has been adopted.
- No household data class, person, room, camera, credential, endpoint, device, or capability is enrolled.
- Consent, retention, deletion, access, incident, kill-switch, and independent enforcement mechanisms do not exist.

## Next safe action

Review and improve the B0 semantic contracts and conformance evidence, or separately propose a B1 prerecorded public/synthetic video adapter and frozen indoor evaluation plan. Do not connect a live camera, process household data, add credentials, or implement device action under this checkpoint.
