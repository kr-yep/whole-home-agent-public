# Whole Home Agent

> **Current milestone:** `B1 — offline replay + public sparse-frame perception screen`
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

## What works today

- hash-pinned, project-generated 80-frame MP4 replay with exact annotations;
- PTS-aware PyAV decoding and optional motion-plus-periodic scheduling;
- a deterministic RGB smoke detector for the generated artwork;
- a hash-pinned RF-DETR Nano adapter boundary for a future real model artifact;
- clip-local IoU tracking and one-instance manifest binding;
- conservative containment/location rules with explicit abstention behavior;
- the unchanged B0 claim committer, relation projection, and scoped query path;
- fixed AP, event, answer, latency, FPS, dropped-frame, and VRAM reporting;
- a frozen, source-video-split VISOR indoor screen with hash-pinned local assets;
- paired SSDLite320 and RetinaNet-FPN detector adapters with no implicit download;
- JSON CLI and a local Streamlit presentation;
- automated B0 tests on Python 3.11–3.14 plus locked B1/demo jobs.

On the included browser-compatible H.264 synthetic clip, the current RGB baseline measures AP50 `1.0`, mAP50:95 about `0.7293`, key recall `1.0`, zero false positives, event F1 `1.0`, and the final expected answer. The clip-local tracker records zero ID switches and zero fragmentations on this one easy fixture. These numbers apply only to this generated artwork and do not establish indoor accuracy, real-time operation, or 24/7 readiness.

On the separately downloaded VISOR screen, RetinaNet-FPN improved validation
recall@0.5 from `14.3%` to `25.0%` over SSDLite320 and found `1/3` validation
targets occupying 0.1–1% of the frame versus `0/3`. It used about `393.3 MiB` peak
VRAM and `71.7 ms` detector p95, versus `85.7 MiB` and `47.4 ms`. The first frozen
test improved overall recall from `14.3%` to `39.3%`, but its only small target was
missed by both models. See the [full evidence limits and gate](docs/evaluation/visor-screen-v1.md).

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

The first public indoor screen is now frozen and evaluated. The next bounded step is a
validation-only sliced/ROI RetinaNet experiment: improve validation small-target or
overall recall materially while staying below `200 ms` p95 and `1.5 GiB` VRAM. The
existing `P14_05` test must not be rerun or used for tuning; another untouched source is
required before a later final claim. Training remains capped at 20 epochs with patience
5, and test tuning and automatic submissions remain prohibited.

## Safety and data boundary

- `OPERATE` is globally disabled.
- Do not add real household recordings, identifying media, private queries, model weights, secrets, or credentials to Git.
- Do not connect cameras, RTSP feeds, cloud endpoints, accounts, or physical devices.
- Repository access and passing tests grant no household, consent, policy, or runtime authority.
- Do not claim “real-time,” “24/7,” “understands the home,” or “improved” beyond a directly supporting benchmark.

Read [AGENTS.md](AGENTS.md), [PROJECT_STATE.md](PROJECT_STATE.md), and [ACTION_POLICY.md](ACTION_POLICY.md) before changing data, sensing, authority, or action boundaries. Contributions are described in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Original repository code and documentation use the [MIT License](LICENSE). The generated replay is marked `CC0-1.0`; optional dependencies, public evaluation data, and model candidates retain the licenses listed in [third-party notices](docs/third-party-notices.md). No VISOR source data or model weights are distributed.
