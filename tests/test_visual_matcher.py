"""Tests for visual feature extraction, enrollment session, and few-shot matching."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from PIL import Image

from whole_home_agent.adapters.visual_matcher import (
    VisualEnrollmentSession,
    VisualFeatureMatcher,
    cosine_similarity,
    extract_feature_vector,
)


class TestVisualMatcher(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self._temp_dir.name) / "test_features.json"
        self.matcher = VisualFeatureMatcher(self.storage_path)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_feature_vector_extraction_and_similarity(self) -> None:
        # Create two similar dark rectangular crops (simulating same phone under slight shift)
        phone1 = Image.new("RGB", (80, 160), (25, 25, 25))
        phone2 = Image.new("RGB", (80, 160), (30, 30, 30))
        # Create a contrasting red square crop (simulating red mug/cup)
        cup = Image.new("RGB", (100, 100), (220, 40, 40))

        feat1 = extract_feature_vector(phone1)
        feat2 = extract_feature_vector(phone2)
        feat_cup = extract_feature_vector(cup)

        self.assertIn(len(feat1), (512, 576))
        self.assertEqual(len(feat1), len(feat2))

        # Similar phones should have very high similarity (>= 0.90)
        sim_phones = cosine_similarity(feat1, feat2)
        self.assertGreater(sim_phones, 0.90)

        # Phone vs Red cup should have significantly lower similarity
        sim_phone_cup = cosine_similarity(feat1, feat_cup)
        self.assertLess(sim_phone_cup, sim_phones)

    def test_enrollment_session_auto_stop(self) -> None:
        session = self.matcher.start_session("phone", "手機", target_samples=5)
        self.assertEqual(session.target_samples, 5)
        self.assertFalse(session.completed)

        crop = Image.new("RGB", (64, 120), (30, 30, 30))

        # Feed 5 samples with simulated interval
        for i in range(5):
            # Manually reset last_sample_time so interval check passes in unit test
            session.last_sample_time = 0.0
            accepted = session.add_sample(crop)
            self.assertTrue(accepted)
            if i < 4:
                self.assertFalse(session.completed)

        # After 5th sample, session auto-completes
        self.assertTrue(session.completed)
        self.assertTrue(session.just_completed)

        # 6th sample should be refused
        self.assertFalse(session.add_sample(crop))

    def test_matcher_feed_crop_and_match(self) -> None:
        session = self.matcher.start_session("phone", "手機", target_samples=3)

        phone_crop = Image.new("RGB", (80, 160), (20, 20, 20))
        other_crop = Image.new("RGB", (100, 100), (200, 100, 50))

        # Feed crops via matcher
        for _ in range(3):
            session.last_sample_time = 0.0
            status = self.matcher.feed_crop(phone_crop)
            self.assertIsNotNone(status)

        # Session should have completed and deactivated
        self.assertIsNone(self.matcher.get_active_session())
        self.assertTrue(self.matcher.is_enrolled("phone"))

        # Match phone crop against enrolled template
        matched_id, score = self.matcher.match(phone_crop, threshold=0.75)
        self.assertEqual(matched_id, "phone")
        self.assertGreaterEqual(score, 0.75)

        # Match dissimilar crop -> should return None
        matched_other, _ = self.matcher.match(other_crop, threshold=0.88)
        self.assertIsNone(matched_other)


if __name__ == "__main__":
    unittest.main()
