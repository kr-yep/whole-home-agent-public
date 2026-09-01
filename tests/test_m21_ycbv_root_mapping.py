"""Frozen pre-extraction contract for the M21 YCB-V archive-root repair."""

from __future__ import annotations

import subprocess
import tomllib
import unittest
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
M20 = ROOT / "configs" / "evaluation" / "m20-ycbv-bop19-acquisition-v1.toml"
CONTRACT = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"


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


if __name__ == "__main__":
    unittest.main()
