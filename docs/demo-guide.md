# Demo guide

## Before presenting

```powershell
python -m pip install uv==0.11.24
uv sync --frozen --extra demo
.\.venv\Scripts\python.exe -m unittest tests.test_public_demo -v
.\.venv\Scripts\streamlit.exe run src\whole_home_agent\streamlit_app.py
```

Use the macOS/Linux `.venv/bin/` equivalents where appropriate. The demo needs no account, API key, network model call, camera, or private recording.

## 90-second version

1. Point to the red `OPERATE DISABLED` banner: “This is a safe prerecorded prototype, not a live household camera.”
2. Play the eight-second generated clip: a key approaches a bag, disappears into it, and the bag moves to the sofa.
3. Show the question “Where is the key?” and the answer: “It may be in the bag at the sofa.” Emphasize `estimated`, replay scope, run ID, and as-of frontier.
4. Show the two evidence rows: estimated `inside(key, bag)` at confirmation frame 37 and `at_zone(bag, sofa)` at frame 68.
5. Open “Evidence limits”: no abstention was needed on this easy generated replay, while ambiguous, unsupported, and interrupted cases are tested to fail closed.
6. Close with the limit: “This demonstrates the traceable architecture on one generated clip. Separate public-data screens test detector and scheduler candidates, but none turns this demo into a real-home result.”

## Three-minute version

Add these points to the short flow:

- The RGB detector, tracker, binder, and rule engine are replaceable; only canonical `ClaimCandidate` crosses into state.
- The same deterministic committer handles semantic fixtures and video-derived estimates. A model cannot commit directly.
- The query connects `key → bag → sofa` without fabricating a direct key movement when only the bag moved.
- Event precision/recall/F1 is `1.0` on this fixture with confirmation lags of two and three frames; the perfect clip-local tracking result is only an easy-fixture ceiling, not indoor evidence.
- If the detector fails after producing the first candidate, the run becomes `INCOMPLETE` and exposes no session or partial answer.
- RF-DETR Nano/Small remain evaluation adapters. The Small candidate failed its development recall gate; no real model weight is bundled or silently downloaded.

## Useful CLI evidence

```powershell
.\.venv\Scripts\whole-home-agent.exe demo-recorded --compact --run-id judging-demo
.\.venv\Scripts\python.exe tools\run_b1_perception_eval.py
.\.venv\Scripts\python.exe tools\audit_public_release.py
```

The JSON includes the answer path, evidence ranges, producer/config hashes, quality/cost envelope, abstentions, and run receipt.

## Do not claim

- that it recognizes objects in a real household;
- that the synthetic scores transfer to indoor video;
- that it is 24/7, real-time, production-ready, or privacy-complete;
- that an accepted estimate is a physical fact;
- that live sensing or device action is enabled.
