"""Tests for YOLO detector sink and camera detection integration."""

from __future__ import annotations

import unittest
from whole_home_agent.camera_ingest import (
    CameraIngest,
    CameraSession,
    FRAME_WIDTH,
    FRAME_HEIGHT,
)
from whole_home_agent.adapters.yolo_detector import COCO_TRANSLATIONS


class TestYoloDetectionIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_detections = [
            {"box": [100.0, 150.0, 50.0, 120.0], "label": "手機 (cell phone)", "raw_label": "cell phone", "confidence": 0.88},
            {"box": [300.0, 200.0, 80.0, 80.0], "label": "水杯 (cup)", "raw_label": "cup", "confidence": 0.76},
        ]

        def mock_sink(payload: bytes, width: int, height: int):
            return self.mock_detections

        self.mock_sink = mock_sink
        self.ingest = CameraIngest(default_sink=self.mock_sink)

    def _sample_jpeg(self) -> bytes:
        # Minimal valid 1280x720 JPEG payload
        header = bytes.fromhex(
            "ffd8ffe000104a46494600010101004800480000ffdb00430008060607060508070707090908"
            "0a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c303134"
            "34341f27393d38323c2e333432ffc000110802d0050003012200021101031101ffc4001f0000"
            "010501010101010100000000000000000102030405060708090a0bffda000c03010002110311"
            "003f00fefe00ffd9"
        )
        return header + b"\x00" * 3000

    def test_camera_session_accepts_detections_from_sink(self) -> None:
        session = self.ingest.start(device_label="test-cam", negotiated={})
        payload = self._sample_jpeg()
        result = session.accept(payload, sequence=0, captured_ns=1_000_000_000)

        self.assertEqual(len(result["detections"]), 2)
        self.assertEqual(result["detections"][0]["raw_label"], "cell phone")
        self.assertEqual(session.latest_detections, self.mock_detections)
        self.assertEqual(session.latest_detection_ns, 1_000_000_000)

        # Verify ingest.get_latest_detections()
        latest = self.ingest.get_latest_detections()
        self.assertEqual(len(latest), 2)
        self.assertEqual(latest[0]["raw_label"], "cell phone")

        # Verify status() includes latest_detections
        status = self.ingest.status()
        self.assertTrue(status["running"])
        self.assertEqual(status["latest_detections"], self.mock_detections)

    def test_coco_translations_mapping(self) -> None:
        self.assertEqual(COCO_TRANSLATIONS.get("cell phone"), "手機")
        self.assertEqual(COCO_TRANSLATIONS.get("cup"), "水杯")
        self.assertEqual(COCO_TRANSLATIONS.get("backpack"), "包包")
        self.assertEqual(COCO_TRANSLATIONS.get("couch"), "沙發")
        self.assertEqual(COCO_TRANSLATIONS.get("laptop"), "筆記型電腦")


if __name__ == "__main__":
    unittest.main()
