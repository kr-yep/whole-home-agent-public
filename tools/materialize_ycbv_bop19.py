"""Materialize the frozen M20 BOP YCB-V slice into a Git-ignored local root."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tomllib
import urllib.request
from urllib.parse import urlparse
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from whole_home_agent.adapters.bop_d1 import load_and_translate_ycbv_bop19
from whole_home_agent.target_oracle import evaluate_target_oracle


CONTRACT = ROOT / "configs" / "evaluation" / "m20-ycbv-bop19-acquisition-v1.toml"
USE_CLASS = "D0_PUBLIC_REAL_DETECTOR_TRANSFER_ORACLE"
_ALLOWED_REDIRECT_SUFFIXES = ("huggingface.co", "hf.co", "xethub.hf.co")
_ALLOWED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class MaterializationError(RuntimeError):
    """Fail-closed acquisition or archive error."""


class _RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        hostname = urlparse(newurl).hostname
        if hostname is None or not any(
            hostname == suffix or hostname.endswith("." + suffix)
            for suffix in _ALLOWED_REDIRECT_SUFFIXES
        ):
            raise MaterializationError("download redirect left the official HF host family")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--acknowledge-use-class",
        choices=(USE_CLASS,),
        required=True,
    )
    return parser


def _load_contract() -> dict[str, object]:
    document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    if (
        document.get("status") != "FROZEN_BEFORE_ARCHIVE_DOWNLOAD"
        or document.get("intended_use") != USE_CLASS
        or document.get("source_revision")
        != "5c2c4aa229800355648cd268040aa814f8dc94f0"
    ):
        raise MaterializationError("M20 contract identity or use envelope changed")
    return document


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_bytes(document: object) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _repository_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as error:
        raise MaterializationError("configured local path escaped the repository") from error
    return path


def _download(archive: dict[str, object], destination: Path, max_bytes: int) -> str:
    expected_bytes = int(archive["bytes"])
    expected_hash = str(archive["sha256"])
    if expected_bytes > max_bytes:
        raise MaterializationError("archive exceeds the frozen compressed-size bound")
    if destination.is_file():
        if destination.stat().st_size == expected_bytes and _sha256(destination) == expected_hash:
            return "VERIFIED_EXISTING"
        raise MaterializationError(f"existing archive failed identity: {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    if partial.exists():
        raise MaterializationError(f"stale partial download requires review: {partial.name}")

    opener = urllib.request.build_opener(_RestrictedRedirect())
    request = urllib.request.Request(
        str(archive["url"]),
        headers={"User-Agent": "whole-home-agent-m20/1"},
    )
    last_error: Exception | None = None
    for attempt in range(2):
        digest = hashlib.sha256()
        byte_count = 0
        try:
            with opener.open(request, timeout=120) as response, partial.open("xb") as output:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    byte_count += len(block)
                    if byte_count > expected_bytes or byte_count > max_bytes:
                        raise MaterializationError("download exceeded the frozen byte count")
                    digest.update(block)
                    output.write(block)
            if byte_count != expected_bytes or digest.hexdigest() != expected_hash:
                raise MaterializationError("downloaded archive failed size or SHA-256")
            os.replace(partial, destination)
            return "DOWNLOADED_AND_VERIFIED"
        except Exception as error:
            last_error = error
            if partial.exists():
                partial.unlink()
            if attempt == 1:
                break
    raise MaterializationError(f"download failed after one retry: {destination.name}") from last_error


def _normalized_member(info: zipfile.ZipInfo, expected_root: str) -> str:
    name = info.filename
    if not name or "\x00" in name or "\\" in name or re.match(r"^[A-Za-z]:", name):
        raise MaterializationError("ZIP member has an ambiguous or drive-qualified path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise MaterializationError("ZIP member has an absolute or traversal path")
    normalized = path.as_posix().rstrip("/")
    if not normalized or path.parts[0] != expected_root:
        raise MaterializationError("ZIP member is outside the frozen top-level root")
    mode = (info.external_attr >> 16) & 0o170000
    if mode == stat.S_IFLNK:
        raise MaterializationError("ZIP symbolic links are prohibited")
    if info.flag_bits & 0x1:
        raise MaterializationError("encrypted ZIP members are prohibited")
    if not info.is_dir() and info.compress_type not in _ALLOWED_COMPRESSION:
        raise MaterializationError("ZIP compression method is outside the frozen set")
    return normalized


def inspect_archive(
    archive_path: Path,
    *,
    expected_root: str,
    maximum_member_count: int,
    maximum_total_uncompressed_bytes: int,
    maximum_single_member_bytes: int,
    maximum_compression_ratio: float,
) -> dict[str, object]:
    """Validate every ZIP header before any member extraction."""

    rows: list[dict[str, object]] = []
    names: set[str] = set()
    total = 0
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if len(infos) > maximum_member_count:
            raise MaterializationError("ZIP member count exceeds the frozen bound")
        for info in infos:
            name = _normalized_member(info, expected_root)
            folded = name.casefold()
            if folded in names:
                raise MaterializationError("ZIP contains duplicate normalized paths")
            names.add(folded)
            if info.file_size > maximum_single_member_bytes:
                raise MaterializationError("ZIP member exceeds the frozen size bound")
            total += info.file_size
            if total > maximum_total_uncompressed_bytes:
                raise MaterializationError("ZIP expansion exceeds the frozen total bound")
            if not info.is_dir() and info.file_size:
                if info.compress_size == 0:
                    raise MaterializationError("non-empty ZIP member has zero compressed bytes")
                if info.file_size / info.compress_size > maximum_compression_ratio:
                    raise MaterializationError("ZIP member exceeds the compression-ratio bound")
            rows.append(
                {
                    "compressed_bytes": info.compress_size,
                    "crc32": f"{info.CRC:08x}",
                    "is_directory": info.is_dir(),
                    "name": name,
                    "uncompressed_bytes": info.file_size,
                }
            )
    return {
        "archive": archive_path.name,
        "member_count": len(rows),
        "members": rows,
        "total_uncompressed_bytes": total,
    }


def _extract_members(
    archive_path: Path,
    inspection: dict[str, object],
    requested: set[str],
    destination_root: Path,
) -> list[dict[str, object]]:
    available = {
        str(item["name"])
        for item in inspection["members"]
        if not bool(item["is_directory"])
    }
    missing = requested - available
    if missing:
        first = sorted(missing)[0]
        raise MaterializationError(f"required BOP member is absent: {first}")
    receipts: list[dict[str, object]] = []
    root = destination_root.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        by_name = {
            info.filename.rstrip("/"): info
            for info in archive.infolist()
            if not info.is_dir()
        }
        for name in sorted(requested):
            info = by_name[name]
            destination = (root / Path(*PurePosixPath(name).parts)).resolve()
            try:
                destination.relative_to(root)
            except ValueError as error:
                raise MaterializationError("extraction destination escaped local root") from error
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise MaterializationError("extraction would overwrite an existing file")
            digest = hashlib.sha256()
            byte_count = 0
            with archive.open(info) as source, destination.open("xb") as output:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    byte_count += len(block)
                    digest.update(block)
                    output.write(block)
            if byte_count != info.file_size:
                raise MaterializationError("extracted member size disagrees with ZIP header")
            receipts.append(
                {"bytes": byte_count, "name": name, "sha256": digest.hexdigest()}
            )
    return receipts


def _target_member_set(targets: object) -> set[str]:
    if not isinstance(targets, list) or not targets:
        raise MaterializationError("BOP'19 target list is absent or invalid")
    frames: set[tuple[int, int]] = set()
    for item in targets:
        if not isinstance(item, dict) or type(item.get("scene_id")) is not int or type(item.get("im_id")) is not int:
            raise MaterializationError("BOP'19 target entry is invalid")
        frames.add((item["scene_id"], item["im_id"]))
    members: set[str] = set()
    for scene_id in sorted({scene for scene, _ in frames}):
        scene_root = f"ycbv/test/{scene_id:06d}"
        members.update(
            {
                f"{scene_root}/scene_camera.json",
                f"{scene_root}/scene_gt.json",
                f"{scene_root}/scene_gt_info.json",
            }
        )
    members.update(
        f"ycbv/test/{scene_id:06d}/rgb/{image_id:06d}.png"
        for scene_id, image_id in frames
    )
    return members


def materialize() -> dict[str, object]:
    contract = _load_contract()
    local_root = _repository_path(str(contract["local_root"]))
    archive_root = local_root / "archives"
    extracted = local_root / "extracted"
    partial_extract = local_root / "extracted.partial"
    receipt_path = _repository_path(str(contract["local_receipt"]))
    if partial_extract.exists():
        raise MaterializationError("stale partial extraction requires review")
    if extracted.exists() or receipt_path.exists():
        raise MaterializationError("existing materialization requires explicit verification")

    cost = contract["cost"]
    assert isinstance(cost, dict)
    archive_receipts: list[dict[str, object]] = []
    inspections: dict[str, dict[str, object]] = {}
    for archive in contract["archive"]:
        assert isinstance(archive, dict)
        path = archive_root / str(archive["name"])
        status = _download(archive, path, int(cost["maximum_compressed_bytes"]))
        actual_hash = _sha256(path)
        if path.stat().st_size != archive["bytes"] or actual_hash != archive["sha256"]:
            raise MaterializationError("verified archive changed before inspection")
        inspection = inspect_archive(
            path,
            expected_root=str(contract["archive_safety"]["expected_top_level_root"]),
            maximum_member_count=int(cost["maximum_member_count"]),
            maximum_total_uncompressed_bytes=int(cost["maximum_total_uncompressed_bytes"]),
            maximum_single_member_bytes=int(cost["maximum_single_member_bytes"]),
            maximum_compression_ratio=float(cost["maximum_compression_ratio"]),
        )
        inspections[path.name] = inspection
        archive_receipts.append(
            {
                "bytes": path.stat().st_size,
                "member_count": inspection["member_count"],
                "name": path.name,
                "sha256": actual_hash,
                "source_revision": contract["source_revision"],
                "status": status,
                "total_uncompressed_bytes": inspection["total_uncompressed_bytes"],
                "url": archive["url"],
            }
        )

    total_uncompressed = sum(int(item["total_uncompressed_bytes"]) for item in archive_receipts)
    if total_uncompressed > int(cost["maximum_total_uncompressed_bytes"]):
        raise MaterializationError("combined ZIP expansion exceeds the frozen total bound")

    base_path = archive_root / "ycbv_base.zip"
    test_path = archive_root / "ycbv_test_bop19.zip"
    base_files = {
        str(item["name"])
        for item in inspections[base_path.name]["members"]
        if not bool(item["is_directory"])
    }
    partial_extract.mkdir(parents=True)
    extracted_rows = _extract_members(
        base_path,
        inspections[base_path.name],
        base_files,
        partial_extract,
    )
    targets_path = partial_extract / "ycbv" / "test_targets_bop19.json"
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    test_members = _target_member_set(targets)
    extracted_rows.extend(
        _extract_members(
            test_path,
            inspections[test_path.name],
            test_members,
            partial_extract,
        )
    )
    os.replace(partial_extract, extracted)

    dataset_root = extracted / "ycbv"
    first = load_and_translate_ycbv_bop19(dataset_root)
    second = load_and_translate_ycbv_bop19(dataset_root)
    first_bytes = _canonical_bytes(first.as_dict())
    if first_bytes != _canonical_bytes(second.as_dict()):
        raise MaterializationError("two D1 translations were not deterministic")
    report = evaluate_target_oracle(first.dataset, ())
    if (
        report.evaluated_frame_count != 2
        or report.negative_frame_count != 1
        or report.reference_transition_count != 0
    ):
        raise MaterializationError("translated D1 slice failed the frozen oracle shape")

    slice_path = local_root / "m20-d1-slice.json"
    slice_path.write_bytes(first_bytes)
    extracted_rows.sort(key=lambda item: str(item["name"]))
    extracted_manifest_hash = hashlib.sha256(
        json.dumps(extracted_rows, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    receipt = {
        "schema_version": 1,
        "status": "MATERIALIZED_LOCAL_ONLY",
        "dataset_id": contract["dataset_id"],
        "license_id": contract["license_id"],
        "license_sources": [
            contract["rights"]["dataset_license_source"],
            contract["rights"]["dataset_license_statement_source"],
            contract["rights"]["institutional_distribution_source"],
        ],
        "source_revision": contract["source_revision"],
        "archives": archive_receipts,
        "extracted_file_count": len(extracted_rows),
        "extracted_files_manifest_sha256": extracted_manifest_hash,
        "slice": first.as_dict(),
        "slice_sha256": hashlib.sha256(first_bytes).hexdigest(),
        "empty_prediction_oracle": report.as_dict(),
        "model_or_prediction_used": False,
        "relation_or_transition_emitted": False,
        "operate_enabled": False,
    }
    receipt_path.write_bytes(_canonical_bytes(receipt))
    return receipt


def main(argv: list[str] | None = None) -> int:
    _parser().parse_args(argv)
    print(json.dumps(materialize(), ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
