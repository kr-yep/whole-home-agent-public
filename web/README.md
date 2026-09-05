# The character page

A clone of this repository has all of this code and none of the artwork. That is
deliberate — the repository ignores images by policy and keeps model files out of
version control. A built-in house avatar keeps the demo usable without artwork.

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
| 雷姆 | `web/live2d/rem/` | Fetched by the script from a public repository. Cubism 4 model, about 12 MB. |
| 奶龍 | `web/characters/nailong/model.glb` | [Sketchfab](https://sketchfab.com/3d-models/nailong-d4617facf9574b45bc57c64e44497242), CC Attribution. A free account is needed to download; export glTF Binary. |
| 奶龍（平面） | `web/characters/nailong/idle.png` | Any front-facing full-body illustration on a transparent background. |

Credits and licence terms are in `docs/third-party-notices.md`, including one that
matters: the vendored Live2D Cubism Core is not open source.

## Running it

```
uv run --frozen --extra demo python -m whole_home_agent.web_app --initialize-demo --port 8600
```

Answers come from the same use case the Streamlit page uses, so the memory,
parsing, traversal and abstention are identical; only the surface differs. Set
`WHA_LLM_ENDPOINT` and `WHA_LLM_MODEL` to have a private model do the talking,
and the page falls back to deterministic sentences without them.

## Adding a character

One entry in `web/characters.js` and one asset. The entry says which of three
kinds it is — a Cubism model, a flat image, or a rigged glTF — and the page's
layout, dragging, zooming and speech bubble work the same for all three, because
they ask the character for its bounds rather than reaching into a renderer.

A name that reaches the model's prompt is looked up in a registry on the server
side, so adding a character to this file alone gives it a body and the default
voice; `CHARACTER_NAMES` in `src/whole_home_agent/adapters/loopback_llm.py` is
what gives it its own name.

Missing or failed character loads preserve the existing avatar. The downloader
fetches only Rem; Nailong artwork must be supplied separately. Nothing downloads
automatically when starting the demo. Device controls remain simulated.
