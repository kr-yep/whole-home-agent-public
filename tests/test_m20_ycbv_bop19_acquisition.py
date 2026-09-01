"""Frozen pre-download contract for the M20 YCB-V BOP'19 slice."""

from __future__ import annotations

import importlib.util
import json
import shutil
import stat
import struct
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from urllib.parse import urlparse
import zipfile

from whole_home_agent.adapters.bop_d1 import (
    BopD1Error,
    YCB_VIDEO_CLASS_NAMES,
    load_and_translate_ycbv_bop19,
)
from whole_home_agent.target_oracle import evaluate_target_oracle


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m20-ycbv-bop19-acquisition-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m20-ycbv-bop19-acquisition-result-v1.toml"
FIXTURE = ROOT / "tests" / "fixtures" / "bop" / "ycbv_m20_minimal"
TOOL_PATH = ROOT / "tools" / "materialize_ycbv_bop19.py"
TOOL_SPEC = importlib.util.spec_from_file_location("materialize_ycbv_bop19", TOOL_PATH)
assert TOOL_SPEC is not None and TOOL_SPEC.loader is not None
TOOL = importlib.util.module_from_spec(TOOL_SPEC)
TOOL_SPEC.loader.exec_module(TOOL)


def _png_header(width: int = 640, height: int = 480) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I4sII", 13, b"IHDR", width, height)


def _materialize_synthetic_tree(root: Path) -> Path:
    dataset = root / "ycbv"
    shutil.copytree(FIXTURE, dataset)
    rgb = dataset / "test" / "000048" / "rgb"
    rgb.mkdir()
    for image_id in (1, 2, 3):
        (rgb / f"{image_id:06d}.png").write_bytes(_png_header())
    return dataset


