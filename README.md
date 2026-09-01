# Whole Home Agent

> **Current milestone:** `B1 — offline replay + bounded public perception gates`
>
> **Status:** `NOT PRODUCTION` · `OPERATE DISABLED`
> **Allowed data:** included generated fixtures plus separately downloaded, licensed D0 public data

Whole Home Agent is an evidence-bound prototype for remembering how small objects and containers move through a space. The current public demo analyzes one generated video and answers:

```text
key approaches bag → key disappears with supporting context
bag moves → bag settles at sofa
query(key) → “the key may be in the bag at the sofa”
```

The answer is an `estimated` result scoped to that replay. It is not a claim about a real home.

## Current handoff status

Updated with every milestone push. See the detailed
[capability status](docs/current-capability-status.md).

**Usable now:** clean local Python install; deterministic B0 semantic replay; one closed,
project-owned prerecorded synthetic key→bag→sofa demo through JSON CLI or Streamlit;
traceable scoped answers with explicit top-level query `subject_id`; automated public CI.

**Still missing:** a teammate clean-install/demo drill; convincing protected-group real
indoor small-object gain; robust tracking under occlusion/camera motion; live camera and
multi-camera support; durable household memory/retention; assigned policy/data roles,
consent, and any operational activation. Live/private sensing and actions remain blocked.

**Latest milestone (M35):** repository-only scoring selects exact Git-blob SHA-256 plus
exact revision and clean-worktree checks as the stable identity for versioned text. Raw
checkout hash becomes diagnostic only; canonical-LF fallback is rejected. M34 remains a
normal STOP and was not rerun. M36 may harden only the checker and focused tests.

## What works today

- hash-pinned, project-generated 80-frame MP4 replay with exact annotations;
- a separate three-group, 18-image project-generated D1 oracle substrate;
- PTS-aware PyAV decoding and optional motion-plus-periodic scheduling;
- a deterministic RGB smoke detector for the generated artwork;
- a hash-pinned RF-DETR Nano/Small offline adapter with sparse COCO-ID validation;
- a Safetensors-only D-FINE Small qualification adapter with dense COCO-ID validation;
- clip-local IoU tracking and one-instance manifest binding;
- conservative containment/location rules with explicit abstention behavior;
- the unchanged B0 claim committer, relation projection, and scoped query path;
- fixed AP, event, answer, latency, FPS, dropped-frame, and VRAM reporting;
- a frozen, source-video-split VISOR indoor screen with hash-pinned local assets;
- paired SSDLite320 and RetinaNet-FPN detector adapters with no implicit download;
- a frozen VOST consecutive-frame motion screen with range-only acquisition;
- development-only scheduler selection and paired full-frame/FPN cost evidence;
- an explicit VOST bottle mask-to-box target/tracking gate that stops before movement
  candidates when the observation path is too weak;
- JSON CLI and a local Streamlit presentation;
- automated B0 tests on Python 3.11–3.14 plus locked B1/demo jobs.

On the included browser-compatible H.264 synthetic clip, the current RGB baseline measures AP50 `1.0`, mAP50:95 about `0.7293`, key recall `1.0`, zero false positives, event F1 `1.0`, and the final expected answer. The clip-local tracker records zero ID switches and zero fragmentations on this one easy fixture. These numbers apply only to this generated artwork and do not establish indoor accuracy, real-time operation, or 24/7 readiness.

On the separately downloaded VISOR screen, RetinaNet-FPN improved validation
recall@0.5 from `14.3%` to `25.0%` over SSDLite320 and found `1/3` validation
targets occupying 0.1–1% of the frame versus `0/3`. It used about `393.3 MiB` peak
VRAM and `71.7 ms` detector p95, versus `85.7 MiB` and `47.4 ms`. The first frozen
test improved overall recall from `14.3%` to `39.3%`, but its only small target was
missed by both models. See the [full evidence limits and gate](docs/evaluation/visor-screen-v1.md).

On a separately downloaded VOST consecutive-frame screen, the frozen
motion-plus-periodic scheduler reduced validation RetinaNet-FPN calls from `136` to `52`
(`61.8%`) while selecting `40/41` annotated mask changes within the changed frame or one
following 5 fps frame (`97.6%`). Detector p95 was `65.15 ms`, scheduler p95 `0.58 ms`,
and peak VRAM about `352.2 MiB`. Exact-frame coverage was only `43.9%`, and VOST is an
egocentric camera-motion stress case, so this is scheduling evidence—not proof that the
system identified or understood a moved object. See the
[VOST motion gate](docs/evaluation/vost-motion-screen-v1.md).

