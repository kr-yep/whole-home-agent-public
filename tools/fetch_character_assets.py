"""Fetch the character artwork the web page needs but the repository does not carry.

This repository ignores images by policy and keeps model files out of version
control, so a fresh clone has every line of the front end and none of the art:
the page loads, the panel answers questions, and nobody is standing there.

Run this to get what can be fetched, and to be told where the rest comes from.

    python tools/fetch_character_assets.py
    python tools/fetch_character_assets.py --check

Standard library only, matching the rest of the package.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
TIMEOUT = 120
LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"

# The Live2D model is fan work hosted in a public repository. It is fetched
# rather than vendored because it is 13 MB of third-party art, and because the
# Cubism runtime it needs has its own licence -- see docs/third-party-notices.md.
REM = {
    "repo": "BaneBeetle/waifubeetle2",
    "source": "frontend/live2d-models/REM",
    "dest": WEB / "live2d" / "rem",
    "marker": "REM.model3.json",
}

# Anything a future character needs that cannot be fetched goes here, so a
# missing file is named rather than discovered as an empty canvas.
BY_HAND: list[tuple[Path, str]] = []


def _get(url: str, headers: dict | None = None) -> bytes:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def _tree(repo: str) -> list[dict]:
    payload = _get(
        f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1",
        {"Accept": "application/vnd.github+json"},
    )
    return json.loads(payload)["tree"]


def _resolve_lfs(repo: str, pointers: list[tuple[Path, str, int]]) -> dict[str, str]:
    """Ask the LFS server for the real files behind a set of pointer stubs."""

    body = json.dumps(
        {
            "operation": "download",
            "transfers": ["basic"],
            "objects": [{"oid": oid, "size": size} for _, oid, size in pointers],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://github.com/{repo}.git/info/lfs/objects/batch",
        data=body,
        headers={
            "Accept": "application/vnd.git-lfs+json",
            "Content-Type": "application/vnd.git-lfs+json",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        payload = response.read()
    document = json.loads(payload)
    return {
        entry["oid"]: entry["actions"]["download"]["href"]
        for entry in document.get("objects", [])
        if "actions" in entry
    }


def fetch_rem() -> int:
    prefix = REM["source"] + "/"
    entries = [
        entry
        for entry in _tree(REM["repo"])
        if entry["type"] == "blob" and entry["path"].startswith(prefix)
    ]
    if not entries:
        print(f"  nothing found under {REM['repo']}/{REM['source']}")
        return 1

    print(f"  {len(entries)} files from {REM['repo']}")
    pointers: list[tuple[Path, str, int]] = []
    for entry in entries:
        target = REM["dest"] / entry["path"][len(prefix) :]
        target.parent.mkdir(parents=True, exist_ok=True)
        blob = _get(
            "https://raw.githubusercontent.com/"
            + REM["repo"]
            + "/HEAD/"
            + urllib.parse.quote(entry["path"])
        )
        if blob.startswith(LFS_POINTER):
            fields = dict(
                line.split(" ", 1)
                for line in blob.decode().strip().split("\n")[1:]
            )
            pointers.append((target, fields["oid"].split(":")[1], int(fields["size"])))
        else:
            target.write_bytes(blob)

    if pointers:
        print(f"  {len(pointers)} of them are Git LFS pointers; resolving")
        hrefs = _resolve_lfs(REM["repo"], pointers)
        for target, oid, size in pointers:
            if oid not in hrefs:
                print(f"  could not resolve {target.name}")
                return 1
            data = _get(hrefs[oid])
            if len(data) != size:
                print(f"  {target.name} came back {len(data)} bytes, expected {size}")
                return 1
            target.write_bytes(data)
    return 0


def report() -> int:
    missing = 0
    marker = REM["dest"] / REM["marker"]
    if marker.exists():
        print(f"  present  {marker.relative_to(WEB.parent)}")
    else:
        missing += 1
        print(f"  MISSING  {marker.relative_to(WEB.parent)}")
        print("           run this script without --check to fetch it")
    for path, note in BY_HAND:
        if path.exists():
            print(f"  present  {path.relative_to(WEB.parent)}")
        else:
            missing += 1
            print(f"  MISSING  {path.relative_to(WEB.parent)}")
            for line in note.split("\n"):
                print(f"           {line}")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(prog="fetch-character-assets")
    parser.add_argument(
        "--check",
        action="store_true",
        help="report what is present or missing without downloading anything",
    )
    arguments = parser.parse_args()

    if arguments.check:
        return 1 if report() else 0

    if (REM["dest"] / REM["marker"]).exists():
        print("  Live2D model already present, leaving it alone")
    else:
        print("Fetching the Live2D model")
        if fetch_rem():
            return 1

    print("\nStatus")
    report()
    print(
        "\nArtwork licences and credits are in docs/third-party-notices.md."
        "\nThe characters depict third-party properties; this is a local,"
        "\nnon-commercial prototype and claims no rights over them."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
