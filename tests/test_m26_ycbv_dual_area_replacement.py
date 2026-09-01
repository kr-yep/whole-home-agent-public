"""Frozen pre-source contract for M26 exact replacement materialization."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from whole_home_agent.adapters.bop_d1 import (
    BopD1Error,
    BopFrame,
    BopFrameAnnotation,
    select_exact_cross_scene_ycbv_bop19_slice,
)
from whole_home_agent.target_oracle import evaluate_target_oracle, load_target_oracle_fixture
from tools.materialize_ycbv_cross_scene_d1 import write_clean_d1
from tools.materialize_ycbv_dual_area_replacement import USE_CLASS


ROOT = Path(__file__).resolve().parents[1]
M21 = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"
M25 = ROOT / "configs" / "evaluation" / "m25-ycbv-small-bbox-alignment-result-v1.toml"
CONTRACT = ROOT / "configs" / "evaluation" / "m26-ycbv-dual-area-replacement-d1-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m26-ycbv-dual-area-replacement-d1-result-v1.toml"


class M26ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m21 = tomllib.loads(M21.read_text(encoding="utf-8"))
        cls.m25 = tomllib.loads(M25.read_text(encoding="utf-8"))
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_is_frozen_and_pins_both_authority_inputs(self):
        self.assertEqual(
            self.document["status"],
            "FROZEN_BEFORE_SOURCE_ARCHIVE_ANNOTATION_OR_MEDIA_REREAD",
        )
        identity = self.document["contract_identity"]
        self.assertEqual(hashlib.sha256(M21.read_bytes()).hexdigest(), identity["m21_contract_sha256"])
        self.assertEqual(hashlib.sha256(M25.read_bytes()).hexdigest(), identity["m25_result_sha256"])
        self.assertEqual(self.document["source_revision"], self.m21["source_revision"])
        self.assertEqual(self.m25["decision"], "SELECT_DUAL_AREA_CROSS_SCENE_PAIR")

    def test_exact_selection_is_copied_without_search_authority(self):
        selected = self.document["selection"]
        prior = self.m25["selection"]
        self.assertEqual(selected["selected_object_id"], prior["selected_object_id"])
        self.assertEqual(selected["selected_label"], prior["selected_label"])
        self.assertEqual(selected["positive"]["source_scene_id"], prior["positive"]["source_scene_id"])
        self.assertEqual(selected["positive"]["source_image_id"], prior["positive"]["source_image_id"])
        self.assertEqual(selected["positive"]["bbox_visible_xywh"], prior["positive"]["bbox_visible_xywh"])
        self.assertEqual(selected["negative"]["source_scene_id"], prior["negative"]["source_scene_id"])
        self.assertEqual(selected["negative"]["source_image_id"], prior["negative"]["source_image_id"])
        self.assertFalse(selected["adaptive_candidate_or_fallback_allowed"])
        self.assertFalse(selected["threshold_change_allowed"])

    def test_archive_and_output_access_is_exact_and_ignored(self):
        reuse = self.document["archive_reuse"]
        self.assertFalse(reuse["download_allowed"])
        self.assertEqual(reuse["annotation_member_read_count"], 37)
        self.assertEqual(reuse["rgb_unique_member_read_count"], 2)
        self.assertFalse(reuse["depth_or_mask_member_read_allowed"])
        self.assertFalse(reuse["filesystem_bulk_extraction_allowed"])
        output = self.document["output"]
        self.assertEqual(output["real_source_passes"], 1)
        self.assertEqual(output["clean_materialization_runs"], 2)
        self.assertFalse(output["third_party_bytes_in_git_allowed"])
        for field in ("source_archive_root", "local_root", "local_d1_root", "local_receipt"):
            path = self.document[field]
            self.assertTrue(path.startswith("data/external/"), field)
            ignored = subprocess.run(["git", "check-ignore", "-q", path + "/probe"], cwd=ROOT)
            self.assertEqual(ignored.returncode, 0)

    def test_oracle_gate_requires_the_actual_m16_small_bucket(self):
        gate = self.document["oracle_gate"]
        self.assertEqual(gate["evaluated_frame_count"], 2)
        self.assertEqual(gate["negative_frame_count"], 1)
        self.assertEqual(gate["scorable_target_count"], 1)
        self.assertEqual(gate["small_bbox_target_count"], 1)
        self.assertEqual(gate["tiny_bbox_target_count"], 0)
        self.assertEqual(gate["large_bbox_target_count"], 0)
        self.assertEqual(gate["reference_transition_count"], 0)

    def test_next_authority_and_all_non_media_boundaries_are_closed(self):
        decision = self.document["decision"]
        self.assertEqual(decision["pass_authorizes_only"], "M27_NO_MODEL_DEMO_AND_EVALUATION_CONTRACT_DESIGN")
        self.assertTrue(decision["pass_is_not_prediction_training_or_transfer_gain"])
        self.assertTrue(all(self.document["claim_limits"].values()))
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


def _annotation(
    object_id: int,
    *,
    bbox: tuple[int, int, int, int] = (473, 161, 22, 129),
    visible_pixels: int = 1739,
    all_pixels: int = 9908,
    visible_fraction: float = 0.17551473556721842,
) -> BopFrameAnnotation:
    return BopFrameAnnotation(
        object_id=object_id,
        bbox_visible_xywh=bbox,
        pixel_count_all=all_pixels,
        pixel_count_visible=visible_pixels,
        visible_fraction=visible_fraction,
    )


def _frames() -> tuple[BopFrame, ...]:
    return (
        BopFrame(scene_id=48, image_id=1, annotations=(_annotation(2, bbox=(10, 10, 80, 80)),)),
        BopFrame(scene_id=50, image_id=722, annotations=(_annotation(4),)),
    )


def _select(frames: tuple[BopFrame, ...] | None = None):
    return select_exact_cross_scene_ycbv_bop19_slice(
        _frames() if frames is None else frames,
        object_id=4,
        positive_identity=(50, 722),
        negative_identity=(48, 1),
        expected_bbox_visible_xywh=(473, 161, 22, 129),
        expected_visible_pixel_area_fraction=1739 / 307200,
        expected_bbox_area_fraction=(22 * 129) / 307200,
        expected_visible_fraction=0.17551473556721842,
    )


class M26SyntheticMaterializationTests(unittest.TestCase):
    def test_exact_pair_translates_without_search_or_physical_transition(self):
        selected = _select()
        self.assertEqual(selected.selected_object_id, 4)
        self.assertEqual(
            [(item["source_scene_id"], item["source_image_id"]) for item in selected.source_frames],
            [(50, 722), (48, 1)],
        )
        self.assertEqual(len(selected.dataset.sequences), 2)
        self.assertEqual(len(selected.dataset.transitions), 0)

    def test_any_exact_positive_or_negative_drift_fails_closed(self):
        with self.assertRaises(BopD1Error) as bbox_error:
            _select(
                (
                    _frames()[0],
                    BopFrame(scene_id=50, image_id=722, annotations=(_annotation(4, bbox=(473, 161, 23, 129)),)),
                )
            )
        self.assertEqual(bbox_error.exception.code, "EXACT_POSITIVE_DRIFT")
        with self.assertRaises(BopD1Error) as negative_error:
            _select(
                (
                    BopFrame(scene_id=48, image_id=1, annotations=(_annotation(4),)),
                    _frames()[1],
                )
            )
        self.assertEqual(negative_error.exception.code, "EXACT_NEGATIVE_DRIFT")

    def test_two_outputs_are_identical_and_have_one_m16_small_target(self):
        selected = _select()
        png = b"\x89PNG\r\n\x1a\n" + b"synthetic-not-source"
        archives = [{"name": "synthetic.zip", "bytes": 1, "sha256": "0" * 64}]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first_records = write_clean_d1(
                first,
                selected=selected,
                rgb_payloads=(png, png),
                source_revision="synthetic",
                archive_rows=archives,
                use_class=USE_CLASS,
            )
            second_records = write_clean_d1(
                second,
                selected=selected,
                rgb_payloads=(png, png),
                source_revision="synthetic",
                archive_rows=archives,
                use_class=USE_CLASS,
            )
            self.assertEqual(first_records, second_records)
            fixture = load_target_oracle_fixture(
                first / "oracle.json", allowed_use_classes=frozenset({USE_CLASS})
            )
            report = evaluate_target_oracle(fixture.dataset, fixture.predictions_for("empty"))
        self.assertEqual(
            dict(report.quality.size_target_count),
            {"tiny_lt_0.1pct": 0, "small_0.1_to_1pct": 1, "large_ge_1pct": 0},
        )

    def test_tool_has_no_network_download_or_adaptive_selector(self):
        source = (ROOT / "tools" / "materialize_ycbv_dual_area_replacement.py").read_text(encoding="utf-8")
        for forbidden in ("requests", "urllib", "def _download", "select_cross_scene_ycbv_bop19_slice("):
            self.assertNotIn(forbidden, source)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "materialize_ycbv_dual_area_replacement.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class M26ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_passes_exact_frozen_branch_and_records_pre_source_fix(self):
        self.assertEqual(self.result["decision"], self.contract["decision"]["pass"])
        self.assertFalse(self.result["pre_source_fix"]["real_source_read_before_fix"])
        self.assertFalse(self.result["pre_source_fix"]["frame_selection_or_threshold_changed"])
        self.assertEqual(
            self.result["pre_source_fix"]["resolution"],
            "REUSE_EXISTING_TEST_ONLY_MINIMAL_DETECTOR_TRANSFER_ORACLE",
        )

    def test_exact_pair_and_two_rgb_hashes_are_recorded(self):
        selection = self.result["selection"]
        self.assertEqual(selection["selected_object_id"], 4)
        self.assertEqual([selection["positive"]["source_scene_id"], selection["positive"]["source_image_id"]], [50, 722])
        self.assertEqual([selection["negative"]["source_scene_id"], selection["negative"]["source_image_id"]], [48, 1])
        self.assertEqual(len(self.result["output_file"]), 4)
        self.assertEqual(self.result["unique_rgb_member_read_count"], 2)

    def test_m16_metric_alignment_is_now_exact_but_not_a_gain(self):
        metric = self.result["metric_alignment"]
        self.assertEqual(metric["m16_tiny_bbox_target_count"], 0)
        self.assertEqual(metric["m16_small_bbox_target_count"], 1)
        self.assertEqual(metric["m16_large_bbox_target_count"], 0)
        self.assertTrue(metric["small_bbox_detector_oracle_established"])
        self.assertFalse(metric["detector_gain_established"])
        self.assertFalse(metric["transfer_gain_experiment_authorized"])

    def test_output_is_deterministic_ignored_and_has_no_staging(self):
        output = self.result["output"]
        self.assertTrue(self.result["byte_identical_outputs"])
        self.assertEqual(output["file_count"], 4)
        self.assertEqual(output["total_bytes"], 1066049)
        self.assertTrue(output["all_files_git_ignored"])
        self.assertFalse(output["raw_annotation_rows_persisted"])
        self.assertFalse(output["staging_remaining"])

    def test_next_gate_and_all_boundaries_remain_closed(self):
        next_gate = self.result["next_gate"]
        self.assertEqual(next_gate["proposal"], "M27_NO_MODEL_DEMO_AND_EVALUATION_CONTRACT_DESIGN")
        self.assertFalse(next_gate["source_or_media_read_allowed"])
        self.assertFalse(next_gate["model_prediction_training_or_test_tuning_allowed"])
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