A separate target-aware development gate then tested whether those scheduled calls
contained usable observations. On 51 frames of `3518_unscrew_bottle`, full-frame
RetinaNet recall@0.5 was only `19.6%`; the clip-local tracker recorded five ID switches
and four fragmentations. Scheduled target-event coverage was `20.5%`, retaining `72.7%`
of full-frame target-event coverage while avoiding `49.0%` of calls. The candidate was
rejected on development, so the reserved validation sequence was not run and no
movement-candidate layer was added. See the
[target-tracking gate](docs/evaluation/vost-target-track-screen-v1.md).

One later RF-DETR Small development screen raised same-frame target matches from
`10/51` to `25/51`, measured `49.78 ms` detector p95 and about `143.0 MiB` peak
allocated VRAM, but still missed the frozen `0.60` recall gate (`25/51 = 0.4902`). It
was stopped without a retry or reserved validation. These are finite egocentric VOST
results, not a general small-object, indoor, fixed-camera, or real-time claim. See the
[M12 evidence report](docs/evaluation/vost-m12-rfdetr-small-v1.md).

A subsequent D-FINE Small engineering preflight used only one generated in-memory RGB
input. Its 51-call p95 was `58.81 ms`, peak allocated VRAM was about `99.7 MiB`, and the
canonical output was deterministic, but the checkpoint is a community conversion with
no verified parity to the author artifact. It therefore passed engineering compatibility
and was stopped before VOST rather than treated as accuracy evidence. See the
[M13 evidence report](docs/evaluation/m13-dfine-small-synthetic-v1.md).

A no-media M14 review then compared exactly D-FINE Medium and RT-DETRv2 Small using
official primary evidence. D-FINE Medium improves over D-FINE Small on generic COCO,
but neither candidate supplies a material same-protocol prior over the RF-DETR Small
path that already failed the target development gate. The current off-the-shelf model
tournament is therefore stopped; no new model or media was loaded. See the
[M14 evidence report](docs/evaluation/m14-detector-scientific-priority-v1.md).

M15 then checked exactly Home Action Genome, CAD-120, and Watch-n-Patch using official
pages, papers, terms, and endpoint metadata without downloading media. No candidate
passed every frozen localization, rights, acquisition, split, manifest, and bounded-cost
gate. The project therefore selected none and pivoted to proving a no-media target-label
oracle before generating or acquiring data. See the
[M15 evidence report](docs/evaluation/m15-target-domain-substrate-v1.md).

M16 implemented that no-media oracle as a thin scope/validation layer around the existing
quality evaluator. A synthetic semantic fixture now proves exact perfect, empty,
duplicate, wrong-class, bad-localization, negative-frame, unknown, identity-conflict, and
source-group leakage behavior. This validates scoring semantics only; no image, model,
training, or transfer result exists. See the
[M16 evidence report](docs/evaluation/m16-target-label-oracle-feasibility-v1.md).

M17 then compared the existing vector renderer, Blender headless 3D, and Kubric with
licensed assets against frozen D1, provenance, split, delivery, storage, and dependency
gates. Only the existing project-owned renderer passed every gate. Blender and Kubric
remain possible later realism routes, but their bounded exact integrations were not
established here. M17 installed nothing and generated no media. See the
[M17 evidence report](docs/evaluation/m17-generation-strategy-reality-gate-v1.md).

M18 used that route to generate a deliberately tiny D1 substrate: three protected
development/validation/test groups, 18 PNG/annotation pairs, six reference transitions,
and explicit visible/truncated/occluded/absent/unknown cases. Two clean generations
matched every committed byte, the output stayed at 103,957 bytes, and the old golden
replay was unchanged. This proves data mechanics, not detector transfer. See the
[M18 evidence report](docs/evaluation/m18-vector-d1-slice-v1.md).

M19 then compared GMU Kitchens, HomebrewedDB, and YCB-Video without downloading data.
GMU's official dataset route is no longer available. HB and YCB-V both pass through the
current BOP distribution; the final frozen cost tie-break selects only YCB-V's 660 MB
BOP'19 subset for one acquisition and D1 translation slice. No small target or detector
gain has yet been observed. See the
[M19 evidence report](docs/evaluation/m19-real-transfer-oracle-reality-gate-v1.md).

