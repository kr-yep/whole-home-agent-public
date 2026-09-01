"""VOST consecutive-frame and motion-screen contract tests."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

try:
    import numpy as np
    from PIL import Image

    VIDEO_AVAILABLE = True
except ImportError:  # pragma: no cover - base-only CI intentionally skips.
    VIDEO_AVAILABLE = False

from whole_home_agent.adapters.motion import MotionPeriodicScheduler, MotionScheduleConfig
from whole_home_agent.adapters.vost import (
    load_vost_motion_screen_manifest,
    load_vost_motion_sequence,
)
from whole_home_agent.model import ProducerRef, SourceKind, TimestampBasis, UseClass
from whole_home_agent.motion_evaluation import (
    decide_motion_gate,
    evaluate_motion_screen,
    evaluate_scheduler_selection,
)


FETCH_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "fetch_vost_motion_subset.py"
if FETCH_TOOL_PATH.is_file():
    FETCH_TOOL_SPEC = importlib.util.spec_from_file_location(
        "fetch_vost_motion_subset", FETCH_TOOL_PATH
    )
    assert FETCH_TOOL_SPEC is not None and FETCH_TOOL_SPEC.loader is not None
    FETCH_TOOL = importlib.util.module_from_spec(FETCH_TOOL_SPEC)
    FETCH_TOOL_SPEC.loader.exec_module(FETCH_TOOL)
else:  # The repository-only acquisition tool is intentionally absent from wheels.
    FETCH_TOOL = None


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(rows: list[dict[str, object]]) -> str:
    return _sha(json.dumps(rows, separators=(",", ":"), sort_keys=True).encode())


class _EmptyDetector:
    producer_ref = ProducerRef(
        component="empty-detector",
        version="1",
        artifact_hash="a" * 64,
        config_hash="b" * 64,
    )
    device = "cpu"

    def detect(self, frame):
        return ()

    def peak_vram_bytes(self):
        return 0

    def runtime_metadata(self):
        return {"test_double": True}


@unittest.skipUnless(FETCH_TOOL is not None, "repository-only VOST fetch tool is absent")
class VostFetchParserTests(unittest.TestCase):
    def test_central_directory_parser_and_path_guard(self):
        name = b"VOST/JPEGImages/1_open_bag/frame00000.jpg"
        payload = b"frame-bytes"
        header = struct.pack(
            "<4s6H3L5H2L",
            b"PK\x01\x02",
            45,
            20,
            0,
            0,
            0,
            0,
            zlib.crc32(payload) & 0xFFFFFFFF,
            len(payload),
            len(payload),
            len(name),
            0,
            0,
            0,
            0,
            0,
            123,
        )
        entries = FETCH_TOOL._central_entries(header + name)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], name.decode())
        self.assertEqual(entries[0]["local_header_offset"], 123)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with self.assertRaisesRegex(RuntimeError, "escaped"):
                FETCH_TOOL._safe_destination(root, Path("..") / "escape.bin")


@unittest.skipUnless(VIDEO_AVAILABLE, "VOST tests require the video extra")
class VostMotionTests(unittest.TestCase):
    def _fixture(self, root: Path, *, target_label: str | None = None) -> Path:
        config_dir = root / "configs" / "evaluation"
        local_root = root / "datasets" / "vost-test"
        config_dir.mkdir(parents=True)
        upstream = {
            "license": (
                "VOST/LICENSE",
                "upstream/LICENSE",
                b"Attribution-NonCommercial-ShareAlike 4.0",
            ),
            "readme": (
                "VOST/README.md",
                "upstream/README.md",
                b"VOST uses CC BY-NC-SA 4.0 at 5 fps",
            ),
            "train_split": (
                "VOST/ImageSets/train.txt",
                "upstream/train.txt",
                b"1_open_bag\n",
            ),
            "validation_split": (
                "VOST/ImageSets/val.txt",
                "upstream/val.txt",
                b"2_open_box\n",
            ),
        }
        artifact_blocks = []
        for kind, (member, relative, value) in upstream.items():
            path = local_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
            artifact_blocks.append(
                f'''[[upstream_artifact]]
kind = "{kind}"
member = "{member}"
path = "{relative}"
bytes = {len(value)}
sha256 = "{_sha(value)}"
'''
            )

        rows: list[dict[str, object]] = []
        sequence_data = []
        for sequence, source_partition, split in (
            ("1_open_bag", "train", "development"),
            ("2_open_box", "val", "validation"),
        ):
            sequence_rows = []
            for local_index, source_offset in enumerate((0, 6)):
                rgb = np.zeros((8, 8, 3), dtype=np.uint8)
                rgb[:, local_index * 2 : local_index * 2 + 2] = 255
                frame_path = (
                    local_root
                    / "VOST"
                    / "JPEGImages"
                    / sequence
                    / f"frame{source_offset:05d}.jpg"
                )
                frame_path.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(rgb, mode="RGB").save(frame_path, format="JPEG")
                mask = np.zeros((8, 8), dtype=np.uint8)
                mask[2:4, local_index * 3 : local_index * 3 + 2] = 1
                mask_path = (
                    local_root
                    / "VOST"
                    / "Annotations"
                    / sequence
                    / f"frame{source_offset:05d}.png"
                )
                mask_path.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(mask, mode="P").save(mask_path, format="PNG")
                for source_kind, path in (("JPEGImages", frame_path), ("Annotations", mask_path)):
                    value = path.read_bytes()
                    row = {
                        "member": (
                            f"VOST/{source_kind}/{sequence}/"
                            f"frame{source_offset:05d}{path.suffix}"
                        ),
                        "bytes": len(value),
                        "crc32": f"{zlib.crc32(value) & 0xFFFFFFFF:08x}",
                        "sha256": _sha(value),
                        "split": split,
                        "sequence": sequence,
                    }
                    rows.append(row)
                    sequence_rows.append(row)
            sequence_rows.sort(key=lambda item: item["member"])
            frame_rows = [item for item in sequence_rows if "/JPEGImages/" in item["member"]]
            mask_rows = [item for item in sequence_rows if "/Annotations/" in item["member"]]
            sequence_data.append(
                {
                    "sequence": sequence,
                    "source_partition": source_partition,
                    "split": split,
                    "rows": sequence_rows,
                    "frame_hash": _canonical(frame_rows),
                    "mask_hash": _canonical(mask_rows),
                }
            )
        rows.sort(key=lambda item: item["member"])
        subset_hash = _canonical(rows)
        (local_root / "subset-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "dataset": "VOST",
                    "license": "CC BY-NC-SA 4.0",
                    "source_url": "https://tri-ml-public.s3.amazonaws.com/datasets/VOST.zip",
                    "sequences": {
                        "development": "1_open_bag",
                        "validation": "2_open_box",
                    },
                    "file_count": len(rows),
                    "files": rows,
                    "files_manifest_sha256": subset_hash,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        sequence_blocks = []
        for item in sequence_data:
            sequence_rows = item["rows"]
            sequence_blocks.append(
                f'''[[sequence]]
sequence_id = "{item['sequence']}"
source_partition = "{item['source_partition']}"
split = "{item['split']}"
frame_count = 2
frame_width = 8
frame_height = 8
source_frame_step = 6
{f'label_review_source_offsets = [0, 6]' if target_label is not None else ''}
subset_file_count = 4
subset_bytes = {sum(row['bytes'] for row in sequence_rows)}
sequence_files_manifest_sha256 = "{_canonical(sequence_rows)}"
frame_files_manifest_sha256 = "{item['frame_hash']}"
annotation_files_manifest_sha256 = "{item['mask_hash']}"
'''
            )
        config = f'''schema_version = 1
dataset_id = "vost-test"
dataset_version = "test-version"
origin_url = "https://www.vostdataset.org/data.html"
repository_url = "https://github.com/TRI-ML/VOST"
archive_url = "https://tri-ml-public.s3.amazonaws.com/datasets/VOST.zip"
archive_version_id = "test-version-id"
archive_etag = "test-etag"
archive_bytes = 1000
central_directory_offset = 900
central_directory_bytes = 90
central_directory_sha256 = "{'c' * 64}"
central_directory_entries = 8
license_id = "CC-BY-NC-SA-4.0"
license_url = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
license_source_member = "VOST/LICENSE"
readme_source_member = "VOST/README.md"
intended_use = "D0_PUBLIC_NONCOMMERCIAL_MOTION_SCREENING"
redistribution_allowed = false
local_root = "datasets/vost-test"
sample_fps_numerator = 5
sample_fps_denominator = 1
target_mask_id = 1
void_mask_id = 255
{f'target_label = "{target_label}"' if target_label is not None else ''}
mask_change_iou_threshold = 0.5
coverage_window_frames = 1
development_candidate_motion_thresholds = [0.0, 0.03]
development_selection_minimum_mask_change_coverage = 0.95
subset_file_count = {len(rows)}
subset_bytes = {sum(row['bytes'] for row in rows)}
subset_files_manifest_sha256 = "{subset_hash}"

{''.join(artifact_blocks)}
[scheduler]
motion_threshold = 0.0
min_gap_frames = 1
anchor_interval_frames = 10
sample_stride = 2

[gate]
minimum_validation_mask_change_coverage = 0.95
minimum_validation_avoided_detector_fraction = 0.30
maximum_detector_p95_ms = 100.0
maximum_peak_vram_bytes = 1024

{'''[target_tracking_gate]
minimum_full_frame_recall50 = 0.60
minimum_matched_observation_fraction = 0.60
maximum_id_switches = 1
maximum_fragmentations = 2
minimum_scheduled_target_event_coverage = 0.60
minimum_scheduled_target_event_retention = 0.90
''' if target_label is not None else ''}

{''.join(sequence_blocks)}'''
        config_path = config_dir / "vost-test.toml"
        config_path.write_text(config, encoding="utf-8")
        return config_path

    def test_loader_preserves_source_offsets_and_builds_mask_change_events(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._fixture(root)
            manifest = load_vost_motion_screen_manifest(config, repository_root=root)
            source = load_vost_motion_sequence(manifest, "1_open_bag")
        self.assertEqual(source.descriptor.source_kind, SourceKind.RECORDED_FRAME_SET)
        self.assertEqual(source.descriptor.use_class, UseClass.D0_PUBLIC)
        self.assertEqual(source.descriptor.timestamp_basis, TimestampBasis.SOURCE_FRAME_INDEX)
        self.assertEqual(source.records[1].position.source_offset, 6)
        self.assertEqual(source.records[1].position.pts, 1)
        self.assertEqual(source.records[1].position.time_base_denominator, 5)
        self.assertEqual(source.mask_change_frames, frozenset({1}))

    def test_scheduler_coverage_is_distinct_from_detector_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._fixture(root)
            manifest = load_vost_motion_screen_manifest(config, repository_root=root)
            source = load_vost_motion_sequence(manifest, "2_open_box")
            scheduler_config = MotionScheduleConfig(
                motion_threshold=0.0,
                min_gap_frames=1,
                anchor_interval_frames=10,
                sample_stride=2,
            )
            selection = evaluate_scheduler_selection(
                source, MotionPeriodicScheduler(scheduler_config)
            )
            report = evaluate_motion_screen(
                source,
                _EmptyDetector(),
                scheduler=MotionPeriodicScheduler(scheduler_config),
                warmup_frames=0,
                repository_root=root,
                code_revision="d" * 40,
                dirty_worktree=False,
            )
        self.assertEqual(selection.coverage.same_or_following_recall, 1.0)
        self.assertEqual(report.coverage.same_or_following_recall, 1.0)
        self.assertEqual(report.detections_total, 0)
        self.assertEqual(decide_motion_gate(manifest.gate, report).decision, "REJECT_CANDIDATE")

    def test_explicit_target_label_builds_boxes_without_promoting_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._fixture(root, target_label="bottle")
            manifest = load_vost_motion_screen_manifest(config, repository_root=root)
            source = load_vost_motion_sequence(manifest, "1_open_bag")
            report = evaluate_motion_screen(
                source,
                _EmptyDetector(),
                scheduler=None,
                warmup_frames=0,
                repository_root=root,
                code_revision="d" * 40,
                dirty_worktree=False,
            )
        target = source.ground_truth[0][0]
        self.assertEqual(target.label, "bottle")
        self.assertEqual(target.bbox.as_xyxy(), (0.0, 2.0, 2.0, 4.0))
        self.assertIsNotNone(report.target_detection_coverage)
        self.assertEqual(report.target_detection_coverage.same_or_following_recall, 0.0)

    def test_tampered_frame_fails_before_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._fixture(root)
            manifest = load_vost_motion_screen_manifest(config, repository_root=root)
            target = (
                manifest.local_root
                / "VOST"
                / "JPEGImages"
                / "1_open_bag"
                / "frame00000.jpg"
            )
            target.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "size/hash"):
                load_vost_motion_sequence(manifest, "1_open_bag")


if __name__ == "__main__":
    unittest.main()
