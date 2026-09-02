"""Contract tests for the offline, minimized language-context preview."""

from __future__ import annotations

import ast
import importlib.util
import json
import unittest
from pathlib import Path

from whole_home_agent.llm_context import CONTEXT_SCHEMA, build_llm_text_context
from whole_home_agent.public_demo import run_public_demo


ROOT = Path(__file__).resolve().parents[1]
HAS_VIDEO = importlib.util.find_spec("av") is not None and importlib.util.find_spec(
    "numpy"
) is not None


class LlmTextContextTests(unittest.TestCase):
    def test_found_answer_is_projected_through_an_exact_allowlist(self):
        answer = {
            "subject_id": "key",
            "status": "FOUND",
            "location_id": "sofa",
            "epistemic_status": "estimated",
            "relation_path": [
                {
                    "subject_id": "key",
                    "predicate": "inside",
                    "object_id": "bag",
                    "epistemic_status": "estimated",
                    "source_claim_id": "must-not-leave",
                    "source_offset": 35,
                },
                {
                    "subject_id": "bag",
                    "predicate": "at_zone",
                    "object_id": "sofa",
                    "epistemic_status": "estimated",
                    "source_claim_id": "must-not-leave-either",
                },
            ],
            "world_scope": "must-not-leave",
            "replay_run_id": "must-not-leave",
            "source_claim_ids": ["must-not-leave"],
            "reason": "must-not-leave",
        }

        self.assertEqual(
            build_llm_text_context(answer),
            {
                "schema": CONTEXT_SCHEMA,
                "purpose": "verbalize_location_answer",
                "answer": {
                    "subject_id": "key",
                    "status": "FOUND",
                    "location_id": "sofa",
                    "epistemic_status": "estimated",
                },
                "relation_facts": [
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
            },
        )

    def test_unknown_answer_keeps_identity_and_abstention_without_history(self):
        context = build_llm_text_context(
            {
                "subject_id": "missing-object",
                "status": "UNKNOWN",
                "location_id": None,
                "epistemic_status": "unknown",
                "relation_path": [],
                "reason": "no active location relation",
            }
        )

        self.assertEqual(
            context["answer"],
            {
                "subject_id": "missing-object",
                "status": "UNKNOWN",
                "location_id": None,
                "epistemic_status": "unknown",
            },
        )
        self.assertEqual(context["relation_facts"], [])
        self.assertNotIn("reason", json.dumps(context))

    def test_invalid_or_overstated_answers_fail_closed(self):
        cases = [
            {},
            {
                "subject_id": "key",
                "status": "FOUND",
                "location_id": None,
                "epistemic_status": "estimated",
                "relation_path": [],
            },
            {
                "subject_id": "key",
                "status": "UNKNOWN",
                "location_id": "sofa",
                "epistemic_status": "unknown",
                "relation_path": [],
            },
            {
                "subject_id": "key",
                "status": "UNKNOWN",
                "location_id": None,
                "epistemic_status": "unknown",
                "relation_path": [{"subject_id": "key"}],
            },
        ]
        for answer in cases:
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                build_llm_text_context(answer)

    def test_projection_module_has_no_io_or_provider_import(self):
        path = ROOT / "src" / "whole_home_agent" / "llm_context.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
        self.assertEqual(imported_roots, {"__future__", "collections"})

    def test_streamlit_demo_exposes_the_local_preview_without_an_input(self):
        source = (
            ROOT / "src" / "whole_home_agent" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertIn('st.subheader("4 · Local text presentation boundary")', source)
        self.assertIn('st.json(result["language_context"])', source)
        self.assertNotIn("build_llm_text_context", source)
        self.assertNotIn("api_key", source.lower())

    @unittest.skipUnless(HAS_VIDEO, "video optional dependencies are not installed")
    def test_public_demo_answer_produces_the_minimized_context(self):
        result = run_public_demo(replay_run_id="m38-context-test", include_frames=False)
        context = build_llm_text_context(result["answer"])
        self.assertEqual(result["language_context"], context)
        self.assertEqual(result["presentation"]["context_schema"], CONTEXT_SCHEMA)
        self.assertEqual(
            context["answer"],
            {
                "subject_id": "key",
                "status": "FOUND",
                "location_id": "sofa",
                "epistemic_status": "estimated",
            },
        )
        self.assertEqual(
            [
                (item["subject_id"], item["predicate"], item["object_id"])
                for item in context["relation_facts"]
            ],
            [("key", "inside", "bag"), ("bag", "at_zone", "sofa")],
        )


if __name__ == "__main__":
    unittest.main()
