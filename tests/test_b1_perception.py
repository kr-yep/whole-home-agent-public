"""Perception/tracking/evaluation contracts for the prerecorded D0 slice."""

from __future__ import annotations

import importlib.util
import hashlib
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace

from whole_home_agent.adapters.annotation_oracle import AnnotationOracleDetector
from whole_home_agent.adapters.motion import MotionPeriodicScheduler, MotionScheduleConfig
from whole_home_agent.adapters.recorded_video import DecodedVideoFrame
from whole_home_agent.adapters.rfdetr import RFDetrConfig, RFDetrDetector
from whole_home_agent.adapters.synthetic_color import (
    SyntheticColorDetector,
    load_synthetic_color_config,
)
from whole_home_agent.adapters.tracking import IoUTracker, IoUTrackerConfig
from whole_home_agent.evaluation import evaluate_perception
from whole_home_agent.model import ProducerRef, SourcePosition, TimestampBasis
from whole_home_agent.perception import BoundingBox, Detection
from whole_home_agent.video_manifest import load_video_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "media" / "generated" / "key_bag_sofa_v2.manifest.json"
COLOR_CONFIG = ROOT / "configs" / "perception" / "synthetic-color-v1.toml"
HAS_VIDEO = importlib.util.find_spec("av") is not None and importlib.util.find_spec(
    "numpy"
) is not None


class BoundingBoxContractTests(unittest.TestCase):
    def test_iou_uses_exclusive_xyxy_coordinates(self):
        left = BoundingBox(0, 0, 10, 10)
        right = BoundingBox(5, 0, 15, 10)
        self.assertAlmostEqual(left.iou(right), 1 / 3)
        self.assertTrue(left.within(width=10, height=10))
        self.assertFalse(right.within(width=10, height=10))

    def test_invalid_box_fails_closed(self):
        with self.assertRaises(ValueError):
            BoundingBox(5, 5, 5, 8)


@unittest.skipUnless(HAS_VIDEO, "video optional dependencies are not installed")
class PerceptionEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_video_manifest(MANIFEST, repository_root=ROOT)

    def test_annotation_oracle_requires_explicit_test_only_opt_in(self):
        with self.assertRaises(ValueError):
            AnnotationOracleDetector(self.manifest)

    def test_oracle_proves_evaluator_and_tracker_plumbing_only(self):
        report = evaluate_perception(
            self.manifest,
            AnnotationOracleDetector(self.manifest, test_only=True),
            tracker=IoUTracker(),
            repository_root=ROOT,
            code_revision="test-revision",
            dirty_worktree=True,
        )
        self.assertEqual(report.producer_ref["component"], "annotation-oracle-test-only")
        self.assertEqual(report.quality.ap50, 1.0)
        self.assertEqual(report.quality.map50_95, 1.0)
        self.assertEqual(report.quality.key_recall50, 1.0)
        self.assertEqual(report.tracking.id_switches, 0)
        self.assertEqual(report.tracking.fragmentations, 0)
        self.assertEqual(report.cost.decoded_frames, self.manifest.frame_count)
        self.assertEqual(report.cost.peak_vram_bytes, 0)
        self.assertEqual(len(report.environment.dependency_lock_hash), 64)
        self.assertEqual(report.environment.code_revision, "test-revision")
        self.assertTrue(report.environment.dirty_worktree)
        self.assertEqual(report.environment.model_runtime["gpu_name"], None)
        self.assertIn("do not establish indoor transfer", report.evidence_limit)

    def test_pixel_detector_is_measured_separately_from_oracle(self):
        width, height, targets = load_synthetic_color_config(
            COLOR_CONFIG, repository_root=ROOT
        )
        report = evaluate_perception(
            self.manifest,
            SyntheticColorDetector(width=width, height=height, targets=targets),
            tracker=IoUTracker(),
        )
        self.assertEqual(report.producer_ref["component"], "synthetic-color-detector")
        self.assertGreaterEqual(report.quality.ap50, 0.95)
        self.assertGreaterEqual(report.quality.map50_95, 0.50)
        self.assertGreaterEqual(report.quality.key_recall50, 0.85)
        self.assertEqual(report.quality.false_positives50, 0)
        self.assertEqual(report.cost.selected_frames, self.manifest.frame_count)
        self.assertEqual(report.cost.device, "cpu")

    def test_scheduling_saves_detector_calls_but_is_scored_on_all_frames(self):
        scheduler = MotionPeriodicScheduler(
            MotionScheduleConfig(
                motion_threshold=0.005,
                min_gap_frames=2,
                anchor_interval_frames=10,
                sample_stride=8,
            )
        )
        report = evaluate_perception(
            self.manifest,
            AnnotationOracleDetector(self.manifest, test_only=True),
            scheduler=scheduler,
            warmup_frames=0,
        )
        self.assertLess(report.cost.selected_frames, report.cost.decoded_frames)
        self.assertLess(report.quality.recall50, 1.0)


