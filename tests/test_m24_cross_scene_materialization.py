"""Frozen pre-source contract for the M24 cross-scene D1 materialization."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path
import tempfile

from whole_home_agent.adapters.bop_d1 import (
    BopD1Error,
    BopFrame,
    BopFrameAnnotation,
    select_cross_scene_ycbv_bop19_slice,
)
from whole_home_agent.target_oracle import (
    TargetOracleError,
    evaluate_target_oracle,
    load_target_oracle_fixture,
)
from tools.materialize_ycbv_cross_scene_d1 import (
    M21_CONTRACT_SHA256,
    USE_CLASS,
    write_clean_d1,
)


ROOT = Path(__file__).resolve().parents[1]
M21 = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"
M23 = ROOT / "configs" / "evaluation" / "m23-cross-scene-transfer-oracle-validity-result-v1.toml"
CONTRACT = ROOT / "configs" / "evaluation" / "m24-ycbv-cross-scene-d1-materialization-v1.toml"


class M24ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m21 = tomllib.loads(M21.read_text(encoding="utf-8"))
        cls.m23 = tomllib.loads(M23.read_text(encoding="utf-8"))
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_source_and_authority_are_exactly_inherited(self):
        self.assertEqual(self.document["source_revision"], self.m21["source_revision"])
        self.assertEqual(
            self.document["source_archive_root"], self.m21["source_archive_root"]
        )
        self.assertEqual(
            self.m23["decision"], "SELECT_CROSS_SCENE_TEST_ONLY_ORACLE_CONTRACT"
        )
        self.assertTrue(self.m23["cross_scene_rule_adopted_for_this_oracle_only"])
        self.assertEqual(self.document["maximum_frame_count"], self.m23["maximum_slice_frames"])
        self.assertEqual(hashlib.sha256(M21.read_bytes()).hexdigest(), M21_CONTRACT_SHA256)

    def test_smallest_cross_scene_proving_set_is_exact(self):
        selection = self.document["selection"]
        self.assertEqual(self.document["target_frame_count"], 2)
        self.assertTrue(selection["same_modeled_class_required"])
        self.assertTrue(selection["positive_and_negative_distinct_scene_required"])
        self.assertEqual(selection["positive_visible_area_fraction_range"], [0.001, 0.01])
        self.assertEqual(selection["positive_minimum_visibility_fraction"], 0.10)
        self.assertTrue(selection["negative_requires_complete_modeled_class_absence"])
        self.assertFalse(selection["unknown_unmodeled_or_occluded_is_negative"])
        self.assertTrue(selection["smallest_source_ordered_proving_set"])
        self.assertFalse(selection["adaptive_candidate_or_fallback_allowed"])

    def test_cross_scene_identity_is_not_promoted_to_physical_identity(self):
        mapping = self.document["d1_mapping"]
        self.assertTrue(mapping["one_source_sequence_per_scene"])
        self.assertEqual(mapping["each_sequence_local_frame_index"], 0)
        self.assertTrue(mapping["original_scene_and_image_id_in_manifest"])
        self.assertEqual(mapping["positive_instance_identity"], "SCENE_SCOPED_BOP_OBJECT_ID")
        self.assertFalse(mapping["negative_physical_instance_fabricated"])
        self.assertTrue(mapping["negative_sequence_has_zero_scorable_instances"])
        self.assertEqual(mapping["reference_transition_count"], 0)
        self.assertFalse(mapping["relation_or_movement_truth_emitted"])

    def test_archive_reads_and_output_are_minimal_and_ignored(self):
        reuse = self.document["archive_reuse"]
        output = self.document["output"]
        self.assertFalse(reuse["download_allowed"])
        self.assertTrue(reuse["full_header_and_mapped_namespace_preflight_required"])
        self.assertEqual(reuse["rgb_unique_member_read_count"], 2)
        self.assertFalse(reuse["depth_or_mask_member_read_allowed"])
        self.assertFalse(reuse["filesystem_bulk_extraction_allowed"])
        self.assertEqual(output["clean_materialization_runs"], 2)
        self.assertEqual(output["unique_archive_rgb_reads"], 2)
        self.assertFalse(output["third_party_bytes_in_git_allowed"])
        self.assertTrue(output["staging_removed_on_success_or_failure"])
        for field in ("source_archive_root", "local_root", "local_d1_root", "local_receipt"):
            path = self.document[field]
            self.assertTrue(path.startswith("data/external/"), field)

    def test_oracle_shape_and_next_authority_are_bounded(self):
        gate = self.document["oracle_gate"]
        self.assertEqual(gate["evaluated_frame_count"], 2)
        self.assertEqual(gate["negative_frame_count"], 1)
        self.assertEqual(gate["scorable_target_count"], 1)
        self.assertEqual(gate["source_sequence_count"], 2)
        self.assertEqual(gate["reference_transition_count"], 0)
        decision = self.document["decision"]
        self.assertEqual(
            decision["pass_authorizes_only"],
            "M25_PAIRED_NO_TRAINING_TRANSFER_EXPERIMENT_DESIGN",
        )
        self.assertTrue(decision["pass_is_not_prediction_training_or_transfer_gain"])

    def test_every_model_claim_and_operation_boundary_is_closed(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))

def _annotation(
    object_id: int,
    *,
    visible_pixels: int,
    all_pixels: int,
    bbox: tuple[int, int, int, int],
) -> BopFrameAnnotation:
    return BopFrameAnnotation(
        object_id=object_id,
        bbox_visible_xywh=bbox,
        pixel_count_all=all_pixels,
        pixel_count_visible=visible_pixels,
        visible_fraction=visible_pixels / all_pixels,
    )


def _cross_scene_frames() -> tuple[BopFrame, ...]:
    return (
        BopFrame(
            scene_id=48,
            image_id=1,
            annotations=(
                _annotation(
                    2,
                    visible_pixels=6400,
                    all_pixels=6400,
                    bbox=(100, 100, 80, 80),
                ),
            ),
        ),
        BopFrame(
            scene_id=50,
            image_id=620,
            annotations=(
                _annotation(
                    4,
                    visible_pixels=1569,
                    all_pixels=2000,
                    bbox=(10, 20, 39, 40),
                ),
            ),
        ),
    )


class M24CrossSceneSelectionTests(unittest.TestCase):
    def test_source_order_selects_one_positive_and_distinct_scene_negative(self):
        result = select_cross_scene_ycbv_bop19_slice(_cross_scene_frames())
        self.assertEqual(result.selected_object_id, 4)
        self.assertEqual(result.selected_label, "005_tomato_soup_can")
        self.assertEqual(
            [(item["role"], item["source_scene_id"], item["source_image_id"]) for item in result.source_frames],
            [
                ("POSITIVE", 50, 620),
                ("COMPLETE_CLASS_ABSENT_NEGATIVE", 48, 1),
            ],
        )
        self.assertEqual(len(result.dataset.sequences), 2)
        self.assertTrue(
            all(sequence.frames[0].frame_index == 0 for sequence in result.dataset.sequences)
        )
        self.assertEqual(len(result.dataset.sequences[0].frames[0].instances), 1)
        self.assertEqual(len(result.dataset.sequences[1].frames[0].instances), 0)

    def test_same_scene_absence_cannot_satisfy_cross_scene_contract(self):
        frames = tuple(
            BopFrame(scene_id=48, image_id=frame.image_id, annotations=frame.annotations)
            for frame in _cross_scene_frames()
        )
        with self.assertRaises(BopD1Error) as caught:
            select_cross_scene_ycbv_bop19_slice(frames)
        self.assertEqual(caught.exception.code, "NO_CROSS_SCENE_SLICE")

    def test_two_clean_outputs_are_byte_identical_and_explicitly_m16_loadable(self):
        selected = select_cross_scene_ycbv_bop19_slice(_cross_scene_frames())
        png = b"\x89PNG\r\n\x1a\n" + b"synthetic-not-source"
        archives = [
            {
                "name": "synthetic.zip",
                "bytes": 1,
                "sha256": "0" * 64,
                "source_revision": "synthetic",
                "member_count": 2,
                "uncompressed_bytes": 2,
            }
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            first_records = write_clean_d1(
                first,
                selected=selected,
                rgb_payloads=(png, png),
                source_revision="synthetic",
                archive_rows=archives,
            )
            second_records = write_clean_d1(
                second,
                selected=selected,
                rgb_payloads=(png, png),
                source_revision="synthetic",
                archive_rows=archives,
            )
            self.assertEqual(first_records, second_records)
            with self.assertRaises(TargetOracleError) as default_denial:
                load_target_oracle_fixture(first / "oracle.json")
            self.assertEqual(default_denial.exception.code, "INVALID_FIXTURE_USE_CLASS")
            fixture = load_target_oracle_fixture(
                first / "oracle.json",
                allowed_use_classes=frozenset({USE_CLASS}),
            )
            report = evaluate_target_oracle(fixture.dataset, fixture.predictions_for("empty"))
            self.assertEqual(report.evaluated_frame_count, 2)
            self.assertEqual(report.negative_frame_count, 1)
            self.assertEqual(
                sum(count for _, count in report.quality.size_target_count), 1
            )

    def test_materializer_has_no_network_or_download_path(self):
        source = (ROOT / "tools" / "materialize_ycbv_cross_scene_d1.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("urllib", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("def _download", source)


if __name__ == "__main__":
    unittest.main()
