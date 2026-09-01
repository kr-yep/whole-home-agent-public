"""Run the frozen M22 diagnosis directly over pinned YCB-V ZIP JSON members."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from whole_home_agent.adapters.bop_d1 import (
    BopD1Error,
    parse_ycbv_bop19_frames,
    ycbv_bop19_target_frame_keys,
)
from whole_home_agent.adapters.bop_diagnostic import diagnose_ycbv_m21_predicates


CONTRACT = ROOT / "configs" / "evaluation" / "m22-ycbv-annotation-failure-localization-v1.toml"
USE_CLASS = "D0_PUBLIC_REAL_TRANSFER_ORACLE_DIRECTION_DIAGNOSIS"
MAXIMUM_JSON_MEMBER_BYTES = 1024 * 1024 * 1024


class DiagnosticSourceError(RuntimeError):
    """Fail-closed source identity, member, or deterministic-output error."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acknowledge-use-class", choices=(USE_CLASS,), required=True)
    return parser


def _load_contract() -> dict[str, object]:
    document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    if (
        document.get("status") != "FROZEN_BEFORE_REAL_ANNOTATION_REREAD"
        or document.get("intended_use") != USE_CLASS
        or document.get("source_revision")
        != "5c2c4aa229800355648cd268040aa814f8dc94f0"
    ):
        raise DiagnosticSourceError("M22 contract identity or use envelope changed")
    return document


def _repository_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as error:
        raise DiagnosticSourceError("configured path escaped the repository") from error
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strict_json_bytes(payload: bytes, *, member_name: str) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise DiagnosticSourceError(
                    f"duplicate JSON key in allowlisted member: {member_name}"
                )
            result[key] = value
        return result

    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DiagnosticSourceError(
            f"invalid JSON in allowlisted member: {member_name}"
        ) from error


def _read_json_member(archive: zipfile.ZipFile, member_name: str) -> object:
    try:
        info = archive.getinfo(member_name)
    except KeyError as error:
        raise DiagnosticSourceError(f"allowlisted member is absent: {member_name}") from error
    if info.is_dir() or info.file_size > MAXIMUM_JSON_MEMBER_BYTES:
        raise DiagnosticSourceError(f"allowlisted JSON member is invalid: {member_name}")
    payload = archive.read(info)
    if len(payload) != info.file_size:
        raise DiagnosticSourceError(f"allowlisted member size changed: {member_name}")
    return _strict_json_bytes(payload, member_name=member_name)


def _canonical_bytes(document: object) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def diagnose() -> dict[str, object]:
    contract = _load_contract()
    archive_root = _repository_path(str(contract["source_archive_root"]))
    archive_paths: dict[str, Path] = {}
    archive_rows: list[dict[str, object]] = []
    for archive in contract["archive"]:
        assert isinstance(archive, dict)
        path = archive_root / str(archive["name"])
        if not path.is_file():
            raise DiagnosticSourceError(f"pinned local archive is absent: {path.name}")
        actual_bytes = path.stat().st_size
        actual_hash = _sha256(path)
        if actual_bytes != archive["bytes"] or actual_hash != archive["sha256"]:
            raise DiagnosticSourceError(f"pinned local archive identity failed: {path.name}")
        archive_paths[path.name] = path
        archive_rows.append(
            {
                "name": path.name,
                "bytes": actual_bytes,
                "sha256": actual_hash,
                "status": "VERIFIED_EXISTING",
            }
        )

    with zipfile.ZipFile(archive_paths["ycbv_base.zip"]) as base_archive:
        targets = _read_json_member(
            base_archive,
            str(contract["input_access"]["target_member"]),
        )
    target_frames = ycbv_bop19_target_frame_keys(targets)
    scene_ids = sorted({scene_id for scene_id, _ in target_frames})
    if (
        not isinstance(targets, list)
        or len(targets) != contract["expected_target_entry_count"]
        or len(target_frames) != contract["expected_unique_target_frame_count"]
        or scene_ids != contract["expected_scene_ids"]
    ):
        raise DiagnosticSourceError("target scope differs from the frozen M22 envelope")

    scene_documents: dict[int, tuple[object, object, object]] = {}
    with zipfile.ZipFile(archive_paths["ycbv_test_bop19.zip"]) as test_archive:
        for scene_id in scene_ids:
            documents: list[object] = []
            for name in contract["input_access"]["scene_members"]:
                member_name = str(contract["input_access"]["scene_member_template"]).format(
                    scene_id=scene_id,
                    name=name,
                )
                documents.append(_read_json_member(test_archive, member_name))
            scene_documents[scene_id] = tuple(documents)  # type: ignore[assignment]

    frames = parse_ycbv_bop19_frames(targets, scene_documents)
    first = diagnose_ycbv_m21_predicates(frames)
    second = diagnose_ycbv_m21_predicates(frames)
    first_document = first.as_dict()
    if _canonical_bytes(first_document) != _canonical_bytes(second.as_dict()):
        raise DiagnosticSourceError("two annotation diagnostics were not byte-identical")
    return {
        "schema_version": 1,
        "gate_id": contract["gate_id"],
        "source_revision": contract["source_revision"],
        "archives": archive_rows,
        "target_entry_count": len(targets),
        "unique_target_frame_count": len(target_frames),
        "scene_ids": scene_ids,
        "annotation_member_count": 1 + 3 * len(scene_ids),
        "diagnostic": first_document,
        "filesystem_extraction_used": False,
        "media_member_read": False,
        "model_or_prediction_used": False,
        "operate_enabled": False,
    }


def main(argv: list[str] | None = None) -> int:
    _parser().parse_args(argv)
    try:
        document = diagnose()
    except (DiagnosticSourceError, BopD1Error, zipfile.BadZipFile) as error:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "decision": "STOP_YCBV_DIAGNOSTIC_SOURCE_INVALID",
                    "error_type": type(error).__name__,
                    "filesystem_extraction_used": False,
                    "media_member_read": False,
                    "model_or_prediction_used": False,
                    "operate_enabled": False,
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
