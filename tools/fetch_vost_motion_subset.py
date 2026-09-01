"""Fetch a frozen VOST subset through verified HTTP byte ranges.

The 54 GB upstream ZIP is never downloaded as a whole. The tool pins the S3
object version, verifies the central directory, extracts only configured
members, and writes all third-party bytes beneath the Git-ignored data root.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import urllib.request
import zlib


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from whole_home_agent.adapters.vost import (
    VostMotionScreenManifest,
    load_vost_motion_screen_manifest,
)


CONFIG = ROOT / "configs" / "evaluation" / "vost-motion-screen-v1.toml"
USE_CLASS = "D0_PUBLIC_NONCOMMERCIAL_MOTION_SCREENING"
CENTRAL_HEADER = struct.Struct("<4s6H3L5H2L")
LOCAL_HEADER = struct.Struct("<4s5H3L2H")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch the frozen non-commercial VOST motion-screen subset."
    )
    parser.add_argument(
        "--acknowledge-use-class",
        choices=(USE_CLASS,),
        required=True,
        help="Required acknowledgement of the configured non-commercial use envelope.",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG,
        help="Repository-local frozen VOST screen config (defaults to motion screen v1).",
    )
    return parser


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(rows: list[dict[str, object]]) -> str:
    value = json.dumps(rows, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _validate_response_identity(response, manifest: VostMotionScreenManifest) -> None:
    version_id = response.headers.get("x-amz-version-id")
    etag = response.headers.get("ETag", "").strip('"')
    if version_id != manifest.archive_version_id or etag != manifest.archive_etag:
        raise RuntimeError("VOST S3 object identity disagrees with the frozen config")


def _verify_head(manifest: VostMotionScreenManifest) -> None:
    request = urllib.request.Request(manifest.archive_url, method="HEAD")
    with urllib.request.urlopen(request, timeout=60) as response:
        _validate_response_identity(response, manifest)
        if int(response.headers.get("Content-Length", "-1")) != manifest.archive_bytes:
            raise RuntimeError("VOST archive length disagrees with the frozen config")
        if response.headers.get("Accept-Ranges", "").lower() != "bytes":
            raise RuntimeError("VOST archive no longer advertises byte-range support")


def _fetch_range(
    manifest: VostMotionScreenManifest,
    start: int,
    end: int,
) -> bytes:
    request = urllib.request.Request(
        manifest.archive_url,
        headers={"Range": f"bytes={start}-{end}"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        if response.status != 206:
            raise RuntimeError(f"VOST server did not honor Range: {response.status}")
        _validate_response_identity(response, manifest)
        expected = f"bytes {start}-{end}/{manifest.archive_bytes}"
        if response.headers.get("Content-Range") != expected:
            raise RuntimeError("VOST Content-Range disagrees with the request")
        value = response.read()
    if len(value) != end - start + 1:
        raise RuntimeError("VOST range response has the wrong length")
    return value


def _zip64_values(extra: bytes) -> list[int]:
    cursor = 0
    while cursor + 4 <= len(extra):
        field_id, field_length = struct.unpack_from("<HH", extra, cursor)
        cursor += 4
        value = extra[cursor : cursor + field_length]
        cursor += field_length
        if field_id == 0x0001:
            return [item[0] for item in struct.iter_unpack("<Q", value[: len(value) // 8 * 8])]
    return []


def _central_entries(data: bytes) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    cursor = 0
    while cursor < len(data):
        values = CENTRAL_HEADER.unpack_from(data, cursor)
        if values[0] != b"PK\x01\x02":
            raise RuntimeError(f"invalid central-directory signature at {cursor}")
        flag, compression = values[3], values[4]
        crc32, compressed_size, uncompressed_size = values[7:10]
        name_length, extra_length, comment_length = values[10:13]
        local_header_offset = values[16]
        body = cursor + CENTRAL_HEADER.size
        raw_name = data[body : body + name_length]
        extra = data[body + name_length : body + name_length + extra_length]
        name = raw_name.decode("utf-8" if flag & 0x800 else "cp437")
        zip64 = iter(_zip64_values(extra))
        if uncompressed_size == 0xFFFFFFFF:
            uncompressed_size = next(zip64)
        if compressed_size == 0xFFFFFFFF:
            compressed_size = next(zip64)
        if local_header_offset == 0xFFFFFFFF:
            local_header_offset = next(zip64)
        entries.append(
            {
                "name": name,
                "compression": compression,
                "crc32": crc32,
                "compressed_size": compressed_size,
                "uncompressed_size": uncompressed_size,
                "local_header_offset": local_header_offset,
            }
        )
        cursor = body + name_length + extra_length + comment_length
    return entries


def _safe_destination(root: Path, relative: Path) -> Path:
    destination = (root / relative).resolve()
    try:
        destination.relative_to(root)
    except ValueError as error:
        raise RuntimeError("VOST archive member escaped the local data root") from error
    return destination


def _extract_member(
    manifest: VostMotionScreenManifest,
    entry: dict[str, object],
    end: int,
    destination: Path,
) -> dict[str, object]:
    expected_bytes = int(entry["uncompressed_size"])
    expected_crc = int(entry["crc32"])
    if destination.is_file():
        decoded = destination.read_bytes()
    else:
        start = int(entry["local_header_offset"])
        record = _fetch_range(manifest, start, end)
        header = LOCAL_HEADER.unpack_from(record)
        if header[0] != b"PK\x03\x04":
            raise RuntimeError(f"invalid local header for {entry['name']}")
        name_length, extra_length = header[-2:]
        data_offset = LOCAL_HEADER.size + name_length + extra_length
        compressed_size = int(entry["compressed_size"])
        compressed = record[data_offset : data_offset + compressed_size]
        compression = int(entry["compression"])
        if compression == 0:
            decoded = compressed
        elif compression == 8:
            decoded = zlib.decompress(compressed, -15)
        else:
            raise RuntimeError(f"unsupported ZIP compression: {compression}")
        if len(decoded) != expected_bytes or zlib.crc32(decoded) & 0xFFFFFFFF != expected_crc:
            raise RuntimeError(f"VOST member failed ZIP verification: {entry['name']}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".part")
        if temporary.exists():
            raise RuntimeError(f"stale partial VOST file requires inspection: {temporary}")
        temporary.write_bytes(decoded)
        os.replace(temporary, destination)
    if len(decoded) != expected_bytes or zlib.crc32(decoded) & 0xFFFFFFFF != expected_crc:
        raise RuntimeError(f"existing VOST member failed verification: {entry['name']}")
    return {
        "bytes": len(decoded),
        "crc32": f"{expected_crc:08x}",
        "sha256": hashlib.sha256(decoded).hexdigest(),
    }


def _entry_end_offsets(
    entries: list[dict[str, object]],
    central_directory_offset: int,
) -> dict[str, int]:
    ordered = sorted(entries, key=lambda item: int(item["local_header_offset"]))
    result: dict[str, int] = {}
    for index, entry in enumerate(ordered):
        following = (
            int(ordered[index + 1]["local_header_offset"])
            if index + 1 < len(ordered)
            else central_directory_offset
        )
        result[str(entry["name"])] = following - 1
    return result


def _fetch_subset(manifest: VostMotionScreenManifest, workers: int) -> dict[str, object]:
    _verify_head(manifest)
    start = manifest.central_directory_offset
    end = start + manifest.central_directory_bytes - 1
    central = _fetch_range(manifest, start, end)
    if _sha256_bytes(central) != manifest.central_directory_sha256:
        raise RuntimeError("VOST central directory failed SHA-256 verification")
    entries = _central_entries(central)
    if len(entries) != manifest.central_directory_entries:
        raise RuntimeError("VOST central-directory entry count is invalid")
    by_name = {str(entry["name"]): entry for entry in entries}
    if len(by_name) != len(entries):
        raise RuntimeError("VOST ZIP contains duplicate member names")
    end_offsets = _entry_end_offsets(entries, manifest.central_directory_offset)

    jobs: list[tuple[str, str, str, dict[str, object], Path]] = []
    for spec in manifest.sequences:
        for source_kind, suffix in (("JPEGImages", ".jpg"), ("Annotations", ".png")):
            for index in range(spec.frame_count):
                offset = index * spec.source_frame_step
                member = f"VOST/{source_kind}/{spec.sequence_id}/frame{offset:05d}{suffix}"
                entry = by_name.get(member)
                if entry is None:
                    raise RuntimeError(f"configured VOST member is missing: {member}")
                destination = _safe_destination(
                    manifest.local_root, Path(*member.split("/"))
                )
                jobs.append((spec.split, spec.sequence_id, member, entry, destination))

    artifact_jobs = []
    for artifact in manifest.upstream_artifacts:
        entry = by_name.get(artifact.member)
        if entry is None:
            raise RuntimeError(f"configured VOST upstream member is missing: {artifact.member}")
        artifact_jobs.append((artifact, entry))

    receipts: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _extract_member,
                manifest,
                entry,
                end_offsets[member],
                destination,
            ): (split, sequence, member)
            for split, sequence, member, entry, destination in jobs
        }
        for future in as_completed(futures):
            split, sequence, member = futures[future]
            receipt = future.result()
            receipts.append(
                {
                    "member": member,
                    **receipt,
                    "split": split,
                    "sequence": sequence,
                }
            )
            if len(receipts) % 50 == 0:
                print(f"verified {len(receipts)}/{len(jobs)} data files", flush=True)

    for artifact, entry in artifact_jobs:
        receipt = _extract_member(
            manifest,
            entry,
            end_offsets[artifact.member],
            artifact.path,
        )
        if receipt["bytes"] != artifact.bytes or receipt["sha256"] != artifact.sha256:
            raise RuntimeError(f"VOST upstream artifact hash mismatch: {artifact.kind}")

    receipts.sort(key=lambda item: str(item["member"]))
    actual_bytes = sum(int(item["bytes"]) for item in receipts)
    actual_hash = _canonical_hash(receipts)
    if (
        len(receipts) != manifest.subset_file_count
        or actual_bytes != manifest.subset_bytes
        or actual_hash != manifest.subset_files_manifest_sha256
    ):
        raise RuntimeError(
            "VOST fetched subset disagrees with the frozen aggregate: "
            f"files={len(receipts)}, bytes={actual_bytes}, sha256={actual_hash}"
        )
    document = {
        "schema_version": 1,
        "dataset": "VOST",
        "license": "CC BY-NC-SA 4.0",
        "source_url": manifest.archive_url,
        "sequences": {
            item.split: item.sequence_id for item in manifest.sequences
        },
        "file_count": len(receipts),
        "files": receipts,
        "files_manifest_sha256": manifest.subset_files_manifest_sha256,
    }
    manifest_path = manifest.local_root / "subset-manifest.json"
    encoded = (
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    manifest_status = "CREATED"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        existing_rows = existing.get("files")
        if (
            existing.get("files_manifest_sha256")
            != manifest.subset_files_manifest_sha256
            or not isinstance(existing_rows, list)
            or _canonical_hash(existing_rows)
            != manifest.subset_files_manifest_sha256
        ):
            raise RuntimeError("existing VOST subset manifest records different source bytes")
        manifest_status = "VERIFIED_EXISTING"
    else:
        manifest_path.write_bytes(encoded)
    return {
        "archive_bytes_avoided": manifest.archive_bytes - manifest.subset_bytes,
        "central_directory_sha256": manifest.central_directory_sha256,
        "file_count": len(receipts),
        "local_bytes": manifest.subset_bytes,
        "manifest": manifest_path.as_posix(),
        "manifest_status": manifest_status,
        "operate": "DISABLED",
        "source_version_id": manifest.archive_version_id,
        "subset_files_manifest_sha256": manifest.subset_files_manifest_sha256,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not 1 <= args.workers <= 16:
        _parser().error("--workers must be between 1 and 16")
    manifest = load_vost_motion_screen_manifest(args.config, repository_root=ROOT)
    result = _fetch_subset(manifest, args.workers)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
