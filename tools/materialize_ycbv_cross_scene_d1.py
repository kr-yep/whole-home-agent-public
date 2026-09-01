"""Materialize the frozen M24 two-frame YCB-V test oracle without model work."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.diagnose_ycbv_annotations import _read_json_member
from tools.materialize_ycbv_bop19 import (
    _verify_existing_archive,
    inspect_archive,
    validate_destination_namespace,
)
from whole_home_agent.adapters.bop_d1 import (
    BopCrossSceneD1Slice,
    cross_scene_slice_oracle_document,
    parse_ycbv_bop19_frames,
    select_cross_scene_ycbv_bop19_slice,
    ycbv_bop19_target_frame_keys,
)
from whole_home_agent.target_oracle import (
    evaluate_target_oracle,
    load_target_oracle_fixture,
    validate_source_group_splits,
)


CONTRACT = ROOT / "configs" / "evaluation" / "m24-ycbv-cross-scene-d1-materialization-v1.toml"
M21_CONTRACT = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"
USE_CLASS = "TEST_ONLY_MINIMAL_DETECTOR_TRANSFER_ORACLE"
M21_CONTRACT_SHA256 = "e10bee030cf0469bedf71f1e562d40624984d7bc66fbfaf210faf6d8ba6bc0a6"
M24_CONTRACT_REVISION = "4e0be76ddd64def94f47b4bbb733dd200671ba42"


class M24MaterializationError(RuntimeError):
    """Fail-closed M24 source, selection, or output error."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acknowledge-use-class", choices=(USE_CLASS,), required=True)
    return parser


def _load_contracts() -> tuple[dict[str, object], dict[str, object]]:
    if hashlib.sha256(M21_CONTRACT.read_bytes()).hexdigest() != M21_CONTRACT_SHA256:
        raise M24MaterializationError("M21 archive contract bytes changed")
    contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    m21 = tomllib.loads(M21_CONTRACT.read_text(encoding="utf-8"))
    if (
        contract.get("status")
        != "FROZEN_BEFORE_SOURCE_ARCHIVE_ANNOTATION_OR_MEDIA_REREAD"
        or contract.get("intended_use") != USE_CLASS
        or contract.get("source_revision") != m21.get("source_revision")
        or contract.get("source_archive_root") != m21.get("source_archive_root")
        or contract.get("target_frame_count") != 2
    ):
        raise M24MaterializationError("M24 contract identity or authority changed")
    if contract["archive_reuse"]["exact_m21_archive_table_required"] is not True:
        raise M24MaterializationError("M21 archive inheritance is not mandatory")
    return contract, m21


def _repository_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as error:
        raise M24MaterializationError("configured path escaped the repository") from error
    return path


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(document: object) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _read_scene_documents(
    archive: zipfile.ZipFile, scene_ids: tuple[int, ...]
) -> dict[int, tuple[object, object, object]]:
    documents: dict[int, tuple[object, object, object]] = {}
    for scene_id in scene_ids:
        prefix = f"test/{scene_id:06d}"
        documents[scene_id] = (
            _read_json_member(archive, f"{prefix}/scene_gt.json"),
            _read_json_member(archive, f"{prefix}/scene_gt_info.json"),
            _read_json_member(archive, f"{prefix}/scene_camera.json"),
        )
    return documents


def _read_rgb_member(archive: zipfile.ZipFile, member_name: str) -> bytes:
    try:
        info = archive.getinfo(member_name)
    except KeyError as error:
        raise M24MaterializationError(f"selected RGB is absent: {member_name}") from error
    if info.is_dir() or info.file_size <= 24 or info.file_size > 16 * 1024 * 1024:
        raise M24MaterializationError("selected RGB member size is invalid")
    payload = archive.read(info)
    if len(payload) != info.file_size:
        raise M24MaterializationError("selected RGB size disagrees with its header")
    if (
        payload[:8] != b"\x89PNG\r\n\x1a\n"
        or payload[12:16] != b"IHDR"
        or struct.unpack(">II", payload[16:24]) != (640, 480)
    ):
        raise M24MaterializationError("selected RGB is not a 640x480 PNG")
    return payload


def _artifact_records(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        records.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": len(payload),
                "sha256": _sha256_bytes(payload),
            }
        )
    return records


