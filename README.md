# Whole Home Agent

> **Hackathon demo:** prerecorded object-location memory
> **Status:** `NOT PRODUCTION` · `OPERATE DISABLED` · no camera or API key required

Whole Home Agent demonstrates one useful idea: remember how a small object moves through
containers and locations, then answer with a traceable evidence chain.

```text
key enters bag → bag moves to sofa
query(key) → “the key may be in the bag on the sofa”
```

The current demo analyzes one included, project-generated eight-second video. Its answer
is an `estimated` result scoped to that replay, not a claim about a real home.

## Run the demo in five minutes

Requires Git and Python 3.11 or newer. The first setup downloads public Python packages;
the demo itself makes no cloud/model request.

### Windows PowerShell

```powershell
git clone https://github.com/kr-yep/whole-home-agent-public.git
cd whole-home-agent-public
python -m pip install uv==0.11.24
uv run --frozen --extra demo whole-home-agent demo-recorded --compact
uv run --frozen --extra demo streamlit run src/whole_home_agent/streamlit_app.py
```

### macOS or Linux

```bash
git clone https://github.com/kr-yep/whole-home-agent-public.git
cd whole-home-agent-public
python3 -m pip install uv==0.11.24
uv run --frozen --extra demo whole-home-agent demo-recorded --compact
uv run --frozen --extra demo streamlit run src/whole_home_agent/streamlit_app.py
```

The first `uv run` synchronizes the locked environment and prints the structured answer.
The second opens the original closed visual demo. Neither command accepts an upload,
camera, credential, free-form prompt, or action handle.

## Add local memory and free-text questions

The new optional path writes only the completed generated replay's semantic claims to
an explicit local SQLite file. It stores no video, frame, question, answer prose, or API
key. A later process verifies and rebuilds the projection before answering.

```powershell
uv run --frozen --extra demo whole-home-agent remember-demo `
  --db .whole-home-agent/demo-memory.sqlite3
uv run --frozen --extra demo whole-home-agent ask-memory `
  --db .whole-home-agent/demo-memory.sqlite3 `
  --question "鑰匙在哪裡？"
uv run --frozen --extra demo streamlit run src/whole_home_agent/memory_app.py
```

The bounded parser accepts location questions in Chinese or English and maps exactly
one known entity to the typed query. Ambiguous, unknown, action-shaped, or malformed
text is rejected instead of being sent to a model.

An optional OpenAI-compatible presenter can be used with a language model already
running on a literal loopback address:

```powershell
$env:WHA_LLM_API_KEY = "optional-local-token"
uv run --frozen --extra demo whole-home-agent ask-memory `
  --db .whole-home-agent/demo-memory.sqlite3 `
  --question "Where is my key?" `
  --presenter local-api `
  --llm-endpoint http://127.0.0.1:11434/v1/chat/completions `
  --llm-model your-exact-local-model-id
```

The key is read only after `local-api` is explicitly selected. Remote hosts, redirects,
and ambient proxies are rejected. The model receives only the minimized answer and
relation text packet; its output cannot change memory, query results, policy, or action.
Cloud API use remains disabled pending adopted data-egress authority.

## What the demo proves

- One prerecorded-video path reaches detection, tracking, relation inference, state,
  query, and presentation.
- `key → bag → sofa` is resolved without fabricating a direct key movement.
- The answer exposes source claims, evidence frames, replay scope, and `estimated` status.
- A deterministic local Chinese presenter works without an LLM or API key.
- A completed D0 replay can be restored from SQLite in another process and queried in
  bounded Chinese or English.
- Ambiguous or incomplete runs fail closed instead of returning partial state.

It does **not** prove real-home recognition, 24/7 operation, live sensing, multi-camera
identity, durable household memory/retention safety, cloud privacy, or device control.

## Architecture

```text
allowlisted generated MP4 + manifest/config hashes
  → PTS-aware frame decoder
  → replaceable detector and clip-local tracker
  → conservative relation candidates / abstention
  → deterministic claim validation and commit
  → optional D0-only SQLite completed-replay archive
  → rebuilt projection and scoped query
  → bounded free-text subject parser
  → structured AnswerTrace
  → compact CLI or Streamlit presentation
  → minimized text context + deterministic or loopback-local prose
