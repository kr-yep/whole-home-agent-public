"""Frozen pre-extraction contract for the M21 YCB-V archive-root repair."""

from __future__ import annotations

import importlib.util
import json
import stat
import struct
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path, PurePosixPath
import zipfile

from whole_home_agent.adapters.bop_d1 import (
    load_and_translate_ycbv_bop19,
    select_ycbv_bop19_slice_from_metadata,
)


ROOT = Path(__file__).resolve().parents[1]
M20 = ROOT / "configs" / "evaluation" / "m20-ycbv-bop19-acquisition-v1.toml"
CONTRACT = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"
FIXTURE = ROOT / "tests" / "fixtures" / "bop" / "ycbv_m20_minimal"
TOOL_PATH = ROOT / "tools" / "materialize_ycbv_bop19.py"
TOOL_SPEC = importlib.util.spec_from_file_location("materialize_ycbv_bop19_m21", TOOL_PATH)
assert TOOL_SPEC is not None and TOOL_SPEC.loader is not None
TOOL = importlib.util.module_from_spec(TOOL_SPEC)
TOOL_SPEC.loader.exec_module(TOOL)


def _png_header(width: int = 640, height: int = 480) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sII", 13, b"IHDR", width, height)


def _synthetic_archives(root: Path) -> tuple[Path, Path]:
    base = root / "ycbv_base.zip"
    test = root / "ycbv_test_bop19.zip"
    with zipfile.ZipFile(base, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(
            FIXTURE / "test_targets_bop19.json",
            "ycbv/test_targets_bop19.json",
        )
    with zipfile.ZipFile(test, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        scene = FIXTURE / "test" / "000048"
        for name in ("scene_camera.json", "scene_gt.json", "scene_gt_info.json"):
            archive.write(scene / name, f"test/000048/{name}")
        for image_id in (1, 2, 3):
            archive.writestr(f"test/000048/rgb/{image_id:06d}.png", _png_header())
    return base, test


def _inspect(path: Path, source_root: str, destination_root: str):
    return TOOL.inspect_archive(
        path,
        expected_root=source_root,
        destination_root=destination_root,
        maximum_member_count=100,
        maximum_total_uncompressed_bytes=1024 * 1024,
        maximum_single_member_bytes=128 * 1024,
        maximum_compression_ratio=200.0,
    )


class M21ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m20 = tomllib.loads(M20.read_text(encoding="utf-8"))
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_only_per_archive_source_to_destination_mapping_changes(self):
        self.assertEqual(
            self.document["status"],
            "FROZEN_BEFORE_ARCHIVE_REUSE_EXTRACTION_OR_REAL_ANNOTATION_READ",
        )
        self.assertEqual(
            self.document["supersedes_only"],
            "M20_SINGLE_SOURCE_ROOT_ASSUMPTION",
        )
        self.assertEqual(self.document["allowed_repair_count"], 1)
        self.assertFalse(self.document["further_contract_repair_allowed"])
        mappings = {
            item["name"]: (item["source_root"], item["destination_root"])
            for item in self.document["archive"]
        }
        self.assertEqual(
            mappings,
            {
                "ycbv_base.zip": ("ycbv", "ycbv"),
                "ycbv_test_bop19.zip": ("test", "ycbv/test"),
            },
        )
        for source_root, destination_root in mappings.values():
            self.assertEqual(PurePosixPath(source_root).parts, (source_root,))
            self.assertNotIn("..", PurePosixPath(destination_root).parts)

    def test_source_identity_and_scientific_rules_equal_m20(self):
        for field in (
            "dataset_id",
            "license_id",
            "source_repository",
            "source_revision",
            "expected_compressed_bytes",
        ):
            self.assertEqual(self.document[field], self.m20[field], field)
        for key in (
            "maximum_compressed_bytes",
            "maximum_total_uncompressed_bytes",
            "maximum_single_member_bytes",
            "maximum_member_count",
            "maximum_compression_ratio",
            "first_slice_max_working_hours",
        ):
            self.assertEqual(self.document["cost"][key], self.m20["cost"][key], key)
        for key, value in self.m20["slice_selection"].items():
            self.assertEqual(self.document["slice_selection"][key], value, key)
        expected = {
            item["name"]: (item["url"], item["bytes"], item["sha256"], item["kind"])
            for item in self.m20["archive"]
        }
        actual = {
            item["name"]: (item["url"], item["bytes"], item["sha256"], item["kind"])
            for item in self.document["archive"]
        }
        self.assertEqual(actual, expected)

    def test_reuses_only_gitignored_local_archives_and_cannot_download(self):
        self.assertEqual(self.document["cost"]["download_retry_count"], 0)
        self.assertFalse(self.document["boundaries"]["archive_download_allowed"])
        for field in ("source_archive_root", "local_root", "local_receipt", "local_slice"):
            relative = self.document[field]
            (ROOT / relative).resolve().relative_to(ROOT)
            result = subprocess.run(
                ["git", "check-ignore", "-q", relative + "/probe" if "." not in Path(relative).name else relative],
                cwd=ROOT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, field)

    def test_mapping_and_selective_extraction_are_fail_closed(self):
        safety = self.document["archive_safety"]
        self.assertTrue(safety["full_header_preflight_before_any_extraction"])
        self.assertTrue(safety["mapped_destination_namespace_preflight_before_any_extraction"])
        for key, value in safety.items():
            if key not in {
                "full_header_preflight_before_any_extraction",
                "mapped_destination_namespace_preflight_before_any_extraction",
            }:
                self.assertFalse(value, key)
        extraction = self.document["selective_extraction"]
        self.assertEqual(extraction["base_members"], ["ycbv/test_targets_bop19.json"])
        self.assertEqual(
            extraction["scene_members"],
            ["scene_camera.json", "scene_gt.json", "scene_gt_info.json"],
        )
        self.assertFalse(extraction["extract_all_rgb_allowed"])
        self.assertFalse(extraction["extract_depth_allowed"])
        self.assertFalse(extraction["extract_masks_allowed"])

    def test_every_model_claim_and_operation_boundary_remains_false(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertEqual(self.document["translator"]["relation_or_transition_count"], 0)
        self.assertEqual(self.document["translator"]["translation_runs_required"], 2)
        self.assertTrue(self.document["translator"]["byte_identical_outputs_required"])
        self.assertFalse(self.document["translator"]["unmodeled_objects_are_negative"])
        self.assertFalse(self.document["translator"]["incomplete_frames_are_scored"])
        self.assertTrue(
            all(value is True for key, value in self.document["gate"].items() if key.startswith("stop_on_"))
        )


class M21MappedArchiveTests(unittest.TestCase):
    def test_two_archive_mapping_preflights_then_extracts_only_selected_rgb(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_path, test_path = _synthetic_archives(root)
            inspections = {
                base_path.name: _inspect(base_path, "ycbv", "ycbv"),
                test_path.name: _inspect(test_path, "test", "ycbv/test"),
            }
            destination = root / "materialized"
            self.assertFalse(destination.exists())
            TOOL.validate_destination_namespace(inspections)
            self.assertFalse(destination.exists())

            destination.mkdir()
            TOOL._extract_members(
                base_path,
                inspections[base_path.name],
                {"ycbv/test_targets_bop19.json"},
                destination,
            )
            targets = json.loads(
                (destination / "ycbv" / "test_targets_bop19.json").read_text(encoding="utf-8")
            )
            TOOL._extract_members(
                test_path,
                inspections[test_path.name],
                TOOL._target_metadata_member_set(targets),
                destination,
            )
            metadata = select_ycbv_bop19_slice_from_metadata(destination / "ycbv")
            selected_rgb = TOOL._selected_rgb_member_set(metadata)
            self.assertEqual(len(selected_rgb), 2)
            TOOL._extract_members(
                test_path,
                inspections[test_path.name],
                selected_rgb,
                destination,
            )
            result = load_and_translate_ycbv_bop19(destination / "ycbv")
            self.assertEqual(result.as_dict(), metadata.as_dict())
            self.assertEqual(result.dataset.dataset_id, "bop-ycbv-bop19-local-slice")
            self.assertEqual(
                sorted(path.name for path in (destination / "ycbv" / "test" / "000048" / "rgb").iterdir()),
                ["000001.png", "000002.png"],
            )

    def test_casefolded_cross_archive_collision_fails_before_output_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.zip"
            test = root / "test.zip"
            with zipfile.ZipFile(base, "w") as archive:
                archive.writestr("ycbv/test/Item.json", b"a")
            with zipfile.ZipFile(test, "w") as archive:
                archive.writestr("test/item.JSON", b"b")
            inspections = {
                base.name: _inspect(base, "ycbv", "ycbv"),
                test.name: _inspect(test, "test", "ycbv/test"),
            }
            output = root / "output"
            with self.assertRaisesRegex(TOOL.MaterializationError, "collision"):
                TOOL.validate_destination_namespace(inspections)
            self.assertFalse(output.exists())

    def test_file_directory_prefix_collision_and_destination_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.zip"
            test = root / "test.zip"
            with zipfile.ZipFile(base, "w") as archive:
                archive.writestr("ycbv/test", b"file")
            with zipfile.ZipFile(test, "w") as archive:
                archive.writestr("test/nested.json", b"{}")
            inspections = {
                base.name: _inspect(base, "ycbv", "ycbv"),
                test.name: _inspect(test, "test", "ycbv/test"),
            }
            with self.assertRaisesRegex(TOOL.MaterializationError, "traverses a file"):
                TOOL.validate_destination_namespace(inspections)
        with self.assertRaisesRegex(TOOL.MaterializationError, "destination root"):
            TOOL.map_member_destination(
                "test/item.json",
                source_root="test",
                destination_root="../escape",
            )

    def test_source_path_link_encryption_method_ratio_and_size_guards_remain_active(self):
        for name, pattern in (
            ("/test/item", "absolute"),
            ("C:test/item", "drive"),
            ("test/../item", "traversal"),
            ("other/item", "top-level root"),
        ):
            info = zipfile.ZipInfo(name)
            with self.assertRaisesRegex(TOOL.MaterializationError, pattern):
                TOOL._normalized_member(info, "test")

        symlink = zipfile.ZipInfo("test/link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaisesRegex(TOOL.MaterializationError, "symbolic"):
            TOOL._normalized_member(symlink, "test")
        encrypted = zipfile.ZipInfo("test/encrypted")
        encrypted.flag_bits |= 0x1
        with self.assertRaisesRegex(TOOL.MaterializationError, "encrypted"):
            TOOL._normalized_member(encrypted, "test")
        unsupported = zipfile.ZipInfo("test/unsupported")
        unsupported.compress_type = 99
        with self.assertRaisesRegex(TOOL.MaterializationError, "compression method"):
            TOOL._normalized_member(unsupported, "test")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ratio = root / "ratio.zip"
            with zipfile.ZipFile(ratio, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("test/ratio.bin", b"0" * 1000)
            with self.assertRaisesRegex(TOOL.MaterializationError, "compression-ratio"):
                TOOL.inspect_archive(
                    ratio,
                    expected_root="test",
                    destination_root="ycbv/test",
                    maximum_member_count=10,
                    maximum_total_uncompressed_bytes=2000,
                    maximum_single_member_bytes=2000,
                    maximum_compression_ratio=2.0,
                )
            with self.assertRaisesRegex(TOOL.MaterializationError, "member exceeds"):
                TOOL.inspect_archive(
                    ratio,
                    expected_root="test",
                    destination_root="ycbv/test",
                    maximum_member_count=10,
                    maximum_total_uncompressed_bytes=2000,
                    maximum_single_member_bytes=10,
                    maximum_compression_ratio=200.0,
                )

    def test_materializer_has_no_network_download_path(self):
        source = TOOL_PATH.read_text(encoding="utf-8")
        self.assertNotIn("urllib", source)
        self.assertNotIn("def _download", source)
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.zip"
            with self.assertRaisesRegex(TOOL.MaterializationError, "absent"):
                TOOL._verify_existing_archive(
                    {"bytes": 1, "sha256": "0" * 64},
                    missing,
                    1024,
                )

    def test_target_metadata_parser_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "test_targets_bop19.json"
            target.write_text('[{"scene_id":48,"scene_id":49}]', encoding="utf-8")
            with self.assertRaisesRegex(TOOL.MaterializationError, "duplicate JSON key"):
                TOOL._read_json_strict(target)


if __name__ == "__main__":
    unittest.main()