def write_clean_d1(
    output_root: Path,
    *,
    selected: BopCrossSceneD1Slice,
    rgb_payloads: tuple[bytes, bytes],
    source_revision: str,
    archive_rows: list[dict[str, object]],
    use_class: str = USE_CLASS,
) -> list[dict[str, object]]:
    """Write one clean deterministic output from two already-validated RGB payloads."""

    if output_root.exists():
        raise M24MaterializationError("clean output root already exists")
    if len(selected.source_frames) != 2 or len(rgb_payloads) != 2:
        raise M24MaterializationError("M24 output requires exactly two frames")
    (output_root / "rgb").mkdir(parents=True)
    for index, payload in enumerate(rgb_payloads):
        (output_root / "rgb" / f"{index:06d}.png").write_bytes(payload)

    oracle_bytes = _canonical_bytes(
        cross_scene_slice_oracle_document(selected, use_class=use_class)
    )
    (output_root / "oracle.json").write_bytes(oracle_bytes)
    media_rows: list[dict[str, object]] = []
    for frame, payload in zip(selected.source_frames, rgb_payloads, strict=True):
        index = int(frame["d1_frame_index"])
        media_rows.append(
            {
                **frame,
                "local_path": f"rgb/{index:06d}.png",
                "source_member": (
                    f"test/{int(frame['source_scene_id']):06d}/rgb/"
                    f"{int(frame['source_image_id']):06d}.png"
                ),
                "rgb_bytes": len(payload),
                "rgb_sha256": _sha256_bytes(payload),
            }
        )
    manifest = {
        "schema_version": 1,
        "dataset_id": selected.dataset.dataset_id,
        "use_class": use_class,
        "project_split": "test",
        "source_revision": source_revision,
        "source_archives": archive_rows,
        "license": {
            "id": "MIT",
            "statement_source": (
                "https://github.com/yuxng/YCB_Video_toolbox"
            ),
            "text_source": (
                "https://github.com/yuxng/YCB_Video_toolbox/blob/master/LICENSE"
            ),
        },
        "coordinate_space": "PIXEL_XYXY_EXCLUSIVE_640X480",
        "selected_object_id": selected.selected_object_id,
        "selected_label": selected.selected_label,
        "frames": media_rows,
        "oracle": {
            "path": "oracle.json",
            "bytes": len(oracle_bytes),
            "sha256": _sha256_bytes(oracle_bytes),
        },
        "reference_transition_count": 0,
        "relation_or_movement_truth_emitted": False,
        "model_or_prediction_used": False,
        "operate_enabled": False,
    }
    (output_root / "manifest.json").write_bytes(_canonical_bytes(manifest))
    records = _artifact_records(output_root)
    expected = ["manifest.json", "oracle.json", "rgb/000000.png", "rgb/000001.png"]
    if [str(item["path"]) for item in records] != expected:
        raise M24MaterializationError("M24 output file set differs from the frozen set")
    return records


def _remove_staging(path: Path, local_root: Path) -> None:
    if not path.exists():
        return
    try:
        path.resolve().relative_to(local_root.resolve())
    except ValueError as error:
        raise M24MaterializationError("staging path escaped local root") from error
    shutil.rmtree(path)


