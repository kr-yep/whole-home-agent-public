"""Frozen pre-source contract for the M24 cross-scene D1 materialization."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
