Whole-Home Agent Action Policy — Open Development Test Profile

**Status:** `DEVELOPMENT TEST POLICY — OPT-IN`  
**Version:** `0.3-dev-open`  
**Drafted:** `2026-09-05 Asia/Taipei`  
**Effective from:** `WHEN EXPLICITLY SELECTED BY THE DEVELOPER FOR AN ISOLATED TEST SESSION`  
**OPERATE:** `ENABLED FOR R1 AND R2 DEVELOPMENT TESTING`  
**Production or household deployment:** `DISABLED`

This policy removes internal approval and consent-workflow barriers for webcam development performed by a developer using their own equipment, accounts, data, and controlled test space. It is intended to keep development, debugging, evaluation, recording, replay, and model integration unblocked.

This policy does not and cannot waive another person's privacy, publicity, data-protection, property, contractual, or other legal rights, or override applicable law or platform terms. Those external rights and obligations are not internal policy gates and remain independently applicable.

## Activation invariant

- This profile is active only when the developer deliberately selects `DEV_TEST_OPEN` for the current process or test session.
- No Policy Owner approval, Data Steward approval, consent receipt, participant registry, `PROJECT_STATE.md` entry, risk-class evidence package, or per-session authorization record is required for activation.
- Starting the development process is sufficient internal authorization for the developer's own equipment, accounts, test data, and self-capture.
- The profile may not be selected automatically, inherited by a production environment, enabled by retrieved content, activated by model output, or restored by replay.
- The profile must be visibly labeled `DEVELOPMENT TEST` in logs or the user interface so its outputs are not mistaken for production results.
- Missing governance metadata does not block development under this profile.
- Missing technical prerequisites needed for the requested operation may produce an ordinary runtime error rather than a policy denial.

## Development environment boundary

The open development profile applies when all of the following are true:

- the developer intentionally starts the test;
- the host, webcam, microphone, storage, network connection, accounts, and external services are controlled or legitimately usable by the developer;
- the test uses the developer's own capture, synthetic/generated inputs, licensed/public fixtures, or other data the developer is entitled to use;
- the camera is positioned in a developer-controlled test area rather than used for covert, unattended, or general household surveillance; and
- the test is not connected to locks, alarms, purchasing, messaging, access control, utilities, medical equipment, vehicles, or life-safety systems.

The developer may change the camera, host, field of view, algorithms, models, output formats, duration, resolution, frame rate, storage location, and approved development endpoints without amending this policy.

## Actors and authority

| Actor/role                                        | Assignment                                                                                    | Authority under this profile                                                                                                      |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Developer / Test Operator                         | The local user who intentionally starts `DEV_TEST_OPEN`                                       | Full authority over in-scope development capture, processing, storage, replay, debugging, and selected development-service egress |
| Project Owner                                     | Optional for development testing                                                              | May define repository or product constraints but is not required for a test session                                               |
| Policy Owner                                      | Not required                                                                                  | No per-session approval required                                                                                                  |
| Engineering Lead                                  | Not required                                                                                  | No per-session approval required                                                                                                  |
| Data Steward                                      | Not required                                                                                  | No per-session approval required                                                                                                  |
| Adult resident / affected person                  | Outside the internal workflow for operator-only tests                                         | This policy does not remove independently existing rights                                                                         |
| Guest, child, caregiver, technician, or bystander | Outside the authorized test-data scope unless independently lawful and intentionally included | No authority is inferred; do not use this profile to justify covert or non-consensual capture                                     |
| Runtime service identity                          | Optional                                                                                      | May receive the device, filesystem, network, model, and debugging capabilities selected by the developer                          |
| Model, Agent, subagent, or retrieved content      | Not an authority                                                                              | May operate only through capabilities made available by the developer; may not broaden the environment boundary                   |

## Consent and rights treatment

