# Whole Home Agent

> **Current milestone:** `B0 — frozen D0 semantic replay`
>
> **Status:** `NOT PRODUCTION` · `OPERATE DISABLED`
>
> **Allowed data:** local synthetic fixtures or lawfully reusable public fixtures

Whole Home Agent is an offline-first prototype for answering traceable questions about how objects and containers move through a space. A representative story is:

```text
key placed in bag -> bag moved to sofa -> query(key)
                                      -> “the key may be in the bag at the sofa”
```

This repository deliberately starts below the camera layer. The current baseline replays frozen JSON events, validates them deterministically, projects current relations, and returns an answer with its scope, time frontier, and supporting claim chain. It is a maintainable semantic core for later perception experiments—not evidence that a camera understands a real home.

## What works today

- deterministic replay of versioned synthetic fixtures;
- containment and location propagation such as `key -> bag -> sofa`;
- explicit `UNKNOWN`, `CONFLICT`, and stale-result behavior;
- idempotent claim handling and rejection of same-ID/different-content input;
- query answers scoped to a fixture, run, source sequence, and claim chain;
- a standard-library Python runtime and CLI;
- automated tests on Python 3.11–3.14 through GitHub Actions.

The current milestone excludes cameras, recorded or live household media, databases, LLM/VLM calls, cloud services, device control, action planners, credentials, and multi-agent runtime behavior.

## Architecture boundary

```text
frozen D0 fixture
  -> ClaimCandidate
  -> deterministic validation / commit
  -> session-local AcceptedClaim ledger
  -> pure relation projection
  -> scoped AnswerTrace
```

Data, control, action, authority, and physical outcome are intentionally separate. An accepted claim means only that a source report passed the validator for this replay. It does not establish that a real-world event happened. A future command acknowledgement would likewise not prove a physical result.

See the [B0 → B1 minimal architecture proposal](docs/b0-b1-architecture-plan.md), [interactive system map](docs/b0-b1-system.architecture.html), and [interactive perception data flow](docs/b0-b1-perception.dataflow.html) for the current plan. The HTML files are self-contained and can be downloaded and opened locally. The earlier [minimal viable architecture](docs/minimal-viable-architecture.md), [architecture roadmap](docs/architecture.md), and [ADRs](docs/adr/) remain available for context; none of the proposed B1 material is adopted or implemented merely because it is documented.

## Quick start

Requires Python 3.11 or newer.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
```

### macOS or Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Run the key → bag → sofa example:

```bash
whole-home-agent replay examples/fixtures/b0_key_bag_sofa_v1.json \
  --entity key \
  --as-of 2 \
  --run-id demo-b0-001
```

The CLI writes structured results to stdout. Invalid input produces a typed error on stderr and exit code `2`; valid `UNKNOWN` or `CONFLICT` domain results use exit code `0`.

## Repository map

```text
src/whole_home_agent/       B0 domain, application flow, adapters, and CLI
tests/                      semantic, boundary, hostile, and replay tests
examples/fixtures/          small synthetic JSON fixtures safe for Git
docs/                       architecture notes and proposed ADRs
AGENTS.md                   proposed repository governance
PROJECT_STATE.md            current status, evidence, and unresolved gates
ACTION_POLICY.md            proposed policy; all operation remains disabled
```

## Working with the team

1. Create a short-lived branch from `main`.
2. Keep changes inside the current B0 boundary unless an ADR and explicit project decision expand it.
3. Add or update a frozen fixture and deterministic test for behavior changes.
4. Run the full test suite before opening a pull request.
5. Keep datasets, media, model weights, databases, runtime outputs, secrets, and credentials out of Git.

More details are in [CONTRIBUTING.md](CONTRIBUTING.md). Repository access or a merged pull request does not authorize real household sensing, data processing, or device operation.

## Roadmap

- Complete the remaining B0 conformance and maintainer-replay gates.
- Define a narrow B1 adapter contract for prerecorded public or synthetic video.
- Evaluate small-object methods on a frozen indoor set with paired quality and inference-cost measurements.
- Consider live sensing only after roles, consent, retention, enforcement, and independent activation are adopted and verified.

Memory graphs, a “Memory Core,” multi-agent orchestration, and device actions are candidates only if evidence shows they are needed. They are not architectural prerequisites.

The current B1 proposal keeps YOLO, tracking, and event extraction inside a replaceable offline adapter. That adapter may emit only the existing canonical `ClaimCandidate`; it cannot commit claims or bypass the B0 semantic core.

## Safety and data policy

- `OPERATE` is globally disabled.
- Do not add real household recordings, identifying media, credentials, or private queries.
- Do not connect cameras, RTSP feeds, cloud endpoints, or physical devices in the B0 path.
- Do not claim “real-time,” “24/7,” or “improved” without a reproducible benchmark that directly supports it.

Read [AGENTS.md](AGENTS.md), [PROJECT_STATE.md](PROJECT_STATE.md), and [ACTION_POLICY.md](ACTION_POLICY.md) before making changes that affect data, sensing, authority, or action boundaries.

## License

The repository's original code and documentation are available under the [MIT License](LICENSE). Third-party datasets, models, and dependencies keep their own licenses and must be reviewed before use or redistribution.