class TrackerContractTests(unittest.TestCase):
    def test_tracker_is_label_aware_and_deterministic(self):
        producer = ProducerRef("fake", "1", "a" * 64, "b" * 64)
        tracker = IoUTracker(IoUTrackerConfig(match_iou_threshold=0.1))

        def position(index: int) -> SourcePosition:
            return SourcePosition(
                source_sequence=index,
                source_offset=index,
                timestamp_basis=TimestampBasis.MEDIA_PTS,
                frame_index=index,
                pts=index,
                time_base_numerator=1,
                time_base_denominator=10,
            )

        first_position = position(0)
        first = Detection("key", 0.9, BoundingBox(0, 0, 10, 10), first_position, producer)
        first_track = tracker.update(first_position, (first,))[0]
        second_position = position(1)
        second = Detection(
            "key", 0.9, BoundingBox(2, 0, 12, 10), second_position, producer
        )
        second_track = tracker.update(second_position, (second,))[0]
        self.assertEqual(first_track.track_id, second_track.track_id)
        self.assertEqual(second_track.track_age, 2)


@unittest.skipUnless(HAS_VIDEO, "video optional dependencies are not installed")
class RFDetrAdapterContractTests(unittest.TestCase):
    def test_training_candidate_is_capped_and_cannot_tune_on_test(self):
        config = tomllib.loads(
            (ROOT / "configs" / "perception" / "rfdetr-nano-training-gate-v1.toml")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(config["status"], "CANDIDATE_NOT_RUN")
        self.assertEqual(config["max_epochs"], 20)
        self.assertEqual(config["early_stopping_patience"], 5)
        self.assertEqual(config["selection_split"], "validation")
        self.assertFalse(config["test_tuning_allowed"])

    def test_hash_pinned_fake_sdk_result_is_translated_and_clipped(self):
        import numpy as np

        class FakeModel:
            def predict(self, image, *, threshold):
                self.image_size = image.size
                self.threshold = threshold
                return SimpleNamespace(
                    xyxy=np.asarray([[-4.0, 2.0, 12.0, 20.0], [5.0, 5.0, 5.0, 8.0]]),
                    confidence=np.asarray([0.9, 0.8]),
                    class_id=np.asarray([0, 0]),
                )

        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "local-nano.pth"
            weights.write_bytes(b"test-only-fake-weights")
            config = RFDetrConfig(
                weights_path=weights,
                weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
                class_names=("key",),
                device="cpu",
                optimize_for_inference=False,
            )
            model = FakeModel()
            detector = RFDetrDetector(config, model_object=model)
            position = SourcePosition(
                source_sequence=0,
                source_offset=0,
                timestamp_basis=TimestampBasis.MEDIA_PTS,
                frame_index=0,
                pts=0,
                time_base_numerator=1,
                time_base_denominator=10,
            )
            detections = detector.detect(
                DecodedVideoFrame(
                    position=position,
                    rgb=np.zeros((16, 16, 3), dtype=np.uint8),
                )
            )
        self.assertEqual(model.image_size, (16, 16))
        self.assertEqual(model.threshold, 0.35)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].label, "key")
        self.assertEqual(detections[0].bbox.as_xyxy(), (0.0, 2.0, 12.0, 16.0))
        self.assertEqual(detections[0].producer_ref.component, "rfdetr-nano")

    def test_weight_hash_mismatch_fails_before_model_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / "local-nano.pth"
            weights.write_bytes(b"different")
            with self.assertRaises(ValueError):
                RFDetrConfig(
                    weights_path=weights,
                    weights_sha256="0" * 64,
                    class_names=("key",),
                )


if __name__ == "__main__":
    unittest.main()
