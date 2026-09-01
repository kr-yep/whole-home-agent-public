"""Frozen contract and bounded implementation checks for M31."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m31-answer-trace-subject-implementation-v1.toml"


class M31ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_m30_selection_and_six_statuses_are_frozen(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_BOUNDED_IMPLEMENTATION")
        self.assertEqual(self.document["selected_candidate"], "A_CANONICAL_ANSWER_TRACE_SUBJECT")
        self.assertEqual(
            self.document["required_statuses"],
            ["FOUND", "UNKNOWN", "CONFLICT", "SCOPE_REQUIRED", "OUT_OF_SCOPE", "FRONTIER_MISMATCH"],
        )

    def test_prechange_files_and_m30_result_are_hash_pinned(self):
        for item in self.document["prechange_file"]:
            payload = (ROOT / item["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), item["sha256"])
        result = (ROOT / self.document["m30_result"]).read_bytes()
        self.assertEqual(hashlib.sha256(result).hexdigest(), self.document["m30_result_sha256"])

    def test_implementation_is_one_field_one_constructor_two_serializers(self):
        implementation = self.document["implementation"]
        self.assertTrue(implementation["answer_trace_add_required_subject_id"])
        self.assertEqual(implementation["answer_trace_construction_site_count"], 1)
        self.assertTrue(implementation["b0_cli_serializer_add_subject_id"])
        self.assertTrue(implementation["b1_public_demo_serializer_add_subject_id"])
        self.assertFalse(implementation["other_production_file_changes_allowed"])

    def test_no_legacy_empty_subject_and_compatibility_risk_is_visible(self):
        compatibility = self.document["compatibility"]
        self.assertEqual(compatibility["serialized_output_change"], "ADDITIVE_SUBJECT_ID_FIELD")
        self.assertTrue(compatibility["manual_or_positional_answer_trace_constructor_may_require_update"])
        self.assertFalse(compatibility["legacy_default_or_empty_subject_allowed"])

    def test_every_runtime_and_semantic_boundary_is_closed(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertFalse(self.document["decision"]["m29_retry_allowed"])


if __name__ == "__main__":
    unittest.main()
