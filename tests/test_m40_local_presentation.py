"""Frozen contract and implementation witnesses for M40 local presentation."""

from __future__ import annotations

import hashlib
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m40-local-presentation-implementation-v1.toml"


class M40ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_is_frozen_from_exact_m39_result(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_IMPLEMENTATION")
        result = ROOT / self.document["m39_result"]
        self.assertEqual(
            hashlib.sha256(result.read_bytes()).hexdigest(),
            self.document["m39_result_sha256"],
        )
        self.assertEqual(
            self.document["m39_revision"],
            "38e9118f4812072d2a66831c552f951d7e93b282",
        )

    def test_one_port_one_presenter_and_one_composition_root_are_named(self):
        implementation = self.document["implementation"]
        self.assertEqual(implementation["port"], "LocationPresenter")
        self.assertEqual(
            implementation["concrete_presenter"],
            "DeterministicLocationPresenter",
        )
        self.assertEqual(implementation["use_case"], "present_location_context")
        self.assertEqual(
            implementation["composition_root"],
            "src/whole_home_agent/public_demo.py",
        )
        self.assertFalse(implementation["new_runtime_dependency_allowed"])

    def test_input_and_output_are_exact_bounded_contracts(self):
        input_contract = self.document["input_contract"]
        output_contract = self.document["output_contract"]
        self.assertEqual(len(input_contract["exact_top_level_fields"]), 4)
        self.assertEqual(len(input_contract["exact_answer_fields"]), 4)
        self.assertEqual(len(input_contract["exact_relation_fields"]), 4)
        self.assertEqual(len(output_contract["exact_fields"]), 7)
        self.assertTrue(input_contract["extra_or_malformed_fields_fail_to_fallback"])
        self.assertTrue(
            output_contract["empty_non_string_overlong_or_control_output_fails_to_fallback"]
        )
        self.assertFalse(output_contract["exception_text_may_leave_boundary"])
        self.assertFalse(output_contract["model_or_presenter_output_is_authority"])

    def test_wording_cannot_invent_temporal_events(self):
        wording = self.document["wording_contract"]
        self.assertTrue(wording["found_chain_uses_only_active_inside_and_at_zone_relations"])
        self.assertFalse(wording["temporal_put_move_or_sequence_claim_allowed"])
        self.assertTrue(wording["unknown_conflict_or_scope_failure_names_status_and_abstains"])
        self.assertFalse(wording["raw_evidence_claim_run_or_source_identifiers_allowed"])

    def test_structured_answer_survives_and_summary_key_is_compatible(self):
        demo = self.document["public_demo_contract"]
        compatibility = self.document["compatibility"]
        self.assertTrue(demo["retain_answer_field"])
        self.assertTrue(demo["retain_answer_summary_field"])
        self.assertTrue(demo["structured_answer_survives_fallback"])
        self.assertTrue(compatibility["answer_summary_key_retained"])
        self.assertTrue(compatibility["answer_summary_text_changes_to_remove_unrepresented_temporal_claim"])

    def test_every_runtime_and_authority_boundary_remains_closed(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))


if __name__ == "__main__":
    unittest.main()