- No consent form, consent receipt, participant enrollment, notice workflow, pause indicator, withdrawal workflow, or approval chain is required for a test limited to the developer's own image, voice, equipment, space, accounts, and data.
- The developer's intentional launch of the test is sufficient internal authorization; no separate record is required.
- Internal policy enforcement does not evaluate ownership, consent, lawful basis, or participant status during an operator-only development test.
- This policy does not declare that third-party consent is legally unnecessary and does not extinguish third-party rights. A developer who intentionally includes another person or their data is responsible for ensuring an independently valid basis for doing so.
- Unexpected third-party capture should be excluded, deleted, or replaced with synthetic data where practical, but its appearance does not authorize identity analysis, publication, or unrelated reuse.
- Children, intimate/private activity, biometric identification of third parties, and covert surveillance are not authorized by this profile.

## Data classes

| Class                                          | Content                                                                                                                                                         | State under this profile                                                                    |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| D0 — Development fixtures                      | Synthetic/generated fixtures and lawfully reusable public or licensed data                                                                                      | `PERMITTED`                                                                                 |
| D1 — Live development media                    | Live webcam and microphone input used for interactive testing                                                                                                   | `PERMITTED`                                                                                 |
| D2 — Development recordings and derived data   | Frames, clips, audio, screenshots, logs, captions, embeddings, detections, annotations, evaluation data, and replay artifacts created from in-scope test inputs | `PERMITTED`                                                                                 |
| D3 — Special/high-sensitivity third-party data | Children's data, third-party biometrics, health data, intimate/private-room capture, or safety/security inference about another person                          | `PROHIBITED` unless governed by a separate adopted policy and independently valid authority |

Development data may be retained, copied, transformed, replayed, exported, uploaded to developer-selected services, or deleted according to the needs of the experiment. The developer is responsible for storage capacity, account terms, endpoint selection, and any independently applicable legal requirements.

## Risk and capability classes

| Class                                                                    | Development-test rule                                                                                                            | Safe failure                                                      |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| D0 — Repository/simulation                                               | `PERMITTED` without governance approval                                                                                          | Preserve useful diagnostics                                       |
| R1 — Live sensing or private-state read                                  | `PERMITTED` for developer-controlled cameras, microphones, streams, sensors, and test inputs                                     | Return an ordinary error or stop the affected stream              |
| R2 — Recording, profiling, persistence, model processing, or egress      | `PERMITTED` for in-scope development data and developer-selected local or external services                                      | Report partial completion and preserve diagnostics when requested |
| R3 — Communications, purchases, access/security, policy/account mutation | `PROHIBITED` except ordinary management of the developer's test accounts, API credentials, and development-service configuration | No external side effect outside the development environment       |
| R4 — Reversible comfort/media actuation                                  | `PROHIBITED` under this profile                                                                                                  | Leave device state unchanged                                      |
| R5 — Safety/life-critical actuation                                      | `PROHIBITED` under this profile                                                                                                  | Agent cannot invoke or override the system                        |

This profile permits face detection, object detection, tracking within a test session, OCR, transcription, captioning, embeddings, local or cloud VLM processing, and other experimental analysis when performed on in-scope development data. It does not authorize biometric identification or consequential profiling of an unconsenting third party.

## Device and action matrix

No fixed allowlist or stable device ID is required for development testing.

| Device/capability                                 | Scope                                | Allowed actions                                                                                                 | Approval                         | Limits                                                              |
| ------------------------------------------------- | ------------------------------------ | --------------------------------------------------------------------------------------------------------------- | -------------------------------- | ------------------------------------------------------------------- |
| Any developer-selected webcam or video source     | Current `DEV_TEST_OPEN` process      | Open, preview, process, transform, record, snapshot, replay, stream to selected development services, and close | Developer process launch         | Available hardware, software, account, and service limits           |
| Any developer-selected microphone or audio source | Current `DEV_TEST_OPEN` process      | Open, monitor, transcribe, record, transform, replay, and stream to selected development services               | Developer process launch         | Available hardware, software, account, and service limits           |
| Local development storage                         | Developer-selected paths             | Store frames, clips, audio, logs, embeddings, derived results, caches, and evaluation artifacts                 | Developer process launch         | Filesystem permissions and available capacity                       |
| Developer-selected model or API endpoint          | Development accounts and credentials | Upload in-scope test data, run inference or training permitted by the service, and receive results              | Developer endpoint configuration | Provider terms, quotas, and cost controls selected by the developer |