M20 downloaded those two exact archives into ignored local storage and verified their
immutable sizes and SHA-256 values. It then stopped before extraction: the base archive
uses `ycbv/`, while the test archive uses `test/`, contradicting M20's frozen single-root
assumption. No real annotation or image was read. See the
[M20 evidence report](docs/evaluation/m20-ycbv-bop19-acquisition-translation-v1.md).

M21 repaired only that mapping and passed archive identity, complete ZIP-header safety,
and destination-collision checks. The unchanged real annotation selector then found no
same-object/same-scene pair satisfying both the 0.1–1% visible-positive and complete
class-absent requirements, so it stopped before RGB or D1 output. See the
[M21 evidence report](docs/evaluation/m21-ycbv-per-archive-root-repair-v1.md).

M22 localized that failure without reading media: the same public annotations contain
81 qualifying small-positive frames and 14,775 safe negatives, but zero positive/negative
pairs within one object/scene key. M22 alone did not adopt cross-scene pairing. See the
[M22 evidence report](docs/evaluation/m22-ycbv-annotation-failure-localization-v1.md).

M23 checked that proposed repair against current official BOP/COCO evaluator code and
the executable M16 metric/split contract. All five frozen gates pass: one modeled class
may aggregate a positive and complete class-absent negative from different scenes while
remaining in the same test-only oracle. The selection is capped at 18 frames and does
not authorize data/model work or a movement, relation, or whole-home claim. See the
[M23 evidence report](docs/evaluation/m23-cross-scene-transfer-oracle-validity-v1.md).

M24 materialized the smallest pair into ignored local storage: one object-4 positive
from scene 50/image 620 and one complete class-absent negative from scene 48/image 1.
Archive safety, two-run determinism, separate scene identities, and M16 fixture loading
passed. The run also exposed a metric mismatch: visible pixels occupy 0.5107% of the
image, but the bbox occupies 3.043%, so M16 does not count it as a small-bbox target.
No detector run is authorized until that mismatch is resolved. See the
[M24 evidence report](docs/evaluation/m24-ycbv-cross-scene-d1-materialization-v1.md).

M25 repaired the evaluation definition before touching media: the same annotation must
occupy 0.1–1% under both visible pixels and the M16 visible-bbox area. Only 2 of 900
target frames pass. The fixed source-order replacement is object 4 at scene 50/image
722 with the complete class-absent scene 48/image 1 frame. This selects one exact
two-frame replacement materialization only; it is too small to support a detector-gain
or household-transfer claim. See the
[M25 evidence report](docs/evaluation/m25-ycbv-small-bbox-alignment-v1.md).

M26 materialized that exact replacement pair into ignored local storage and loaded it
through M16. The sole target is now correctly counted in `small_0.1_to_1pct` (tiny 0,
small 1, large 0); the two clean outputs are byte-identical and the scenes remain
separate with zero transitions. This is a fixture-mechanics pass, not model evidence.
See the [M26 evidence report](docs/evaluation/m26-ycbv-dual-area-replacement-d1-v1.md).

M27 selects the already packaged project-owned key→bag→sofa replay as the primary
90-second hackathon demo. It alone passes all seven clarity, reproducibility, end-to-end
value, trace, dependency, claim, and safety gates. M26 stays optional mechanical CV
evidence; future model gain requires a separate protected-group development plus
untouched-test contract. See the
[M27 evidence report](docs/evaluation/m27-demo-evaluation-contract-v1.md).

M28 ran the direct and compact-CLI demo paths offline. They agreed on the scoped
`FOUND sofa` answer and semantic output, with zero socket attempts. The frozen check
stopped because it incorrectly equated source event-label frames with inference
evidence-window starts; two separate presentation gaps were hardened by collapsing and
strongly labeling perfect synthetic fixture metrics. See the
[M28 evidence report](docs/evaluation/m28-primary-demo-acceptance-v1.md).

M29 corrected that timing meaning before one committed retry. Both interfaces again
agreed offline, and the event-label/evidence-window/confirmation triples now pass. The
retry normally stopped only because the public answer object does not expose its queried
`subject_id`, although `key` remains traceable in the relation path. No second M29 retry
is allowed. See the
[M29 evidence report](docs/evaluation/m29-primary-demo-acceptance-retry-v1.md).

