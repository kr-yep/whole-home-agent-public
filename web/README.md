# The character page

A clone of this repository has all of this code and none of the artwork. That is
deliberate — the repository ignores images by policy and keeps model files out of
version control — but it means the page loads with nobody standing on it.

If you opened the page and the panel worked while the canvas stayed empty, this
is why, and it is one command to fix:

```
python tools/fetch_character_assets.py
```

That downloads what can be downloaded, and tells you where the rest comes from.
`--check` reports what is present without fetching anything.

## What each character needs

| Character | File | Where it comes from |
|---|---|---|
| 雷姆 | `web/live2d/rem/` | Fetched at setup, never committed: Live2D sample-data terms. About 12 MB across 112 files. |
| 奶龍 | `web/characters/nailong/idle.png` | Committed with the repository. Project-generated art, no upstream terms. |

Credits and licence terms are in `docs/third-party-notices.md`, including one that
matters: the vendored Live2D Cubism Core is not open source.

## Running it

```
python -m whole_home_agent.web_app --port 8600
```

Answers come from the same use case the Streamlit page uses, so the memory,
parsing, traversal and abstention are identical; only the surface differs. Set
`WHA_LLM_ENDPOINT` and `WHA_LLM_MODEL` to have a private model do the talking,
and the page falls back to deterministic sentences without them.

## Adding a character

One entry in `web/characters.js` and one asset. The entry says which of three
kinds it is — a Cubism model or a flat image — and the page's
layout, dragging, zooming and speech bubble work the same for all three, because
they ask the character for its bounds rather than reaching into a renderer.

A name that reaches the model's prompt is looked up in a registry on the server
side, so adding a character to this file alone gives it a body and the default
voice; `CHARACTER_NAMES` in `src/whole_home_agent/adapters/loopback_llm.py` is
what gives it its own name.
