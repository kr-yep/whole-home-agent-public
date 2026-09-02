"""Frozen contract and implementation witnesses for M40 local presentation."""

from __future__ import annotations

import ast
import hashlib
import tomllib
import unittest
from pathlib import Path

from whole_home_agent.presentation import (
    DETERMINISTIC_PRESENTER_ID,
    FALLBACK,
    FALLBACK_TEXT,
    MAX_PRESENTATION_CHARACTERS,
    PRESENTATION_SCHEMA,
    PRESENTED,
    PRESENTER_FAILURE,
    DeterministicLocationPresenter,
    present_location_context,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m40-local-presentation-implementation-v1.toml"
RESULT = ROOT / "configs" / "evaluation" / "m40-local-presentation-implementation-result-v1.toml"


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


def found_context(*, relation_facts: list[dict[str, str]] | None = None):
    return {
        "schema": "whole-home-agent.location-context.v1",
        "purpose": "verbalize_location_answer",
        "answer": {
            "subject_id": "key",
            "status": "FOUND",
            "location_id": "sofa",
            "epistemic_status": "estimated",
        },
        "relation_facts": relation_facts if relation_facts is not None else [
            {
                "subject_id": "key",
                "predicate": "inside",
                "object_id": "bag",
                "epistemic_status": "estimated",
            },
            {
                "subject_id": "bag",
                "predicate": "at_zone",
                "object_id": "sofa",
                "epistemic_status": "estimated",
            },
        ],
    }


def non_found_context(status: str):
    return {
        "schema": "whole-home-agent.location-context.v1",
        "purpose": "verbalize_location_answer",
        "answer": {
            "subject_id": "key",
            "status": status,
            "location_id": None,
            "epistemic_status": "reported",
        },
        "relation_facts": [],
    }


class _CapturePresenter:
    presenter_id = "capture/1"

    def __init__(self, output: object = "bounded output"):
        self.output = output
        self.calls: list[object] = []

    def present(self, context):
        self.calls.append(context)
        return self.output


class _ThrowingPresenter:
    presenter_id = "throwing/1"

    def present(self, context):
        raise RuntimeError("sensitive-provider-payload-must-not-escape")


class M40ImplementationTests(unittest.TestCase):
    def test_found_chain_uses_only_present_relation_facts(self):
        result = present_location_context(
            found_context(),
            DeterministicLocationPresenter(),
        )
        self.assertEqual(result.status, PRESENTED)
        self.assertEqual(result.presenter_id, DETERMINISTIC_PRESENTER_ID)
        self.assertEqual(
            result.text,
            "在這段固定重播中，系統估計鑰匙在包包裡，且包包位於沙發；"
            "所以鑰匙可能在沙發上的包包裡。",
        )
        self.assertNotIn("被放進", result.text)
        self.assertNotIn("之後", result.text)
        self.assertNotIn("停在", result.text)

    def test_found_without_chain_uses_bounded_direct_location(self):
        result = present_location_context(
            found_context(relation_facts=[]),
            DeterministicLocationPresenter(),
        )
        self.assertEqual(result.status, PRESENTED)
        self.assertEqual(result.text, "在這段固定重播中，系統估計鑰匙位於沙發。")
        reported = found_context()
        reported["answer"]["epistemic_status"] = "reported"
        for fact in reported["relation_facts"]:
            fact["epistemic_status"] = "reported"
        reported_result = present_location_context(
            reported,
            DeterministicLocationPresenter(),
        )
        self.assertIn("系統記錄鑰匙在包包裡", reported_result.text)

    def test_every_non_found_status_abstains_and_names_the_status(self):
        for status in (
            "CONFLICT",
            "FRONTIER_MISMATCH",
            "OUT_OF_SCOPE",
            "SCOPE_REQUIRED",
            "UNKNOWN",
        ):
            with self.subTest(status=status):
                result = present_location_context(
                    non_found_context(status),
                    DeterministicLocationPresenter(),
                )
                self.assertEqual(result.status, PRESENTED)
                self.assertIn(status, result.text)
                self.assertIn("不補猜位置", result.text)
                self.assertNotIn("沙發", result.text)

    def test_malformed_extra_and_hostile_identifier_contexts_fall_back_before_call(self):
        cases = []
        extra = found_context()
        extra["history"] = ["must-not-leave"]
        cases.append(extra)
        hostile = found_context()
        hostile["answer"]["subject_id"] = "<script>"
        cases.append(hostile)
        contradictory = non_found_context("UNKNOWN")
        contradictory["answer"]["location_id"] = "sofa"
        cases.append(contradictory)
        for context in cases:
            presenter = _CapturePresenter()
            with self.subTest(context=context):
                result = present_location_context(context, presenter)
                self.assertEqual(result.status, FALLBACK)
                self.assertEqual(result.failure_code, PRESENTER_FAILURE)
                self.assertEqual(result.text, FALLBACK_TEXT)
                self.assertEqual(presenter.calls, [])

    def test_throwing_empty_overlong_and_control_outputs_fall_back(self):
        presenters = (
            _ThrowingPresenter(),
            _CapturePresenter(""),
            _CapturePresenter("x" * (MAX_PRESENTATION_CHARACTERS + 1)),
            _CapturePresenter("line one\nline two"),
            _CapturePresenter(7),
        )
        for presenter in presenters:
            with self.subTest(presenter=type(presenter).__name__):
                result = present_location_context(found_context(), presenter)
                self.assertEqual(result.status, FALLBACK)
                self.assertTrue(result.fallback_used)
                self.assertEqual(result.failure_code, PRESENTER_FAILURE)

    def test_exception_content_never_leaves_the_sanitized_result(self):
        result = present_location_context(found_context(), _ThrowingPresenter())
        serialized = str(result.as_dict())
        self.assertNotIn("sensitive-provider-payload", serialized)
        self.assertEqual(result.presenter_id, "throwing/1")

    def test_port_receives_a_fresh_exact_minimized_mapping(self):
        context = found_context()
        presenter = _CapturePresenter()
        result = present_location_context(context, presenter)
        self.assertEqual(result.status, PRESENTED)
        self.assertEqual(len(presenter.calls), 1)
        received = presenter.calls[0]
        self.assertIsNot(received, context)
        self.assertEqual(set(received), {"schema", "purpose", "answer", "relation_facts"})
        self.assertEqual(
            set(received["answer"]),
            {"subject_id", "status", "location_id", "epistemic_status"},
        )
        self.assertEqual(
            set(received["relation_facts"][0]),
            {"subject_id", "predicate", "object_id", "epistemic_status"},
        )

    def test_result_dictionary_has_only_the_frozen_receipt_fields(self):
        result = present_location_context(found_context(), _CapturePresenter())
        payload = result.as_dict()
        self.assertEqual(payload["schema"], PRESENTATION_SCHEMA)
        self.assertEqual(payload["status"], PRESENTED)
        self.assertFalse(payload["fallback_used"])
        self.assertIsNone(payload["failure_code"])
        self.assertEqual(
            set(payload),
            {
                "schema",
                "status",
                "presenter_id",
                "context_schema",
                "text",
                "fallback_used",
                "failure_code",
            },
        )

    def test_invalid_presenter_identity_is_sanitized_and_not_called(self):
        presenter = _CapturePresenter()
        presenter.presenter_id = "bad identity with spaces"
        result = present_location_context(found_context(), presenter)
        self.assertEqual(result.status, FALLBACK)
        self.assertEqual(result.presenter_id, "unavailable")
        self.assertEqual(presenter.calls, [])

    def test_presentation_module_has_no_io_network_provider_or_dynamic_import(self):
        path = ROOT / "src" / "whole_home_agent" / "presentation.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_roots: set[str] = set()
        called_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
        self.assertEqual(
            imported_roots,
            {"__future__", "re", "collections", "dataclasses", "typing", "llm_context"},
        )
        self.assertTrue(
            called_names.isdisjoint(
                {"open", "exec", "eval", "compile", "__import__"}
            )
        )


class M40ResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.result = tomllib.loads(RESULT.read_text(encoding="utf-8"))

    def test_result_binds_exact_contract_implementation_and_module(self):
        self.assertEqual(
            self.result["contract_revision"],
            "99d785e1b77f3ad36b9d178c8c8f13a4690d0518",
        )
        self.assertEqual(
            self.result["implementation_revision"],
            "9d0fc81e47f0077e5dce6e7a244d866826506d53",
        )
        module = ROOT / "src" / "whole_home_agent" / "presentation.py"
        self.assertEqual(
            hashlib.sha256(module.read_bytes()).hexdigest(),
            self.result["presentation_module_sha256"],
        )

    def test_implemented_surface_is_one_local_presenter_without_dependency(self):
        surface = self.result["implemented_surface"]
        self.assertEqual(surface["port"], self.contract["implementation"]["port"])
        self.assertEqual(
            surface["local_presenter"],
            self.contract["implementation"]["concrete_presenter"],
        )
        self.assertFalse(surface["provider_or_local_model_adapter"])
        self.assertFalse(surface["runtime_dependency_added"])

    def test_recorded_prose_is_relation_only_and_additive(self):
        presentation = self.result["presentation_result"]
        compatibility = self.result["compatibility"]
        self.assertEqual(presentation["status"], PRESENTED)
        self.assertFalse(presentation["temporal_put_move_or_sequence_claim"])
        self.assertNotIn("被放進", presentation["text"])
        self.assertNotIn("之後", presentation["text"])
        self.assertTrue(compatibility["answer_field_retained"])
        self.assertTrue(compatibility["answer_summary_field_retained"])
        self.assertFalse(
            compatibility["claim_query_relation_evidence_and_context_semantics_changed"]
        )

    def test_recorded_fallback_is_sanitized_and_keeps_structured_answer(self):
        fallback = self.result["fallback_result"]
        self.assertEqual(fallback["status"], FALLBACK)
        self.assertEqual(fallback["failure_code"], PRESENTER_FAILURE)
        self.assertFalse(fallback["exception_content_exposed"])
        self.assertTrue(fallback["structured_answer_retained"])
        self.assertFalse(fallback["provider_retry_or_network"])

    def test_result_preserves_every_runtime_authority_and_claim_limit(self):
        self.assertTrue(all(value is False for value in self.result["boundaries"].values()))
        limits = self.result["claim_limits"]
        self.assertFalse(limits["establishes_language_model_quality"])
        self.assertFalse(limits["establishes_local_model_or_cloud_provider_compatibility"])
        self.assertFalse(limits["establishes_real_home_or_teammate_usability"])
        self.assertTrue(limits["authorizes_only_separately_frozen_m41_packaging_gate"])


if __name__ == "__main__":
    unittest.main()
