"""Recorded D0 manifest, PTS decode, and scheduling witnesses."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

from whole_home_agent import SourceError
from whole_home_agent.adapters.motion import (
    MotionPeriodicScheduler,
    MotionScheduleConfig,
    SelectionReason,
)
from whole_home_agent.adapters.recorded_video import iter_decoded_frames
from whole_home_agent.video_manifest import load_video_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
MEDIA_ROOT = REPO_ROOT / "examples" / "media" / "generated"
MANIFEST_PATH = MEDIA_ROOT / "key_bag_sofa_v1.manifest.json"


@unittest.skipUnless(
    importlib.util.find_spec("av") is not None
    and importlib.util.find_spec("numpy") is not None,
    "video optional dependency is not installed",
)
class RecordedVideoContractTests(unittest.TestCase):
    def test_manifest_pins_media_annotations_generator_and_scope(self):
        manifest = load_video_manifest(MANIFEST_PATH, repository_root=REPO_ROOT)

        self.assertEqual(manifest.descriptor.source_id, "b1-key-bag-sofa")
        self.assertEqual(manifest.descriptor.world_scope, "source:b1-key-bag-sofa@1")
        self.assertEqual(manifest.license_id, "CC0-1.0")
        self.assertEqual(manifest.frame_count, 80)
        self.assertEqual((manifest.width, manifest.height), (640, 360))
        self.assertEqual((manifest.fps_numerator, manifest.fps_denominator), (10, 1))
        self.assertEqual(manifest.split, "demo")
        self.assertEqual(
            hashlib.sha256(manifest.media_path.read_bytes()).hexdigest(),
            manifest.descriptor.content_hash,
        )
        self.assertEqual(
            hashlib.sha256(manifest.annotation_path.read_bytes()).hexdigest(),
            manifest.annotation_hash,
        )
        self.assertEqual({item["entity_id"] for item in manifest.entities}, {"key", "bag", "sofa"})

    def test_manifest_outside_allowlist_fails_closed(self):
        with self.assertRaises(SourceError):
            load_video_manifest(
                REPO_ROOT / "examples" / "fixtures" / "fixture_manifest_v1.json",
                repository_root=REPO_ROOT,
            )

    def test_decode_uses_monotonic_integer_pts_and_manifest_dimensions(self):
        manifest = load_video_manifest(MANIFEST_PATH, repository_root=REPO_ROOT)
        frames = list(iter_decoded_frames(manifest))

        self.assertEqual(len(frames), manifest.frame_count)
        self.assertEqual(frames[0].position.frame_index, 0)
        self.assertEqual(frames[-1].position.frame_index, 79)
        pts = [frame.position.pts for frame in frames]
        self.assertEqual(pts, sorted(pts))
        self.assertEqual(len(set(pts)), len(pts))
        for frame in frames:
            self.assertEqual(frame.rgb.shape, (360, 640, 3))
            self.assertGreater(frame.position.time_base_denominator or 0, 0)
            self.assertIsNotNone(frame.position.pts)

    def test_motion_is_only_a_compute_hint_and_periodic_anchors_remain(self):
        manifest = load_video_manifest(MANIFEST_PATH, repository_root=REPO_ROOT)
        scheduler = MotionPeriodicScheduler(
            MotionScheduleConfig(
                motion_threshold=0.005,
                min_gap_frames=2,
                anchor_interval_frames=10,
                sample_stride=8,
            )
        )
        decisions = [scheduler.evaluate(frame) for frame in iter_decoded_frames(manifest)]
        selected = [decision for decision in decisions if decision.selected]
        reasons = {decision.reason for decision in selected}

        self.assertEqual(decisions[0].reason, SelectionReason.FIRST)
        self.assertIn(SelectionReason.MOTION, reasons)
        self.assertIn(SelectionReason.PERIODIC_ANCHOR, reasons)
        self.assertLess(len(selected), len(decisions))
        self.assertLessEqual(79 - max(item.frame_index for item in selected), 9)
        self.assertTrue(all(not hasattr(item, "claim_id") for item in decisions))

    def test_annotations_use_declared_pixel_coordinate_space(self):
        manifest = load_video_manifest(MANIFEST_PATH, repository_root=REPO_ROOT)
        annotations = json.loads(manifest.annotation_path.read_text(encoding="utf-8"))

        self.assertEqual(annotations["coordinate_space"], "pixel_xyxy_exclusive")
        self.assertEqual(len(annotations["frames"]), manifest.frame_count)
        first = annotations["frames"][0]["objects"]
        self.assertIsNotNone(first["key"])
        after_put = annotations["frames"][35]["objects"]
        self.assertIsNone(after_put["key"])
        self.assertEqual(manifest.events[0]["frame_index"], 35)
        self.assertEqual(manifest.events[1]["frame_index"], 65)


if __name__ == "__main__":
    unittest.main()
