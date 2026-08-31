# CLI and Streamlit presentation boundary

**Status:** implemented for the single allowlisted generated replay

`public_demo.py` is the closed composition and presentation boundary for M5. It selects fixed repository manifests/configurations, constructs concrete offline adapters, runs perception and relation evaluation, queries the completed session, and returns JSON-safe presentation values. The CLI and Streamlit app do not receive the model, tracker, binder, candidate source, ledger, filesystem, credentials, or a generic tool handle.

The only separate media method returns bytes from the same hash-validated public manifest. It does not accept a path or URL. The Streamlit source contains no upload, camera, free-form query/chat, network model, device, or action widget.

## Why Streamlit

For a three-day hackathon, Streamlit provides a small local presentation layer for video, tables, metrics, and structured evidence without creating a frontend/backend protocol or database. Version `1.62.0` is exact-pinned in the `demo` extra and resolved in `uv.lock`; it is Apache 2.0. It is not a runtime requirement for B0, the recorded adapter, or CLI JSON.

The app intentionally recomputes the eight-second fixture rather than reading a trusted-looking saved answer. Streamlit's `AppTest` renders the app in CI, while separate tests assert the absence of upload/camera/chat widgets and validate the presentation payload, public media hash, CLI compact mode, scoped answer, evidence, and limits.

## Presentation content

The UI shows:

- a persistent `OPERATE DISABLED` warning and the included CC0 video;
- an estimated, replay-scoped answer and two-step relation path;
- accepted claim rows with confirmation frames, confidence floor, and evidence span;
- fixed-fixture detection/event quality and measured p95 latency;
- visible abstention and notable timeline frames;
- raw answer and execution receipt expanders;
- explicit limits against present-world, indoor, live, and action claims.

The concise answer is a deterministic template, not an LLM call. Language quality cannot alter claims, authority, or query scope.

## Evidence boundary

Passing UI/CLI tests supports only rendering and serialization of the fixed public demo. It does not test public hosting, concurrent users, authentication, live data, household consent, or operational safety. Local web serving for the developer UI does not enable household sensing or `OPERATE`.
