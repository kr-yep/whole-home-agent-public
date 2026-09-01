"""Frozen pre-generation contract for the M18 vector D1 slice."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import tempfile
import tomllib
import unittest
from pathlib import Path

from whole_home_agent.target_oracle import (
    TransitionKind,
    evaluate_target_oracle,
    load_target_oracle_fixture,
    validate_source_group_splits,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m18-vector-d1-slice-v1.toml"
MEDIA_ROOT = ROOT / "examples" / "media" / "generated" / "d1_vector_v1"
MANIFEST = MEDIA_ROOT / "manifest.json"
ORACLE_FIXTURE = ROOT / "examples" / "fixtures" / "evaluation" / "d1_vector_slice_v1.json"
HAS_PILLOW = importlib.util.find_spec("PIL") is not None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise AssertionError(f"not a canonical PNG: {path}")
    return struct.unpack(">II", data[16:24])


class M18VectorD1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_exact_tiny_shape_and_split_assignment_are_frozen(self):
        shape = self.document["shape"]
        self.assertEqual((shape["width"], shape["height"]), (640, 360))
        self.assertEqual(shape["source_group_count"], 3)
        self.assertEqual(shape["frames_per_group"], 6)
        self.assertEqual(shape["image_annotation_pair_count"], 18)
        split = self.document["split_integrity"]
        self.assertEqual(split["splits"], ["development", "validation", "test"])
        self.assertTrue(split["assign_before_render"])
        self.assertFalse(split["protected_factor_cross_split_allowed"])
        groups = self.document["scene_groups"]
        self.assertEqual(list(groups), split["splits"])
        for field in split["protected_factors"]:
            values = [groups[name][field] for name in split["splits"]]
            self.assertEqual(len(values), len(set(values)))

    def test_six_frame_semantic_plan_is_exact(self):
        plan = self.document["frame_plan"]
        self.assertEqual(
            plan["roles"],
            [
                "visible_source",
                "truncated_near_container",
                "occluded_inside_container",
                "visible_destination",
                "scored_negative",
                "unknown",
            ],
        )
        self.assertEqual(len(plan["evaluation_states"]), 6)
        self.assertEqual(len(plan["visibility_states"]), 6)
        self.assertEqual(len(plan["relation_states"]), 6)
        self.assertEqual(self.document["vector_geometry"]["key_width"], 28)
        self.assertEqual(self.document["vector_geometry"]["key_height"], 12)

    def test_complete_d1_case_coverage_is_frozen(self):
        coverage = self.document["coverage"]
        self.assertEqual(coverage["small_object_area_fraction_range"], [0.001, 0.01])
        self.assertEqual(
            coverage["required_visibility_states"],
            ["VISIBLE", "TRUNCATED", "OCCLUDED", "ABSENT"],
        )
        self.assertEqual(
            coverage["required_transition_kinds"],
            ["CONTAINMENT_CHANGE", "LOCATION_CHANGE"],
        )
        self.assertTrue(coverage["explicit_scored_negative_per_split"])
        self.assertTrue(coverage["explicit_unknown_frame_per_split"])

    def test_manifest_reproducibility_and_golden_identity_are_bounded(self):
        reproducibility = self.document["reproducibility"]
        self.assertEqual(reproducibility["clean_generation_count"], 2)
        self.assertEqual(
            reproducibility["maximum_total_non_manifest_output_bytes"],
            5 * 1024 * 1024,
        )
        self.assertFalse(reproducibility["new_dependency_allowed"])
        self.assertTrue(self.document["existing_golden"]["must_remain_unchanged"])
        for key, value in self.document["existing_golden"].items():
            if key.endswith("sha256"):
                self.assertEqual(len(value), 64)

    def test_gate_cannot_authorize_models_claims_or_operation(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertEqual(
            self.document["gate"]["pass_decision"],
            "PASS_TO_REALISM_TRANSFER_GATE_DESIGN",
        )


class M18VectorD1ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.fixture = load_target_oracle_fixture(ORACLE_FIXTURE)

    def test_manifest_pairs_exactly_eighteen_images_and_annotations(self):
        media = self.manifest["media"]
        annotations = self.manifest["annotations"]
        self.assertEqual(len(media), 18)
        self.assertEqual(len(annotations), 18)
        self.assertEqual(self.manifest["image_annotation_pair_count"], 18)
        media_by_path = {item["path"]: item for item in media}
        for annotation_record in annotations:
            annotation_path = ROOT / annotation_record["path"]
            document = json.loads(annotation_path.read_text(encoding="utf-8"))
            image_record = media_by_path[annotation_record["image_path"]]
            image_path = ROOT / image_record["path"]
            self.assertEqual(_sha256(image_path), image_record["sha256"])
            self.assertEqual(image_path.stat().st_size, image_record["size_bytes"])
            self.assertEqual(_sha256(annotation_path), annotation_record["sha256"])
            self.assertEqual(annotation_path.stat().st_size, annotation_record["size_bytes"])
            self.assertEqual(document["image"]["path"], image_record["path"])
            self.assertEqual(document["image"]["sha256"], image_record["sha256"])
            self.assertEqual(_png_dimensions(image_path), (640, 360))

    def test_every_non_manifest_output_is_hash_pinned_and_below_total_bound(self):
        outputs = self.manifest["outputs"]
        self.assertEqual(len(outputs), 37)
        self.assertEqual(len({item["path"] for item in outputs}), 37)
        actual_total = 0
        for item in outputs:
            path = ROOT / item["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(_sha256(path), item["sha256"])
            self.assertEqual(path.stat().st_size, item["size_bytes"])
            actual_total += path.stat().st_size
        self.assertEqual(actual_total, self.manifest["total_non_manifest_output_bytes"])
        self.assertLessEqual(
            actual_total,
            self.contract["reproducibility"]["maximum_total_non_manifest_output_bytes"],
        )
        self.assertIsNone(self.manifest["manifest_self_hash"])

    def test_m16_oracle_loads_all_groups_states_transitions_and_splits(self):
        dataset = self.fixture.dataset
        self.assertEqual((dataset.width, dataset.height), (640, 360))
        self.assertEqual(len(dataset.sequences), 3)
        self.assertTrue(all(len(sequence.frames) == 6 for sequence in dataset.sequences))
        validate_source_group_splits(self.fixture.split_groups)
        self.assertEqual(
            {transition.kind for transition in dataset.transitions},
            {TransitionKind.CONTAINMENT_CHANGE, TransitionKind.LOCATION_CHANGE},
        )
        self.assertEqual(len(dataset.transitions), 6)
        empty_report = evaluate_target_oracle(dataset, self.fixture.predictions_for("empty"))
        self.assertEqual(empty_report.evaluated_frame_count, 15)
        self.assertEqual(empty_report.unknown_frame_count, 3)
        self.assertEqual(empty_report.reference_transition_count, 6)

    def test_each_split_has_exact_case_roles_and_small_visible_target(self):
        required_roles = set(self.contract["frame_plan"]["roles"])
        lower, upper = self.contract["coverage"]["small_object_area_fraction_range"]
        frame_area = self.contract["shape"]["width"] * self.contract["shape"]["height"]
        grouped: dict[str, list[dict[str, object]]] = {
            split: [] for split in self.contract["split_integrity"]["splits"]
        }
        for item in self.manifest["annotations"]:
            document = json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
            grouped[document["split"]].append(document)
        for split, documents in grouped.items():
            self.assertEqual({item["frame_role"] for item in documents}, required_roles)
            self.assertTrue(
                any(
                    item["frame_role"] == "scored_negative"
                    and item["evaluation_state"] == "SCORED"
                    and item["instances"][0]["visibility"] == "ABSENT"
                    for item in documents
                )
            )
            self.assertTrue(
                any(
                    item["frame_role"] == "unknown"
                    and item["evaluation_state"] == "UNKNOWN"
                    for item in documents
                )
            )
            visible_areas = []
            for item in documents:
                instance = item["instances"][0]
                if instance["visibility"] != "VISIBLE":
                    continue
                left, top, right, bottom = instance["bbox"]
                visible_areas.append(((right - left) * (bottom - top)) / frame_area)
            self.assertTrue(any(lower <= area <= upper for area in visible_areas), split)
            relations = {
                relation["predicate"]
                for item in documents
                for relation in item["relations"]
            }
            self.assertEqual(relations, {"inside", "at_zone"})

    def test_every_manifest_protected_factor_is_confined_to_one_split(self):
        groups = self.manifest["source_groups"]
        required = self.contract["manifest"]["required_group_fields"]
        self.assertEqual(len(groups), 3)
        for group in groups:
            self.assertTrue(set(required).issubset(group))
        for factor in self.contract["split_integrity"]["protected_factors"]:
            split_by_value: dict[object, str] = {}
            for group in groups:
                previous = split_by_value.setdefault(group[factor], group["split"])
                self.assertEqual(previous, group["split"])

    def test_existing_b1_golden_hashes_are_unchanged(self):
        golden = self.contract["existing_golden"]
        self.assertEqual(_sha256(ROOT / "tools" / "generate_synthetic_replay.py"), golden["generator_sha256"])
        self.assertEqual(_sha256(ROOT / "examples" / "media" / "generated" / "key_bag_sofa_v2.mp4"), golden["media_sha256"])
        self.assertEqual(_sha256(ROOT / "examples" / "media" / "generated" / "key_bag_sofa_v2.annotations.json"), golden["annotations_sha256"])
        self.assertEqual(_sha256(ROOT / "examples" / "media" / "generated" / "key_bag_sofa_v2.manifest.json"), golden["manifest_sha256"])

    @unittest.skipUnless(HAS_PILLOW, "Pillow is an optional video dependency")
    def test_two_clean_generations_match_the_committed_bytes(self):
        from tools.generate_d1_vector_slice import generate

        with tempfile.TemporaryDirectory() as first_root, tempfile.TemporaryDirectory() as second_root:
            first = Path(first_root)
            second = Path(second_root)
            generate(media_directory=first / "media", oracle_fixture_path=first / "oracle.json")
            generate(media_directory=second / "media", oracle_fixture_path=second / "oracle.json")
            committed_files = {
                item["path"]: (ROOT / item["path"]).read_bytes()
                for item in self.manifest["outputs"]
            }
            for item in self.manifest["outputs"]:
                if item["kind"] == "m16_oracle_fixture":
                    first_path = first / "oracle.json"
                    second_path = second / "oracle.json"
                else:
                    name = Path(item["path"]).name
                    first_path = first / "media" / name
                    second_path = second / "media" / name
                self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
                self.assertEqual(first_path.read_bytes(), committed_files[item["path"]])
            self.assertEqual(
                (first / "media" / "manifest.json").read_bytes(),
                (second / "media" / "manifest.json").read_bytes(),
            )
            self.assertEqual(
                (first / "media" / "manifest.json").read_bytes(),
                MANIFEST.read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