```

Only canonical claim candidates cross from perception into state. Detector/model output
cannot commit facts directly. The presenter sees only the scoped answer context—not
frames, the ledger, credentials, or an action interface.

The current slice is a modular monolith. SQLite is an optional completed-replay archive;
it is not a Memory Core, graph, model authority, or second claim-write path. The default
demo still needs no database or LLM.

## What works today

- deterministic B0 semantic replay with idempotency, conflict, cycle, and unknown cases;
- hash-pinned generated H.264 replay and exact annotation/manifest checks;
- PTS-aware PyAV decoding and optional motion-plus-periodic scheduling;
- synthetic RGB detector, clip-local tracking, containment/location rules, and abstention;
- evidence-bound `AnswerTrace` with subject, location, epistemic status, and relation path;
- compact JSON CLI and a closed Streamlit UI;
- provider-neutral minimized text context and deterministic local presentation fallback;
- optional SQLite replay persistence, bounded natural-language location questions, and
  a separate local-memory Streamlit UI;
- optional no-retry loopback OpenAI-compatible presentation with remote egress denied;
- automated tests on Python 3.11–3.14 plus prerecorded-video and demo CI jobs.

On the included synthetic clip, the current RGB baseline measures AP50 `1.0`,
mAP50:95 about `0.7293`, key recall `1.0`, event F1 `1.0`, and the expected final
answer. These measurements apply only to this generated artwork.

Public-data experiments and alternative detector adapters remain a supporting research
lane. None has established reliable real-home small-object detection or tracking.

## Test the handoff

```powershell
uv run --frozen --extra demo python -m unittest tests.test_public_demo -v
uv run --frozen --extra demo python tools/audit_public_release.py
```

The full deterministic suite is larger and includes historical research contracts:

```powershell
uv run --frozen --extra demo python -m unittest discover -s tests -v
```

## 90-second presentation

1. Show the red `OPERATE DISABLED` banner: this is a safe prerecorded prototype.
2. Play the eight-second clip: the key enters the bag and the bag moves to the sofa.
3. Ask “Where is the key?” and show the answer plus `estimated` status.
4. Show the two relation rows: `inside(key, bag)` and `at_zone(bag, sofa)`.
5. Explain that a model proposes candidates, while deterministic code validates state.
6. Close with the limit: this proves the architecture on one generated clip, not a real
   household deployment.

See the complete [demo guide](docs/demo-guide.md).

## Three-day scope

**Demo-critical:** the included video, B0 claim/query core, B1 prerecorded adapter,
compact CLI, Streamlit UI, and deterministic presenter.

**Supporting research:** VISOR/VOST/YCB-V screens and alternative detector adapters.
They inform later model work but are not required to install or present the demo.

**Deferred:** live/private cameras, multi-camera handoff, cloud LLM calls, persistent
household history/retention, and physical actions. `OPERATE` remains disabled.

## Current gaps

- one independent teammate run of the quick start on their own machine;
- a convincing protected-group real indoor small-object benchmark;
- tracking robust to occlusion, camera motion, and container transitions;
- a product-level recorded indoor replay beyond generated artwork;
- any adopted cloud-provider/egress policy or remote language-model adapter;
- live sensing, real household persistence, consent/retention controls, and actions.

A wheel or sdist is optional for this Git-checkout hackathon handoff. Historical M41–M44
artifact experiments are retained as diagnostics, but they do not block the verified
repository demo.

## Repository map

```text
src/whole_home_agent/       product core, prerecorded adapters, CLI, presentation
configs/perception/         versioned detector/rule/evaluation controls
examples/fixtures/          frozen semantic fixtures
examples/media/generated/   included CC0 generated replay and manifest
tests/                      product, boundary, and historical research tests
tools/                      evaluation and public-release utilities
docs/evaluation/            detailed experiment evidence and limits
```

Start with the concise [capability status](docs/current-capability-status.md). Detailed
architecture and historical evidence remain in
[the B0→B1 plan](docs/b0-b1-architecture-plan.md),
[market synthesis](docs/market-synthesis.md),
[evaluation reports](docs/evaluation/), and [PROJECT_STATE.md](PROJECT_STATE.md).

## Safety and data boundary

- `OPERATE` is globally disabled.
- Do not commit real household recordings, identifying media, private queries, model
  weights, secrets, or credentials.
- Do not connect cameras, RTSP feeds, cloud endpoints, accounts, or physical devices.
- Passing tests grants no household, consent, policy, or runtime authority.
- Do not claim real-time, 24/7, general home understanding, or improved indoor accuracy
  without a directly supporting benchmark.

Read [AGENTS.md](AGENTS.md), [PROJECT_STATE.md](PROJECT_STATE.md), and
[ACTION_POLICY.md](ACTION_POLICY.md) before changing data, sensing, authority, or action
boundaries. Contributions are described in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Original repository code and documentation use the [MIT License](LICENSE). The included
generated replay is marked `CC0-1.0`; optional dependencies, public evaluation data, and
model candidates retain the licenses listed in
[third-party notices](docs/third-party-notices.md). No VISOR/VOST source data or model
weights are distributed.
