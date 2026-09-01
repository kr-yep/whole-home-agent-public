"""Materialize the exact frozen M26 YCB-V dual-area pair without model work."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tools.diagnose_ycbv_annotations import _read_json_member
from tools.materialize_ycbv_bop19 import (
    _verify_existing_archive,
    inspect_archive,
    validate_destination_namespace,
)
from tools.materialize_ycbv_cross_scene_d1 import (
    _canonical_bytes,
    _read_rgb_member,
    _read_scene_documents,
    _remove_staging,
    _sha256_bytes,
    write_clean_d1,
)
from whole_home_agent.adapters.bop_d1 import (
    parse_ycbv_bop19_frames,
    select_exact_cross_scene_ycbv_bop19_slice,
    ycbv_bop19_target_frame_keys,
)
from whole_home_agent.target_oracle import (
    evaluate_target_oracle,
    load_target_oracle_fixture,
    validate_source_group_splits,
)


CONTRACT = ROOT / "configs" / "evaluation" / "m26-ycbv-dual-area-replacement-d1-v1.toml"
M21_CONTRACT = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"
M25_RESULT = ROOT / "configs" / "evaluation" / "m25-ycbv-small-bbox-alignment-result-v1.toml"
USE_CLASS = "TEST_ONLY_MINIMAL_DETECTOR_TRANSFER_ORACLE"
M26_CONTRACT_REVISION = "ac4b0a649179a4cbc721d61439e11f486a058d6f"


class M26MaterializationError(RuntimeError):
    """Fail-closed M26 source, exact-selection, metric, or output error."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acknowledge-use-class", choices=(USE_CLASS,), required=True)
    return parser


def _load_contracts() -> tuple[dict[str, object], dict[str, object]]:
    contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    m21 = tomllib.loads(M21_CONTRACT.read_text(encoding="utf-8"))
    m25 = tomllib.loads(M25_RESULT.read_text(encoding="utf-8"))
    identity = contract["contract_identity"]
    if (
        hashlib.sha256(M21_CONTRACT.read_bytes()).hexdigest() != identity["m21_contract_sha256"]
        or hashlib.sha256(M25_RESULT.read_bytes()).hexdigest() != identity["m25_result_sha256"]
        or m25.get("decision") != "SELECT_DUAL_AREA_CROSS_SCENE_PAIR"
        or m25.get("verification", {}).get("clean_result_revision")
        != identity["m25_clean_result_revision"]
    ):
        raise M26MaterializationError("pinned M21 or M25 contract bytes changed")
    if (
        contract.get("status")
        != "FROZEN_BEFORE_SOURCE_ARCHIVE_ANNOTATION_OR_MEDIA_REREAD"
        or contract.get("intended_use") != USE_CLASS
        or contract.get("source_revision") != m21.get("source_revision")
        or contract.get("source_archive_root") != m21.get("source_archive_root")
        or contract.get("target_frame_count") != 2
    ):
        raise M26MaterializationError("M26 contract identity or authority changed")
    return contract, m21


def _repository_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as error:
        raise M26MaterializationError("configured path escaped the repository") from error
    return path


