"""Run the frozen M25 dual-area diagnostic over pinned YCB-V JSON members."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tools.diagnose_ycbv_annotations import (
    DiagnosticSourceError,
    _canonical_bytes,
    _read_json_member,
    _read_scene_documents,
    _sha256,
)
from whole_home_agent.adapters.bop_d1 import (
    BopD1Error,
    parse_ycbv_bop19_frames,
    ycbv_bop19_target_frame_keys,
)
from whole_home_agent.adapters.bop_diagnostic import diagnose_ycbv_dual_area


CONTRACT = ROOT / "configs" / "evaluation" / "m25-ycbv-small-bbox-alignment-v1.toml"
USE_CLASS = "ANNOTATION_ONLY_DUAL_AREA_TEST_ORACLE_SUITABILITY_DIAGNOSTIC"


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
        or document.get("expected_annotation_member_count") != 37
    ):
        raise DiagnosticSourceError("M25 contract identity or use envelope changed")
    return document


def _repository_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as error:
        raise DiagnosticSourceError("configured path escaped the repository") from error
    return path


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
        raise DiagnosticSourceError("target scope differs from the frozen M25 envelope")

    with zipfile.ZipFile(archive_paths["ycbv_test_bop19.zip"]) as test_archive:
        scene_documents = _read_scene_documents(
            test_archive,
            scene_ids,
            contract["input_access"],
        )
    frames = parse_ycbv_bop19_frames(targets, scene_documents)
    first_document = diagnose_ycbv_dual_area(frames).as_dict()
    second_document = diagnose_ycbv_dual_area(frames).as_dict()
    if _canonical_bytes(first_document) != _canonical_bytes(second_document):
        raise DiagnosticSourceError("two M25 pure diagnostic runs were not byte-identical")
    return {
        "schema_version": 1,
        "gate_id": contract["gate_id"],
        "source_revision": contract["source_revision"],
        "archives": archive_rows,
        "target_entry_count": len(targets),
        "unique_target_frame_count": len(target_frames),
        "scene_ids": scene_ids,
        "annotation_member_count": 1 + 3 * len(scene_ids),
        "pure_diagnostic_run_count": 2,
        "byte_identical_result": True,
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
                    "decision": "STOP_YCBV_SMALL_BBOX_SOURCE_INVALID",
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
