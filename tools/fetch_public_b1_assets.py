"""Fetch hash-pinned public B1 screening assets into Git-ignored local paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tomllib
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
VISOR_CONFIG = ROOT / "configs" / "evaluation" / "visor-screen-v1.toml"
MODEL_CONFIG = ROOT / "configs" / "perception" / "torchvision-coco-baselines-v1.toml"
USE_CLASS = "D0_PUBLIC_NONCOMMERCIAL_METHOD_SCREENING"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch fixed public B1 evaluation data or model artifacts."
    )
    parser.add_argument("asset", choices=("visor", "models", "all"))
    parser.add_argument(
        "--acknowledge-visor-use-class",
        choices=(USE_CLASS,),
        help="Required for VISOR because its published license is non-commercial.",
    )
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _within_root(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as error:
        raise ValueError("asset path escaped the repository") from error
    return path


def _download(
    *,
    url: str,
    destination: Path,
    expected_bytes: int,
    expected_hash: str,
    allowed_host: str,
) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != allowed_host:
        raise ValueError("asset URL is outside the fixed official host")
    if destination.is_file():
        if destination.stat().st_size == expected_bytes and _sha256(destination) == expected_hash:
            return "VERIFIED_EXISTING"
        raise ValueError(f"existing artifact failed verification: {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    if part.exists():
        raise ValueError(f"incomplete artifact needs manual review: {part.name}")
    request = urllib.request.Request(url, headers={"User-Agent": "whole-home-agent/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, part.open("xb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        if part.stat().st_size != expected_bytes or _sha256(part) != expected_hash:
            raise ValueError(f"downloaded artifact failed verification: {destination.name}")
        os.replace(part, destination)
    except Exception:
        # Preserve a partial artifact for diagnosis; it can never pass the verifier.
        raise
    return "DOWNLOADED_AND_VERIFIED"


def _extract_visor(sequence: dict[str, object], local_root: Path) -> str:
    annotation_path = local_root / str(sequence["annotation_path"])
    archive_path = local_root / str(sequence["archive_path"])
    frames_path = local_root / str(sequence["frames_path"])
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    expected_names = {
        record["image"]["name"] for record in annotation["video_annotations"]
    }
    if len(expected_names) != sequence["frame_count"]:
        raise ValueError("VISOR annotation image set disagrees with the frozen count")
    if frames_path.exists():
        actual = {path.name for path in frames_path.rglob("*.jpg") if path.is_file()}
        if actual == expected_names:
            return "VERIFIED_EXISTING"
        raise ValueError("existing VISOR extraction disagrees with the frozen annotation")
    frames_path.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        members = {Path(info.filename).name: info for info in archive.infolist() if not info.is_dir()}
        if set(members) != expected_names:
            raise ValueError("VISOR archive members disagree with the frozen annotation")
        for name in sorted(expected_names):
            destination = frames_path / name
            with archive.open(members[name]) as source, destination.open("xb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    return "EXTRACTED"


def _fetch_visor() -> list[dict[str, str]]:
    document = tomllib.loads(VISOR_CONFIG.read_text(encoding="utf-8"))
    if (
        document.get("intended_use") != USE_CLASS
        or document.get("license_id") != "CC-BY-NC-4.0"
        or document.get("redistribution_allowed") is not False
    ):
        raise ValueError("VISOR use envelope was loosened")
    local_root = _within_root(document["local_root"])
    results: list[dict[str, str]] = []
    for sequence in document["sequence"]:
        annotation = local_root / sequence["annotation_path"]
        archive = local_root / sequence["archive_path"]
        annotation_status = _download(
            url=sequence["annotation_url"],
            destination=annotation,
            expected_bytes=sequence["annotation_bytes"],
            expected_hash=sequence["annotation_sha256"],
            allowed_host="data.bris.ac.uk",
        )
        archive_status = _download(
            url=sequence["archive_url"],
            destination=archive,
            expected_bytes=sequence["archive_bytes"],
            expected_hash=sequence["archive_sha256"],
            allowed_host="data.bris.ac.uk",
        )
        extraction_status = _extract_visor(sequence, local_root)
        results.append(
            {
                "annotation": annotation_status,
                "archive": archive_status,
                "extraction": extraction_status,
                "sequence_id": sequence["sequence_id"],
            }
        )
    return results


def _fetch_models() -> list[dict[str, str]]:
    document = tomllib.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    if (
        document.get("status") != "FROZEN_BASELINE"
        or document.get("test_tuning_allowed") is not False
    ):
        raise ValueError("model baseline envelope was loosened")
    results: list[dict[str, str]] = []
    for model in document["model"]:
        status = _download(
            url=model["weights_url"],
            destination=_within_root(model["weights_path"]),
            expected_bytes=model["weights_bytes"],
            expected_hash=model["weights_sha256"],
            allowed_host="download.pytorch.org",
        )
        results.append({"model_id": model["model_id"], "weights": status})
    return results


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.asset in {"visor", "all"} and args.acknowledge_visor_use_class != USE_CLASS:
        _parser().error(
            "VISOR fetch requires --acknowledge-visor-use-class " + USE_CLASS
        )
    result: dict[str, object] = {"operate": "DISABLED"}
    if args.asset in {"visor", "all"}:
        result["visor"] = _fetch_visor()
    if args.asset in {"models", "all"}:
        result["models"] = _fetch_models()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