M30 used repository evidence only to decide where query-subject identity belongs.
Adding it to canonical `AnswerTrace` is the sole 8/8-gate selection; a public-DTO-only
field would drift from B0, while current path/UI context fails for empty-path non-FOUND
answers. M31 may implement only that additive field across both serializers. See the
[M30 evidence report](docs/evaluation/m30-answer-subject-identity-decision-v1.md).

M31 implements that additive field across canonical `AnswerTrace` and both serializers;
all six query statuses retain subject identity and the B0 semantic hash is unchanged.
The implementation checks pass, but the Goal normally stops because its full-suite
requirement contradicted its literal no-media clause—the suite itself reads the pinned
synthetic demo fixture. See the
[M31 evidence report](docs/evaluation/m31-answer-trace-subject-implementation-v1.md).

## Run the demo

Requires Python 3.11 or newer. The lockfile was generated with `uv 0.11.24`.

### Windows PowerShell

```powershell
python -m pip install uv==0.11.24
uv sync --frozen --extra demo
.\.venv\Scripts\whole-home-agent.exe demo-recorded --compact
.\.venv\Scripts\streamlit.exe run src\whole_home_agent\streamlit_app.py
```

### macOS or Linux

```bash
python -m pip install uv==0.11.24
uv sync --frozen --extra demo
.venv/bin/whole-home-agent demo-recorded --compact
.venv/bin/streamlit run src/whole_home_agent/streamlit_app.py
```

The Streamlit app has no upload, arbitrary path, camera, chat, cloud, or action input. It always runs the included allowlisted D0 clip. See the [90-second and 3-minute demo guide](docs/demo-guide.md).

## Deterministic B0 replay

The original semantic oracle remains independent of video and optional dependencies:

```bash
uv sync --frozen
.venv/bin/whole-home-agent replay examples/fixtures/b0_key_bag_sofa_v1.json \
  --entity key --as-of 2 --run-id demo-b0-001
.venv/bin/python -m unittest discover -s tests -v
```

On Windows, use the matching executables under `.venv\Scripts\`.

## Architecture

```text
allowlisted generated MP4 + manifest/config hashes
  → PTS frame adapter
  → detector estimates
  → clip-local tracker
  → one-instance binder
  → conservative temporal rules / abstention
  → ClaimCandidate (estimated)
  → deterministic ClaimCommitter
  → session projection
  → scoped AnswerTrace
  → CLI / Streamlit presentation dictionaries
