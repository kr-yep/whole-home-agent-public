# Generated D0 replay media

This directory contains only tiny project-generated synthetic fixtures. It does not contain recordings of a household or person.

- `key_bag_sofa_v1.mp4` and its annotations are dedicated under `CC0-1.0`.
- The adjacent manifest records exact hashes, generator provenance, coordinate space, source identity, and intended `D0_SYNTHETIC` use.
- The clip is an integration fixture. It does not demonstrate real-world perception quality or establish that its depicted relations occurred physically.
- Regenerate it with `python tools/generate_synthetic_replay.py` from an environment synchronized with `uv.lock` and the `video` extra.

The repository public-release audit rejects media outside this directory or media without a matching D0 synthetic manifest.
