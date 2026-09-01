"""Frozen M22 annotation-only failure-localization contract."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
import zipfile

from whole_home_agent.adapters.bop_d1 import (
    BopFrame,
    BopFrameAnnotation,
    parse_ycbv_bop19_frames,
)
from whole_home_agent.adapters.bop_diagnostic import (
    CONFORMANCE_CONFLICT,
    NO_SAFE_NEGATIVE,
    NO_SMALL_TARGET,
    PAIRING_SCOPE,
    diagnose_ycbv_m21_predicates,
)


ROOT = Path(__file__).resolve().parents[1]
M21 = ROOT / "configs" / "evaluation" / "m21-ycbv-per-archive-root-repair-v1.toml"
CONTRACT = ROOT / "configs" / "evaluation" / "m22-ycbv-annotation-failure-localization-v1.toml"
FIXTURE = ROOT / "tests" / "fixtures" / "bop" / "ycbv_m20_minimal"
TOOL_PATH = ROOT / "tools" / "diagnose_ycbv_annotations.py"
TOOL_SPEC = importlib.util.spec_from_file_location("diagnose_ycbv_annotations", TOOL_PATH)
assert TOOL_SPEC is not None and TOOL_SPEC.loader is not None
TOOL = importlib.util.module_from_spec(TOOL_SPEC)
TOOL_SPEC.loader.exec_module(TOOL)


def _annotation(object_id: int, *, small: bool = False) -> BopFrameAnnotation:
    pixel_count_visible = 1000 if small else 50000
    pixel_count_all = 2000 if small else 100000
    return BopFrameAnnotation(
        object_id=object_id,
        bbox_visible_xywh=(10, 10, 20, 20),
        pixel_count_all=pixel_count_all,
        pixel_count_visible=pixel_count_visible,
        visible_fraction=0.5,
    )


def _frame(scene_id: int, image_id: int, *annotations: BopFrameAnnotation) -> BopFrame:
    return BopFrame(scene_id=scene_id, image_id=image_id, annotations=annotations)


class M22ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m21 = tomllib.loads(M21.read_text(encoding="utf-8"))
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_source_is_the_exact_ignored_m21_source_and_scope(self):
        self.assertEqual(self.document["status"], "FROZEN_BEFORE_REAL_ANNOTATION_REREAD")
        self.assertEqual(self.document["dataset_id"], self.m21["dataset_id"])
        self.assertEqual(self.document["source_revision"], self.m21["source_revision"])
        expected = {
            item["name"]: (item["bytes"], item["sha256"], item["source_root"])
            for item in self.m21["archive"]
        }
        actual = {
            item["name"]: (item["bytes"], item["sha256"], item["source_root"])
            for item in self.document["archive"]
        }
        self.assertEqual(actual, expected)
        self.assertEqual(self.document["expected_target_entry_count"], 4123)
        self.assertEqual(self.document["expected_unique_target_frame_count"], 900)
        self.assertEqual(self.document["expected_scene_ids"], list(range(48, 60)))
        result = subprocess.run(
            ["git", "check-ignore", "-q", self.document["source_archive_root"] + "/probe"],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0)

    def test_positive_predicate_is_byte_for_byte_equivalent_in_meaning_to_m21(self):
        positive = self.document["positive_predicate"]
        selection = self.m21["slice_selection"]
        translator = self.m21["translator"]
        self.assertEqual(positive["modeled_object_ids"], list(range(1, 22)))
        self.assertEqual(positive["minimum_visible_fraction"], translator["visibility_unknown_below_fraction"])
        self.assertEqual(
            [positive["minimum_visible_area_fraction"], positive["maximum_visible_area_fraction"]],
            selection["target_area_fraction_range"],
        )
        self.assertEqual(positive["area_fraction_basis"], selection["target_area_fraction_basis"])
        self.assertTrue(positive["positive_bbox_width_and_height_required"])

    def test_negative_and_completeness_rules_cannot_invent_absence(self):
        negative = self.document["negative_predicate"]
        self.assertTrue(negative["modeled_object_id_absent_from_complete_ground_truth_rows"])
        for key, value in negative.items():
            if key != "name" and key != "modeled_object_id_absent_from_complete_ground_truth_rows":
                self.assertFalse(value, key)
        completeness = self.document["frame_completeness"]
        self.assertTrue(all(value is True for key, value in completeness.items() if key.endswith("_required")))
        self.assertFalse(completeness["invalid_or_incomplete_frame_is_scored"])
        self.assertTrue(completeness["invalid_or_incomplete_source_normal_stop"])

    def test_four_decision_branches_are_exhaustive_and_ordered(self):
        decision = self.document["decision"]
        self.assertEqual(
            decision["priority"],
            [
                "CONFORMANCE_CONFLICT_IF_ANY_M21_PAIR_EXISTS",
                "NO_SMALL_TARGET_TERM_IF_ZERO_POSITIVES",
                "NO_SAFE_NEGATIVE_TERM_IF_ZERO_NEGATIVES",
                "PAIRING_SCOPE_TERM_OTHERWISE",
            ],
        )
        self.assertEqual(len({decision[key] for key in (
            "conformance_conflict",
            "no_small_target",
            "no_safe_negative",
            "pairing_scope",
            "source_invalid",
        )}), 5)

    def test_diagnostic_cannot_read_media_repair_run_models_or_operate(self):
        access = self.document["input_access"]
        self.assertTrue(access["read_members_directly_from_verified_zip"])
        for key, value in access.items():
            if key.endswith("_allowed"):
                self.assertFalse(value, key)
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertFalse(self.document["aggregation"]["raw_annotations_in_result_allowed"])


class M22SyntheticDiagnosticTests(unittest.TestCase):
    def test_conformance_conflict_branch_has_highest_priority(self):
        result = diagnose_ycbv_m21_predicates(
            (
                _frame(1, 1, _annotation(1, small=True)),
                _frame(1, 2, _annotation(2)),
            )
        )
        self.assertEqual(result.decision, CONFORMANCE_CONFLICT)
        self.assertGreater(result.positive_frame_count, 0)
        self.assertGreater(result.negative_frame_count, 0)
        self.assertGreater(result.paired_object_scene_count, 0)

    def test_no_small_target_branch_precedes_zero_negative(self):
        result = diagnose_ycbv_m21_predicates(
            (_frame(1, 1, *(_annotation(object_id) for object_id in range(1, 22))),)
        )
        self.assertEqual(result.decision, NO_SMALL_TARGET)
        self.assertEqual(result.positive_frame_count, 0)
        self.assertEqual(result.negative_frame_count, 0)

    def test_no_safe_negative_branch_requires_a_positive(self):
        annotations = tuple(
            _annotation(object_id, small=object_id == 1) for object_id in range(1, 22)
        )
        result = diagnose_ycbv_m21_predicates((_frame(1, 1, *annotations),))
        self.assertEqual(result.decision, NO_SAFE_NEGATIVE)
        self.assertEqual(result.positive_frame_count, 1)
        self.assertEqual(result.negative_frame_count, 0)
        self.assertEqual(result.paired_object_scene_count, 0)

    def test_pairing_scope_branch_has_terms_only_in_different_scenes(self):
        result = diagnose_ycbv_m21_predicates(
            (
                _frame(1, 1, _annotation(1, small=True)),
                _frame(2, 1, _annotation(2)),
            )
        )
        self.assertEqual(result.decision, PAIRING_SCOPE)
        self.assertGreater(result.positive_frame_count, 0)
        self.assertGreater(result.negative_frame_count, 0)
        self.assertEqual(result.paired_object_scene_count, 0)

    def test_duplicate_frame_identity_fails_closed(self):
        frame = _frame(1, 1, _annotation(1, small=True))
        with self.assertRaisesRegex(ValueError, "identities"):
            diagnose_ycbv_m21_predicates((frame, frame))

    def test_existing_synthetic_selector_fixture_is_detected_as_a_pair(self):
        targets = json.loads((FIXTURE / "test_targets_bop19.json").read_text(encoding="utf-8"))
        scene = FIXTURE / "test" / "000048"
        documents = {
            48: (
                json.loads((scene / "scene_gt.json").read_text(encoding="utf-8")),
                json.loads((scene / "scene_gt_info.json").read_text(encoding="utf-8")),
                json.loads((scene / "scene_camera.json").read_text(encoding="utf-8")),
            )
        }
        frames = parse_ycbv_bop19_frames(targets, documents)
        result = diagnose_ycbv_m21_predicates(frames)
        self.assertEqual(result.decision, CONFORMANCE_CONFLICT)
        self.assertEqual(result.paired_object_scene_count, 1)

    def test_zip_reader_rejects_duplicate_json_and_tool_has_no_extraction_path(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "fixture.zip"
            with zipfile.ZipFile(archive_path, "w") as output:
                output.writestr("test/duplicate.json", b'{"a":1,"a":2}')
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaisesRegex(TOOL.DiagnosticSourceError, "duplicate JSON"):
                    TOOL._read_json_member(archive, "test/duplicate.json")
        source = TOOL_PATH.read_text(encoding="utf-8")
        self.assertNotIn(".extract(", source)
        self.assertNotIn("extractall", source)
        self.assertNotIn("rgb/", source)

    def test_contract_member_order_is_mapped_to_parser_semantics_by_name(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "scene.zip"
            scene = FIXTURE / "test" / "000048"
            with zipfile.ZipFile(archive_path, "w") as output:
                for name in ("scene_camera.json", "scene_gt.json", "scene_gt_info.json"):
                    output.write(scene / name, f"test/000048/{name}")
            access = {
                "scene_member_template": "test/{scene_id:06d}/{name}",
                "scene_members": [
                    "scene_camera.json",
                    "scene_gt.json",
                    "scene_gt_info.json",
                ],
            }
            with zipfile.ZipFile(archive_path) as archive:
                documents = TOOL._read_scene_documents(archive, [48], access)
            targets = json.loads(
                (FIXTURE / "test_targets_bop19.json").read_text(encoding="utf-8")
            )
            frames = parse_ycbv_bop19_frames(targets, documents)
        self.assertEqual(len(frames), 3)
        self.assertEqual(diagnose_ycbv_m21_predicates(frames).decision, CONFORMANCE_CONFLICT)


if __name__ == "__main__":
    unittest.main()
