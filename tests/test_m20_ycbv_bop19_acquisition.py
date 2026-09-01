"""Frozen pre-download contract for the M20 YCB-V BOP'19 slice."""

from __future__ import annotations

import subprocess
import tomllib
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m20-ycbv-bop19-acquisition-v1.toml"


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


if __name__ == "__main__":
    unittest.main()