def materialize() -> dict[str, object]:
    contract, m21 = _load_contracts()
    archive_root = _repository_path(str(contract["source_archive_root"]))
    local_root = _repository_path(str(contract["local_root"]))
    final_root = _repository_path(str(contract["local_d1_root"]))
    receipt_path = _repository_path(str(contract["local_receipt"]))
    stage_a = local_root / "d1.run-a.partial"
    stage_b = local_root / "d1.run-b.partial"
    receipt_partial = local_root / "m26-local-receipt.partial"
    if final_root.exists() or receipt_path.exists():
        raise M26MaterializationError("existing M26 output requires explicit verification")
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
    reuse = contract["archive_reuse"]
    if (
        sum(int(item["member_count"]) for item in archive_rows)
        != reuse["expected_combined_member_count"]
        or sum(int(item["uncompressed_bytes"]) for item in archive_rows)
        != reuse["expected_combined_uncompressed_bytes"]
    ):
        raise M26MaterializationError("combined archive header evidence changed")
    validate_destination_namespace(inspections)

    with zipfile.ZipFile(archive_paths["ycbv_base.zip"]) as base_archive:
        targets = _read_json_member(base_archive, "ycbv/test_targets_bop19.json")
    target_keys = ycbv_bop19_target_frame_keys(targets)
    scene_ids = tuple(sorted({scene_id for scene_id, _ in target_keys}))
    if (
        len(target_keys) != contract["expected_target_frame_count"]
        or list(scene_ids) != contract["expected_scene_ids"]
    ):
        raise M26MaterializationError("BOP target-frame scope changed")

    selection = contract["selection"]
    positive = selection["positive"]
    negative = selection["negative"]
    with zipfile.ZipFile(archive_paths["ycbv_test_bop19.zip"]) as test_archive:
        documents = _read_scene_documents(test_archive, scene_ids)
        frames = parse_ycbv_bop19_frames(targets, documents)
        if len(frames) != contract["expected_target_frame_count"]:
            raise M26MaterializationError("parsed frame completeness changed")
        selected = select_exact_cross_scene_ycbv_bop19_slice(
            frames,
            object_id=int(selection["selected_object_id"]),
            positive_identity=(int(positive["source_scene_id"]), int(positive["source_image_id"])),
            negative_identity=(int(negative["source_scene_id"]), int(negative["source_image_id"])),
            expected_bbox_visible_xywh=tuple(int(value) for value in positive["bbox_visible_xywh"]),
            expected_visible_pixel_area_fraction=float(positive["visible_pixel_area_fraction"]),
            expected_bbox_area_fraction=float(positive["bbox_area_fraction"]),
            expected_visible_fraction=float(positive["visible_fraction"]),
        )
        member_names = tuple(
            f"test/{int(frame['source_scene_id']):06d}/rgb/"
            f"{int(frame['source_image_id']):06d}.png"
            for frame in selected.source_frames
        )
        expected_members = (
            "test/000050/rgb/000722.png",
            "test/000048/rgb/000001.png",
        )
        if member_names != expected_members or len(set(member_names)) != 2:
            raise M26MaterializationError("exact RGB member allowlist changed")
        loaded = tuple(_read_rgb_member(test_archive, name) for name in member_names)
        rgb_payloads = (loaded[0], loaded[1])

    try:
        first_records = write_clean_d1(
            stage_a,
            selected=selected,
            rgb_payloads=rgb_payloads,
            source_revision=str(contract["source_revision"]),
            archive_rows=archive_rows,
            use_class=USE_CLASS,
        )
        second_records = write_clean_d1(
            stage_b,
            selected=selected,
            rgb_payloads=rgb_payloads,
            source_revision=str(contract["source_revision"]),
            archive_rows=archive_rows,
            use_class=USE_CLASS,
        )
        if first_records != second_records:
            raise M26MaterializationError("two clean M26 outputs were not byte-identical")
        fixture = load_target_oracle_fixture(
            stage_a / "oracle.json",
            allowed_use_classes=frozenset({USE_CLASS}),
        )
        validate_source_group_splits(fixture.split_groups)
        report = evaluate_target_oracle(fixture.dataset, fixture.predictions_for("empty"))
        size_counts = dict(report.quality.size_target_count)
        if (
            report.evaluated_frame_count != 2
            or report.negative_frame_count != 1
            or len(fixture.dataset.sequences) != 2
            or report.reference_transition_count != 0
            or size_counts
            != {"tiny_lt_0.1pct": 0, "small_0.1_to_1pct": 1, "large_ge_1pct": 0}
        ):
            raise M26MaterializationError("M16 small-bbox oracle gate failed")
        receipt = {
            "schema_version": 1,
            "status": "MATERIALIZED_LOCAL_ONLY",
            "decision": contract["decision"]["pass"],
            "contract_revision": M26_CONTRACT_REVISION,
            "source_revision": contract["source_revision"],
            "license_id": contract["license_id"],
            "archives": archive_rows,
            "archive_header_preflight_passed": True,
            "mapped_namespace_preflight_passed": True,
            "target_frame_count": len(target_keys),
            "annotation_member_count": 1 + 3 * len(scene_ids),
            "unique_rgb_member_read_count": len(set(member_names)),
            "selection": selected.as_dict(),
            "selected_member_names": list(member_names),
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
