"""Frozen pre-source contract for M26 exact replacement materialization."""

from __future__ import annotations

import hashlib
import subprocess
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M21 = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"
M25 = ROOT / "configs" / "evaluation" / "m25-ycbv-small-bbox-alignment-result-v1.toml"
CONTRACT = ROOT / "configs" / "evaluation" / "m26-ycbv-dual-area-replacement-d1-v1.toml"


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


if __name__ == "__main__":
    unittest.main()
