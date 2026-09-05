# The character page

A clone of this repository has all of this code and none of the artwork. That is
deliberate — images are ignored repository-wide and `web/live2d/` is ignored as
well — but it means the page loads with nobody standing on it.

If the panel worked and the canvas stayed empty, that is why, and it is one
command to fix:

```
python tools/fetch_character_assets.py
```

`--check` reports what is present without downloading anything.

| Character | Files | Where they come from |
|---|---|---|
| 雷姆 | `web/live2d/rem/` | Fetched by the script from a public repository. Cubism 4 model, about 12 MB across 112 files. |

Credits and licence terms are in `docs/third-party-notices.md`.

## Running it

```
python -m whole_home_agent.web_app --port 8600
```

Answers come from the same use case the Streamlit page uses, so memory, parsing,
traversal and abstention are identical; only the surface differs. Set
`WHA_LLM_ENDPOINT` and `WHA_LLM_MODEL` to have a private model do the talking,
and the page falls back to deterministic sentences without them.