```

Detector and rule outputs cannot directly mutate state. A complete source failure returns no queryable session. The UI receives presentation values and public media bytes, not a model, ledger, filesystem, credential, or generic tool handle. No graph database, Memory Core, LLM/VLM, multi-agent runtime, durable database, or action executor is required for this slice.

See the [minimal B0 → B1 architecture](docs/b0-b1-architecture-plan.md), [system diagram](docs/b0-b1-system.architecture.html), [perception data flow](docs/b0-b1-perception.dataflow.html), [implementation notes](docs/technology-notes/), [release checklist](docs/release-checklist.md), and [ADRs](docs/adr/). Proposed governance and ADR status are recorded in [PROJECT_STATE.md](PROJECT_STATE.md); implementation does not adopt those documents or enable operation.

## Repository map

```text
src/whole_home_agent/       B0 core, B1 contracts/adapters, CLI, presentation
configs/perception/         versioned detector/rule/evaluation controls
configs/evaluation/         public-data source, license, split, and hash controls
examples/fixtures/          frozen semantic D0 fixtures
examples/media/generated/   one CC0 project-generated replay + manifest
tests/                      semantic, hostile, failure, CV, relation, UI tests
tools/                      fixture generation, evaluation, public audit
docs/                       architecture, demo, ADR, and technology notes
```

## Next evidence gate

The first public detector, consecutive motion, target-tracking, failure-localization,
RF-DETR replacement, D-FINE synthetic engineering, M14 scientific-priority, M15
target-substrate, M16 label-oracle, M17 generation-strategy, M18 vector-substrate, and
M19 real-oracle through M32 verification-boundary gates are frozen. M27 selects the existing
synthetic end-to-end replay as the primary demo, keeps M26 as optional smoke, and defers
scientific gain to a separately contracted protected-group development/untouched-test
lane. M31's additive implementation passes all semantic checks but remains a historical
normal stop. M32 now permits the exact committed D0 synthetic fixture only inside the
complete-regression profile. M33 is one separately frozen teammate clean-install and
closed-demo drill; it cannot use external/private/live media, rerun M29, load a model,
tune, or train.
Tracker replacement remains a separate later co-gate.
The reserved VOST validation source and VISOR `P14_05` must remain untouched. Do not add
a movement-candidate layer merely because scheduling is inexpensive. Training remains
capped at 20 epochs with patience 5, and test tuning and automatic submissions remain
prohibited. See the [M11 diagnostic](docs/evaluation/vost-m11-failure-localization-v1.md)
and [M12 detector screen](docs/evaluation/vost-m12-rfdetr-small-v1.md), plus the
[M13 engineering screen](docs/evaluation/m13-dfine-small-synthetic-v1.md), the
[M14 priority decision](docs/evaluation/m14-detector-scientific-priority-v1.md), and the
[M15 result](docs/evaluation/m15-target-domain-substrate-v1.md), plus the
[M16 result](docs/evaluation/m16-target-label-oracle-feasibility-v1.md), the
[M17 result](docs/evaluation/m17-generation-strategy-reality-gate-v1.md), the
[M18 result](docs/evaluation/m18-vector-d1-slice-v1.md), and the
[M19 result](docs/evaluation/m19-real-transfer-oracle-reality-gate-v1.md), the
[M20 result](docs/evaluation/m20-ycbv-bop19-acquisition-translation-v1.md), and the
[M21 result](docs/evaluation/m21-ycbv-per-archive-root-repair-v1.md), and the
[M22 result](docs/evaluation/m22-ycbv-annotation-failure-localization-v1.md), and the
[M23 result](docs/evaluation/m23-cross-scene-transfer-oracle-validity-v1.md), and the
[M24 result](docs/evaluation/m24-ycbv-cross-scene-d1-materialization-v1.md), plus the
[M25 result](docs/evaluation/m25-ycbv-small-bbox-alignment-v1.md), and the
[M26 result](docs/evaluation/m26-ycbv-dual-area-replacement-d1-v1.md), and the
[M27 result](docs/evaluation/m27-demo-evaluation-contract-v1.md).
The [M28 result](docs/evaluation/m28-primary-demo-acceptance-v1.md) records the
normal stop, exact trace mismatch, and bounded presentation hardening.
The [M29 result](docs/evaluation/m29-primary-demo-acceptance-retry-v1.md) records the
single retry, corrected time semantics, and remaining answer-subject mismatch.
The [M30 result](docs/evaluation/m30-answer-subject-identity-decision-v1.md) selects the
canonical boundary for one separately frozen implementation.
The [M31 result](docs/evaluation/m31-answer-trace-subject-implementation-v1.md) records
the correct additive implementation and the distinct verification-boundary STOP.
The [M32 result](docs/evaluation/m32-verification-fixture-boundary-decision-v1.md)
separates static, complete-regression, and ad-hoc experiment authority without changing
M31 history.
The [M33 result](docs/evaluation/m33-teammate-clean-install-demo-drill-v1.md) records the
clean-clone success and exact pre-install harness stop without mislabeling it as a repo
or dependency failure.
The [M34 result](docs/evaluation/m34-teammate-drill-infrastructure-retry-v1.md) records
the successful clean install/offline semantics and the distinct CRLF lock-identity STOP.
The [M35 result](docs/evaluation/m35-versioned-text-identity-portability-decision-v1.md)
selects Git-blob identity for the separately bounded non-acceptance checker hardening.

## Safety and data boundary

- `OPERATE` is globally disabled.
- Do not add real household recordings, identifying media, private queries, model weights, secrets, or credentials to Git.
- Do not connect cameras, RTSP feeds, cloud endpoints, accounts, or physical devices.
- Repository access and passing tests grant no household, consent, policy, or runtime authority.
- Do not claim “real-time,” “24/7,” “understands the home,” or “improved” beyond a directly supporting benchmark.

Read [AGENTS.md](AGENTS.md), [PROJECT_STATE.md](PROJECT_STATE.md), and [ACTION_POLICY.md](ACTION_POLICY.md) before changing data, sensing, authority, or action boundaries. Contributions are described in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Original repository code and documentation use the [MIT License](LICENSE). The generated replay is marked `CC0-1.0`; optional dependencies, public evaluation data, and model candidates retain the licenses listed in [third-party notices](docs/third-party-notices.md). No VISOR/VOST source data or model weights are distributed.