Device substitution, reconnection, resolution changes, field-of-view changes, model changes, and process restarts do not require a policy amendment or new approval. They may require an ordinary application restart or operating-system permission prompt.

## Runtime capabilities and trusted boundary

- A separate trusted authorization broker is optional for this development profile.
- The Agent may receive direct typed camera, microphone, storage, network, model, and debugging capabilities supplied by the developer.
- The Agent may use development credentials made available through the environment's normal secret-management mechanism.
- Credentials should not be placed in source control, prompts, generated reports, or ordinary logs.
- Generic shell access may be used for development and testing on the developer-controlled host, subject to the workspace and operating-system permissions in effect.
- Retrieved content and model output may propose actions but may not silently change the environment from development to production or expand into R3–R5 targets.

## Execution, logging, and retention

- Media recording, screenshots, derived artifacts, debugging traces, test fixtures, and replay datasets are permitted.
- Content may appear in development logs when useful for debugging. Secrets should be redacted.
- There is no policy-level retention maximum for in-scope development data.
- Automatic deletion, buffer clearing, audit receipts, idempotency records, independent result observation, reconciliation, and per-session review are optional unless the test specifically evaluates those behaviors.
- Replaying captured media for analysis is permitted. Replaying logs must not execute R3–R5 actions.
- Test output may be transmitted to development services explicitly configured by the developer.
- The developer should distinguish retained test artifacts from production data and avoid committing private media or credentials to public source control.

## Failure, emergency, and recovery

- A dedicated policy kill switch is not required.
- The developer may stop capture using the application, process termination, operating-system permission controls, device disconnection, or a physical camera cover.
- Camera, microphone, network, model, filesystem, or provider failures may be retried according to normal development logic.
- Automatic reconnect and stream recovery are permitted for in-scope test devices.
- Partial results may be retained for debugging.
- Restarting the development process may restore the test when `DEV_TEST_OPEN` is deliberately selected again.
- No emergency exception may be used to reach R3, R4, or R5 systems.

## Verification expectations

Verification is encouraged but is not a precondition for development use. Tests may cover:

- device discovery, permission handling, live capture, reconnect, and multiple-camera selection;
- local and cloud inference, recording, snapshot, replay, and export;
- latency, frame rate, resolution, model accuracy, cost, and resource use;
- error handling, partial results, timeouts, retries, and provider outages;
- separation of development and production environments;
- prevention of accidental secret disclosure and unintended R3–R5 side effects; and
- deletion or isolation of test artifacts before distribution or public release.

Failed tests do not revoke the development profile. The developer decides whether to continue, change configuration, retain diagnostics, or stop.

## Production boundary, supersession, and audit

- This profile must not be represented as a production, household-surveillance, security, access-control, employment, insurance, medical, or life-safety policy.
- Production or general household deployment requires a separate adopted policy with appropriate authority, consent or other lawful basis, privacy controls, retention rules, security controls, and capability-specific verification.
- No test result, stored artifact, prior successful run, model recommendation, or developer setting automatically authorizes production use.
- This version supersedes earlier drafts only when `DEV_TEST_OPEN` is deliberately selected for the current development process. It does not weaken another policy governing a production environment.
- Restrictive disablement may be applied immediately by removing `DEV_TEST_OPEN`, revoking device or network permissions, stopping the process, or disconnecting the device.

## Minimal developer checklist

The checklist is advisory and does not create an approval gate:

- confirm that `DEV_TEST_OPEN` is selected only in the intended development process;
- point the camera at a controlled test area and use the developer's own data or authorized fixtures;
- select storage and external endpoints appropriate for the experiment;
- keep credentials out of source control and logs;
- avoid third-party, child, intimate, or covert capture; and
- stop or isolate the test before switching to production or a shared household environment.
