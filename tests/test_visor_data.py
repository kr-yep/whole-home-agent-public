"""VISOR public-data manifest and adapter contract tests."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from whole_home_agent.adapters.visor import (
    load_visor_frame_set,
    load_visor_screen_manifest,
)
from whole_home_agent.model import SourceKind, TimestampBasis, UseClass


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class VisorAdapterTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        config_dir = root / "configs" / "evaluation"
        data_root = root / "datasets" / "visor-test"
        source = data_root / "source"
        frames = data_root / "frames"
        config_dir.mkdir(parents=True)
        source.mkdir(parents=True)
        sequences = (
            ("P01_01", "development"),
            ("P02_01", "validation"),
            ("P03_01", "test"),
        )
        blocks: list[str] = []
        for sequence_id, split in sequences:
            name = f"{sequence_id}_frame_0000000010.jpg"
            annotation = json.dumps(
                {
                    "info": {"Dataset Name": "VISOR"},
                    "video_annotations": [
                        {
                            "image": {"name": name},
                            "annotations": [
                                {
                                    "id": f"{sequence_id}-fridge",
                                    "name": "fridge",
                                    "segments": [
                                        [[-1, 20], [50, 20], [50, 80], [10, 80]]
                                    ],
                                },
                                {
                                    "id": f"{sequence_id}-hand",
                                    "name": "right hand",
                                    "segments": [
                                        [[100, 100], [110, 100], [110, 110]]
                                    ],
                                },
                            ],
                        }
                    ],
                },
                separators=(",", ":"),
            ).encode()
            archive = f"fake-zip-{sequence_id}".encode()
            annotation_path = source / f"{sequence_id}.json"
            archive_path = source / f"{sequence_id}.zip"
            annotation_path.write_bytes(annotation)
            archive_path.write_bytes(archive)
            frame_dir = frames / sequence_id
            frame_dir.mkdir(parents=True)
            (frame_dir / name).write_bytes(b"not-read-by-loader")
            participant = sequence_id.split("_", 1)[0]
            blocks.append(
                f'''[[sequence]]
sequence_id = "{sequence_id}"
split = "{split}"
frame_count = 1
annotation_path = "source/{sequence_id}.json"
annotation_url = "https://data.bris.ac.uk/datasets/example/{sequence_id}.json"
annotation_bytes = {len(annotation)}
annotation_sha256 = "{_hash(annotation)}"
archive_path = "source/{sequence_id}.zip"
archive_url = "https://data.bris.ac.uk/datasets/example/{participant}/{sequence_id}.zip"
archive_bytes = {len(archive)}
archive_sha256 = "{_hash(archive)}"
frames_path = "frames/{sequence_id}"
'''
            )
        config = f'''schema_version = 1
dataset_id = "visor-test"
dataset_version = "test-v1"
origin_url = "https://epic-kitchens.github.io/VISOR/site"
repository_url = "https://data.bris.ac.uk/data/dataset/example"
license_id = "CC-BY-NC-4.0"
license_url = "https://creativecommons.org/licenses/by-nc/4.0/"
intended_use = "D0_PUBLIC_NONCOMMERCIAL_METHOD_SCREENING"
redistribution_allowed = false
local_root = "datasets/visor-test"
frame_width = 1920
frame_height = 1080

[class_mapping]
"fridge" = "refrigerator"

{''.join(blocks)}'''
        config_path = config_dir / "visor-test.toml"
        config_path.write_text(config, encoding="utf-8")
        return config_path

    def test_loader_preserves_frame_index_scope_and_filters_unmapped_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = self._fixture(root)
            manifest = load_visor_screen_manifest(config_path, repository_root=root)
            source = load_visor_frame_set(manifest, "P01_01")
        self.assertEqual(source.split, "development")
        self.assertEqual(source.descriptor.source_kind, SourceKind.RECORDED_FRAME_SET)
        self.assertEqual(source.descriptor.use_class, UseClass.D0_PUBLIC)
        self.assertEqual(
            source.descriptor.timestamp_basis, TimestampBasis.SOURCE_FRAME_INDEX
        )
        self.assertEqual(source.records[0].position.source_offset, 10)
        self.assertEqual(source.records[0].position.frame_index, 0)
        self.assertEqual(len(source.ground_truth[0]), 1)
        self.assertEqual(source.ground_truth[0][0].label, "refrigerator")
        self.assertEqual(source.ground_truth[0][0].bbox.as_xyxy(), (0, 20, 50, 80))
        self.assertEqual(source.source_diagnostics["boundary_clipped_points"], 1)

    def test_tampered_archive_fails_before_annotation_use(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = self._fixture(root)
            manifest = load_visor_screen_manifest(config_path, repository_root=root)
            manifest.sequence("P02_01").archive_path.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "size/hash"):
                load_visor_frame_set(manifest, "P02_01")

    def test_config_outside_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            root = Path(directory)
            config_path = self._fixture(Path(other))
            with self.assertRaisesRegex(ValueError, "inside the repository"):
                load_visor_screen_manifest(config_path, repository_root=root)


if __name__ == "__main__":
    unittest.main()
