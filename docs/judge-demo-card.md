# Whole Home Agent — 90-second judge card

## Timeline

- **0–10 seconds — Problem and boundary.** “People lose small objects because the
  object can disappear into a container while the container keeps moving.” Point to
  `OPERATE DISABLED`: this is a local prerecorded prototype, not a live camera.
- **10–30 seconds — Change.** Play the eight-second generated clip. The key enters the
  bag; the bag later moves to the sofa.
- **30–55 seconds — Answer.** Show the fixed scoped question, “Where is the key?” The
  answer is an `estimated` chain: key → bag → sofa, not a physical-truth claim.
- **55–75 seconds — Evidence and abstention.** Show the two evidence ranges and the
  abstention section. Ambiguous, unsupported, and interrupted runs fail closed.
- **75–90 seconds — Limit and value.** “This proves a traceable replaceable architecture
  on one generated clip. Real small-object CV is a separate evaluation lane.”

## Start the UI

### Windows PowerShell

```powershell
python -m pip install uv==0.11.24
uv sync --frozen --extra demo
.\.venv\Scripts\streamlit.exe run src\whole_home_agent\streamlit_app.py
```

### macOS / Linux

```bash
python -m pip install uv==0.11.24
uv sync --frozen --extra demo
.venv/bin/streamlit run src/whole_home_agent/streamlit_app.py
```

## Compact CLI backup

```text
whole-home-agent demo-recorded --compact --run-id judging-demo
```

## Recovery

If the browser does not open, use the compact CLI backup and show `answer`, `claims`,
`source_diagnostics`, `warnings`, and `run_receipt`. If the replay fails, do not switch
to private media or a live camera; show the last green CI link and architecture diagram.

## Do not claim

- real-home recognition accuracy or a detector gain;
- general chat or language understanding;
- live, 24/7, production, or privacy-complete operation;
- that an accepted estimate is physical truth;
- camera, cloud, account, device, or action capability.