def materialize() -> dict[str, object]:
    contract, m21 = _load_contracts()
    archive_root = _repository_path(str(contract["source_archive_root"]))
    local_root = _repository_path(str(contract["local_root"]))
    final_root = _repository_path(str(contract["local_d1_root"]))
    receipt_path = _repository_path(str(contract["local_receipt"]))
    stage_a = local_root / "d1.run-a.partial"
    stage_b = local_root / "d1.run-b.partial"
    receipt_partial = local_root / "m24-local-receipt.partial"
    if final_root.exists() or receipt_path.exists():
        raise M24MaterializationError("existing M24 output requires explicit verification")
    local_root.mkdir(parents=True, exist_ok=True)
    for staging in (stage_a, stage_b):
        _remove_staging(staging, local_root)
    if receipt_partial.exists():
        receipt_partial.unlink()

    cost = m21["cost"]
    inspections: dict[str, dict[str, object]] = {}
    archive_rows: list[dict[str, object]] = []
    archive_paths: dict[str, Path] = {}
    for archive in m21["archive"]:
        assert isinstance(archive, dict)
        path = archive_root / str(archive["name"])
        _verify_existing_archive(archive, path, int(cost["maximum_compressed_bytes"]))
        inspection = inspect_archive(
            path,
            expected_root=str(archive["source_root"]),
            destination_root=str(archive["destination_root"]),
            maximum_member_count=int(cost["maximum_member_count"]),
            maximum_total_uncompressed_bytes=int(cost["maximum_total_uncompressed_bytes"]),
            maximum_single_member_bytes=int(cost["maximum_single_member_bytes"]),
            maximum_compression_ratio=float(cost["maximum_compression_ratio"]),
        )
        inspections[path.name] = inspection
        archive_paths[path.name] = path
        archive_rows.append(
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": str(archive["sha256"]),
                "source_revision": str(contract["source_revision"]),
                "member_count": inspection["member_count"],
                "uncompressed_bytes": inspection["total_uncompressed_bytes"],
            }
        )
    if (
        sum(int(item["member_count"]) for item in archive_rows)
        != contract["archive_reuse"]["expected_combined_member_count"]
        or sum(int(item["uncompressed_bytes"]) for item in archive_rows)
        != contract["archive_reuse"]["expected_combined_uncompressed_bytes"]
    ):
        raise M24MaterializationError("combined archive header evidence changed")
    validate_destination_namespace(inspections)

    with zipfile.ZipFile(archive_paths["ycbv_base.zip"]) as base_archive:
        targets = _read_json_member(base_archive, "ycbv/test_targets_bop19.json")
    target_keys = ycbv_bop19_target_frame_keys(targets)
    scene_ids = tuple(sorted({scene_id for scene_id, _ in target_keys}))
    if (
        len(target_keys) != contract["expected_target_frame_count"]
        or list(scene_ids) != contract["expected_scene_ids"]
    ):
        raise M24MaterializationError("BOP target-frame scope changed")

    with zipfile.ZipFile(archive_paths["ycbv_test_bop19.zip"]) as test_archive:
        documents = _read_scene_documents(test_archive, scene_ids)
        frames = parse_ycbv_bop19_frames(targets, documents)
        if len(frames) != contract["expected_target_frame_count"]:
            raise M24MaterializationError("parsed frame completeness changed")
        selected = select_cross_scene_ycbv_bop19_slice(frames)
        member_names = tuple(
            f"test/{int(frame['source_scene_id']):06d}/rgb/"
            f"{int(frame['source_image_id']):06d}.png"
            for frame in selected.source_frames
        )
        if len(set(member_names)) != contract["archive_reuse"]["rgb_unique_member_read_count"]:
            raise M24MaterializationError("selected RGB member count changed")
        loaded_rgb_payloads = tuple(
            _read_rgb_member(test_archive, member_name) for member_name in member_names
        )
        if len(loaded_rgb_payloads) != 2:
            raise M24MaterializationError("M24 did not read exactly two RGB payloads")
        rgb_payloads = (loaded_rgb_payloads[0], loaded_rgb_payloads[1])

    try:
        first_records = write_clean_d1(
            stage_a,
            selected=selected,
            rgb_payloads=rgb_payloads,
            source_revision=str(contract["source_revision"]),
            archive_rows=archive_rows,
        )
        second_records = write_clean_d1(
            stage_b,
            selected=selected,
            rgb_payloads=rgb_payloads,
            source_revision=str(contract["source_revision"]),
            archive_rows=archive_rows,
        )
        if first_records != second_records:
            raise M24MaterializationError("two clean M24 outputs were not byte-identical")
        loaded = load_target_oracle_fixture(
            stage_a / "oracle.json",
            allowed_use_classes=frozenset({USE_CLASS}),
        )
        validate_source_group_splits(loaded.split_groups)
        report = evaluate_target_oracle(loaded.dataset, loaded.predictions_for("empty"))
        if (
            report.evaluated_frame_count != 2
            or report.negative_frame_count != 1
            or sum(count for _, count in report.quality.size_target_count) != 1
            or len(loaded.dataset.sequences) != 2
            or report.reference_transition_count != 0
        ):
            raise M24MaterializationError("M16 oracle shape differs from the frozen gate")
        receipt = {
            "schema_version": 1,
            "status": "MATERIALIZED_LOCAL_ONLY",
            "decision": contract["decision"]["pass"],
            "contract_revision": M24_CONTRACT_REVISION,
            "source_revision": contract["source_revision"],
            "license_id": contract["license_id"],
            "archives": archive_rows,
            "archive_header_preflight_passed": True,
            "mapped_namespace_preflight_passed": True,
            "target_frame_count": len(target_keys),
            "annotation_member_count": 1 + 3 * len(scene_ids),
            "unique_rgb_member_read_count": len(set(member_names)),
            "selection": selected.as_dict(),
            "output_files": first_records,
            "output_manifest_sha256": _sha256_bytes(_canonical_bytes(first_records)),
            "clean_materialization_runs": 2,
            "byte_identical_outputs": True,
            "empty_prediction_oracle": report.as_dict(),
            "model_or_prediction_used": False,
            "relation_or_transition_emitted": False,
            "operate_enabled": False,
        }
        receipt_partial.write_bytes(_canonical_bytes(receipt))
        _remove_staging(stage_b, local_root)
        os.replace(stage_a, final_root)
        try:
            os.replace(receipt_partial, receipt_path)
        except Exception:
            _remove_staging(final_root, local_root)
            raise
        return receipt
    except Exception:
        _remove_staging(stage_a, local_root)
        _remove_staging(stage_b, local_root)
        if receipt_partial.exists():
            receipt_partial.unlink()
        raise


def main(argv: list[str] | None = None) -> int:
    _parser().parse_args(argv)
    print(json.dumps(materialize(), ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