class M20YcbvAcquisitionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_immutable_two_archive_source_is_frozen(self):
        revision = self.document["source_revision"]
        self.assertEqual(revision, "5c2c4aa229800355648cd268040aa814f8dc94f0")
        archives = self.document["archive"]
        self.assertEqual([item["name"] for item in archives], [
            "ycbv_base.zip",
            "ycbv_test_bop19.zip",
        ])
        self.assertEqual(sum(item["bytes"] for item in archives), 660214506)
        for archive in archives:
            parsed = urlparse(archive["url"])
            self.assertEqual((parsed.scheme, parsed.hostname), ("https", "huggingface.co"))
            self.assertIn(f"/resolve/{revision}/", parsed.path)
            self.assertEqual(len(archive["sha256"]), 64)

    def test_data_destination_is_repository_local_and_git_ignored(self):
        local_root = self.document["local_root"]
        destination = (ROOT / local_root).resolve()
        destination.relative_to(ROOT)
        result = subprocess.run(
            ["git", "check-ignore", "-q", local_root + "/probe.bin"],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.document["boundaries"]["source_bytes_in_git_allowed"])
        self.assertFalse(self.document["boundaries"]["real_annotations_in_git_allowed"])

    def test_zip_safety_and_cost_limits_fail_closed(self):
        safety = self.document["archive_safety"]
        self.assertEqual(safety["expected_top_level_root"], "ycbv")
        for key, value in safety.items():
            if key != "expected_top_level_root":
                self.assertFalse(value, key)
        cost = self.document["cost"]
        self.assertLessEqual(self.document["expected_compressed_bytes"], cost["maximum_compressed_bytes"])
        self.assertEqual(cost["maximum_total_uncompressed_bytes"], 5 * 1024**3)
        self.assertEqual(cost["first_slice_max_working_hours"], 8)
        self.assertEqual(cost["download_retry_count"], 1)

    def test_selection_is_annotation_only_source_order_and_non_relational(self):
        selection = self.document["slice_selection"]
        self.assertTrue(selection["uses_annotations_only"])
        self.assertFalse(selection["model_results_allowed"])
        self.assertEqual(selection["target_area_fraction_range"], [0.001, 0.01])
        self.assertEqual(selection["maximum_selected_frame_count"], 18)
        self.assertTrue(selection["requires_complete_selected_class_absent_frame"])
        self.assertFalse(selection["fallback_candidate_or_rule_allowed"])
        translator = self.document["translator"]
        self.assertEqual(translator["relation_or_transition_count"], 0)
        self.assertFalse(translator["unmodeled_objects_are_negative"])
        self.assertFalse(translator["incomplete_frames_are_scored"])

    def test_every_model_claim_operation_and_scope_expansion_boundary_is_false(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        gate = self.document["gate"]
        self.assertTrue(all(value is True for key, value in gate.items() if key.startswith("stop_on_")))


class M20BopD1SyntheticContractTests(unittest.TestCase):
    def test_author_class_map_and_frozen_source_order_selection_are_exact(self):
        self.assertEqual(len(YCB_VIDEO_CLASS_NAMES), 21)
        self.assertEqual(YCB_VIDEO_CLASS_NAMES[0], "002_master_chef_can")
        self.assertEqual(YCB_VIDEO_CLASS_NAMES[-1], "061_foam_brick")
        with tempfile.TemporaryDirectory() as directory:
            dataset_root = _materialize_synthetic_tree(Path(directory))
            result = load_and_translate_ycbv_bop19(dataset_root)
        self.assertEqual(result.selected_object_id, 1)
        self.assertEqual(result.selected_scene_id, 48)
        self.assertEqual(
            [item["source_image_id"] for item in result.source_frames],
            [1, 2],
        )
        self.assertEqual(
            [item["visibility"] for item in result.source_frames],
            ["VISIBLE", "ABSENT"],
        )
        self.assertNotIn(3, [item["source_image_id"] for item in result.source_frames])

    def test_exact_d1_slice_scores_positive_and_negative_without_relations(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset_root = _materialize_synthetic_tree(Path(directory))
            result = load_and_translate_ycbv_bop19(dataset_root)
            repeated = load_and_translate_ycbv_bop19(dataset_root)
        self.assertEqual(result.as_dict(), repeated.as_dict())
        self.assertEqual(result.dataset.transitions, ())
        report = evaluate_target_oracle(result.dataset, ())
        self.assertEqual(report.evaluated_frame_count, 2)
        self.assertEqual(report.negative_frame_count, 1)
        self.assertEqual(report.unknown_frame_count, 0)
        self.assertEqual(report.reference_transition_count, 0)

    def test_dimension_and_complete_absence_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset_root = _materialize_synthetic_tree(Path(directory))
            frame = dataset_root / "test" / "000048" / "rgb" / "000001.png"
            frame.write_bytes(_png_header(width=320))
            with self.assertRaisesRegex(BopD1Error, "FRAME_DIMENSION_MISMATCH"):
                load_and_translate_ycbv_bop19(dataset_root)
        with tempfile.TemporaryDirectory() as directory:
            dataset_root = _materialize_synthetic_tree(Path(directory))
            gt_path = dataset_root / "test" / "000048" / "scene_gt.json"
            info_path = dataset_root / "test" / "000048" / "scene_gt_info.json"
            gt = json.loads(gt_path.read_text(encoding="utf-8"))
            info = json.loads(info_path.read_text(encoding="utf-8"))
            gt["2"] = gt["3"]
            info["2"] = info["3"]
            gt_path.write_text(json.dumps(gt), encoding="utf-8")
            info_path.write_text(json.dumps(info), encoding="utf-8")
            with self.assertRaisesRegex(BopD1Error, "NO_FROZEN_SLICE"):
                load_and_translate_ycbv_bop19(dataset_root)


class M20ZipSafetyTests(unittest.TestCase):
    def _inspect(self, path: Path):
        return TOOL.inspect_archive(
            path,
            expected_root="ycbv",
            maximum_member_count=10,
            maximum_total_uncompressed_bytes=1024,
            maximum_single_member_bytes=512,
            maximum_compression_ratio=20.0,
        )

    def test_safe_archive_headers_pass_without_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "safe.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("ycbv/test_targets_bop19.json", b"[]")
            inspection = self._inspect(archive_path)
            self.assertEqual(inspection["member_count"], 1)
            self.assertEqual(inspection["members"][0]["name"], "ycbv/test_targets_bop19.json")

    def test_traversal_duplicate_symlink_and_ratio_archives_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traversal = root / "traversal.zip"
            with zipfile.ZipFile(traversal, "w") as archive:
                archive.writestr("ycbv/../escape.txt", b"x")
            with self.assertRaisesRegex(TOOL.MaterializationError, "traversal"):
                self._inspect(traversal)

            duplicate = root / "duplicate.zip"
            with zipfile.ZipFile(duplicate, "w") as archive:
                archive.writestr("ycbv/A.txt", b"a")
                archive.writestr("ycbv/a.txt", b"b")
            with self.assertRaisesRegex(TOOL.MaterializationError, "duplicate"):
                self._inspect(duplicate)

            symlink = root / "symlink.zip"
            link = zipfile.ZipInfo("ycbv/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(symlink, "w") as archive:
                archive.writestr(link, "target")
            with self.assertRaisesRegex(TOOL.MaterializationError, "symbolic"):
                self._inspect(symlink)

            ratio = root / "ratio.zip"
            with zipfile.ZipFile(ratio, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("ycbv/bomb.txt", b"0" * 500)
            with self.assertRaisesRegex(TOOL.MaterializationError, "compression-ratio"):
                self._inspect(ratio)

    def test_official_test_archive_style_root_fails_the_frozen_single_root_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "test-root.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("test/000048/scene_gt.json", b"{}")
            with self.assertRaisesRegex(TOOL.MaterializationError, "top-level root"):
                self._inspect(archive_path)


class M20StoppedResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_stop_matches_the_frozen_fail_closed_branch(self):
        self.assertEqual(cls_value := self.result["decision"], self.contract["gate"]["normal_stop_decision"])
        self.assertEqual(cls_value, "STOP_YCBV_REAL_TRANSFER_ORACLE_MATERIALIZATION")
        self.assertTrue(self.result["normal_stop"])
        self.assertEqual(self.result["failure_stage"], "PRE_EXTRACTION_ARCHIVE_HEADER_PREFLIGHT")
        self.assertFalse(self.result["extraction_started"])
        self.assertFalse(self.result["real_annotation_read"])

    def test_archive_identity_passes_but_single_root_contract_does_not(self):
        self.assertTrue(self.result["source_identity_passed"])
        archives = {item["name"]: item for item in self.result["archive"]}
        self.assertEqual(archives["ycbv_base.zip"]["observed_top_level_root"], "ycbv")
        self.assertEqual(archives["ycbv_test_bop19.zip"]["observed_top_level_root"], "test")
        self.assertEqual(archives["ycbv_test_bop19.zip"]["header_preflight"], "FAIL")
        for expected in self.contract["archive"]:
            actual = archives[expected["name"]]
            self.assertEqual((actual["bytes"], actual["sha256"]), (expected["bytes"], expected["sha256"]))

    def test_next_gate_changes_only_per_archive_root_mapping(self):
        next_gate = self.result["next_gate"]
        self.assertEqual(next_gate["proposal"], "M21_PER_ARCHIVE_ROOT_MAPPING_INFRASTRUCTURE_REPAIR")
        self.assertIn("SOURCE_REVISION", next_gate["unchanged"])
        self.assertIn("SMALL_TARGET_RANGE", next_gate["unchanged"])
        self.assertIn("ALL_MODEL_TRAINING_CLAIM_AND_OPERATION_PROHIBITIONS", next_gate["unchanged"])

    def test_stop_preserves_every_model_claim_and_operation_boundary(self):
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))
        verification = self.result["verification"]
        self.assertEqual(verification["source_bytes_committed"], 0)
        self.assertEqual(verification["extracted_file_count"], 0)
        self.assertEqual(verification["real_annotation_files_read"], 0)


if __name__ == "__main__":
    unittest.main()
