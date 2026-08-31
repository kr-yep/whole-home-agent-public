# Whole Home Agent

> **Current milestone:** `B1 — offline prerecorded synthetic replay`
>
> **Status:** `NOT PRODUCTION` · `OPERATE DISABLED`
> **Allowed data:** the included project-generated D0 clip and frozen semantic fixtures

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
- conservative containment/location rules with visible abstention;
- the unchanged B0 claim committer, relation projection, and scoped query path;
- fixed AP, event, answer, latency, FPS, dropped-frame, and VRAM reporting;
- JSON CLI and a local Streamlit presentation;
- automated B0 tests on Python 3.11–3.14 plus locked B1/demo jobs.

On the included synthetic clip, the current RGB baseline measures AP50 `0.9604`, mAP50:95 about `0.5931`, key recall `0.8857`, zero false positives, event F1 `1.0`, and the final expected answer. It also exposes three tracking ID switches, two fragmentations, and one deliberate relation abstention. These numbers apply only to this generated fixture and do not establish indoor accuracy, real-time operation, or 24/7 readiness.

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

See the [minimal B0 → B1 architecture](docs/b0-b1-architecture-plan.md), [system diagram](docs/b0-b1-system.architecture.html), [perception data flow](docs/b0-b1-perception.dataflow.html), [implementation notes](docs/technology-notes/), and [ADRs](docs/adr/). Proposed governance and ADR status are recorded in [PROJECT_STATE.md](PROJECT_STATE.md); implementation does not adopt those documents or enable operation.

## Repository map

```text
src/whole_home_agent/       B0 core, B1 contracts/adapters, CLI, presentation
configs/perception/         versioned detector/rule/evaluation controls
examples/fixtures/          frozen semantic D0 fixtures
examples/media/generated/   one CC0 project-generated replay + manifest
tests/                      semantic, hostile, failure, CV, relation, UI tests
tools/                      fixture generation, evaluation, public audit
docs/                       architecture, demo, ADR, and technology notes
```

## Next evidence gate

The included color detector is intentionally over-scoped to generated artwork. The next useful ML step is a separately licensed, frozen indoor prerecorded set split by scene/video, followed by paired Grounding DINO zero-shot and RF-DETR Nano specialist evaluation. Training remains capped at 20 epochs with patience 5; test tuning and automatic submissions remain prohibited. A candidate must improve event/recall by at least 5 percentage points within 2× p95 latency, or stay within 1 point of quality while reducing cost by at least 30%.

## Safety and data boundary

- `OPERATE` is globally disabled.
- Do not add real household recordings, identifying media, private queries, model weights, secrets, or credentials to Git.
- Do not connect cameras, RTSP feeds, cloud endpoints, accounts, or physical devices.
- Repository access and passing tests grant no household, consent, policy, or runtime authority.
- Do not claim “real-time,” “24/7,” “understands the home,” or “improved” beyond a directly supporting benchmark.

Read [AGENTS.md](AGENTS.md), [PROJECT_STATE.md](PROJECT_STATE.md), and [ACTION_POLICY.md](ACTION_POLICY.md) before changing data, sensing, authority, or action boundaries. Contributions are described in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Original repository code and documentation use the [MIT License](LICENSE). The generated replay is marked `CC0-1.0`; optional dependencies and model candidates retain the licenses listed in [third-party notices](docs/third-party-notices.md). No model weights are distributed.
