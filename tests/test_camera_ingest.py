"""Frames arriving from a browser are checked, counted, and not kept."""

from __future__ import annotations

import io
import unittest

from whole_home_agent.camera_ingest import (
    FRAME_HEIGHT,
    FRAME_WIDTH,
    MAX_FRAME_BYTES,
    CameraIngest,
    CameraIngestError,
    jpeg_dimensions,
)

try:  # The video extra carries Pillow; without it these tests have no frames.
    from PIL import Image
    import numpy as np

    HAS_IMAGING = True
except ImportError:  # pragma: no cover - exercised only on a bare install
    HAS_IMAGING = False


def jpeg_bytes(width: int = FRAME_WIDTH, height: int = FRAME_HEIGHT, quality: int = 90) -> bytes:
    array = np.zeros((height, width, 3), dtype=np.uint8)
    array[:, :, 0] = np.arange(width, dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, "JPEG", quality=quality)
    return buffer.getvalue()


@unittest.skipUnless(HAS_IMAGING, "requires the video extra for image encoding")
class JpegHeaderTests(unittest.TestCase):
    """Dimensions are read from the header so no pixel is ever materialised."""

    def test_dimensions_come_from_the_header(self):
        self.assertEqual(jpeg_dimensions(jpeg_bytes()), (FRAME_WIDTH, FRAME_HEIGHT))
        self.assertEqual(jpeg_dimensions(jpeg_bytes(640, 480)), (640, 480))

    def test_anything_that_is_not_jpeg_is_refused(self):
        for payload in (b"", b"\x89PNG\r\n\x1a\n" + b"x" * 100, b"\xff\xd8", b"\xff\xd8\xff\xe0"):
            with self.subTest(payload=payload[:8]):
                with self.assertRaises(CameraIngestError):
                    jpeg_dimensions(payload)


@unittest.skipUnless(HAS_IMAGING, "requires the video extra for image encoding")
class CameraSessionTests(unittest.TestCase):
    def setUp(self):
        self.ingest = CameraIngest()
        self.session = self.ingest.start(
            device_label="Test Camera",
            negotiated={"width": FRAME_WIDTH, "height": FRAME_HEIGHT, "resizeMode": "none"},
        )
        self.frame = jpeg_bytes()

    def test_frames_in_order_are_accepted_and_counted(self):
        for sequence in range(4):
            result = self.session.accept(
                self.frame, sequence=sequence, captured_ns=sequence * 100_000_000
            )
            self.assertEqual(result["sequence"], sequence)
            self.assertEqual(result["gaps"], 0)
        self.assertEqual(self.session.stats.accepted, 4)

    def test_a_missing_run_is_recorded_rather_than_smoothed_over(self):
        """Losing frames on a network is ordinary. Pretending otherwise is not."""

        self.session.accept(self.frame, sequence=0, captured_ns=0)
        result = self.session.accept(self.frame, sequence=4, captured_ns=400_000_000)
        self.assertEqual(result["gaps"], 1)
        self.assertEqual(self.session.stats.missing_positions, 3)

    def test_a_frame_of_the_wrong_size_is_refused(self):
        with self.assertRaises(CameraIngestError) as raised:
            self.session.accept(jpeg_bytes(640, 480), sequence=0, captured_ns=0)
        self.assertIn("640x480", str(raised.exception))
        self.assertEqual(self.session.stats.accepted, 0)
        self.assertEqual(self.session.stats.rejected, 1)

    def test_sequences_may_not_go_backwards(self):
        self.session.accept(self.frame, sequence=5, captured_ns=0)
        with self.assertRaises(CameraIngestError):
            self.session.accept(self.frame, sequence=4, captured_ns=100_000_000)

    def test_sizes_outside_the_agreed_range_are_refused(self):
        for payload in (b"\xff\xd8" + b"x" * 10, b"\xff\xd8" + b"x" * (MAX_FRAME_BYTES + 1)):
            with self.subTest(size=len(payload)):
                with self.assertRaises(CameraIngestError):
                    self.session.accept(payload, sequence=0, captured_ns=0)

    def test_the_receipt_reports_the_stream_and_claims_no_retention(self):
        for sequence in range(3):
            self.session.accept(self.frame, sequence=sequence, captured_ns=sequence * 100_000_000)
        receipt = self.ingest.end(self.session.session_id)
        self.assertEqual(receipt["accepted"], 3)
        self.assertEqual(receipt["retention"], "none")
        self.assertEqual(len(receipt["stream_sha256"]), 64)
        self.assertEqual(receipt["negotiated"]["resizeMode"], "none")

    def test_the_stream_hash_depends_on_order_not_only_on_content(self):
        """Two sessions with the same frames in a different order differ."""

        self.assertNotEqual(self._hash([0, 1, 2]), self._hash([0, 2, 4]))

    def _hash(self, sequences: list[int]) -> str:
        # A fresh ingest each time: one session at a time is the rule under test
        # elsewhere, and borrowing it here would only test that.
        ingest = CameraIngest()
        session = ingest.start(device_label="Test", negotiated={})
        for sequence in sequences:
            session.accept(self.frame, sequence=sequence, captured_ns=sequence * 100_000_000)
        return ingest.end(session.session_id)["stream_sha256"]

    def test_a_sealed_session_takes_nothing_further(self):
        self.ingest.end(self.session.session_id)
        with self.assertRaises(CameraIngestError):
            self.session.accept(self.frame, sequence=9, captured_ns=0)

    def test_only_one_session_runs_at_a_time(self):
        """Two pages streaming at once would interleave and void every gap count."""

        with self.assertRaises(CameraIngestError):
            self.ingest.start(device_label="Second Camera", negotiated={})

    def test_an_unknown_session_id_is_refused(self):
        with self.assertRaises(CameraIngestError):
            self.ingest.current("not-a-session")

    def test_frames_are_handed_on_and_not_stored(self):
        """The session holds counts and a hash; pixels go to the sink and no further."""

        seen: list[tuple[int, int, int]] = []
        self.session.sink = lambda payload, w, h: seen.append((len(payload), w, h))
        self.session.accept(self.frame, sequence=0, captured_ns=0)
        self.assertEqual(seen, [(len(self.frame), FRAME_WIDTH, FRAME_HEIGHT)])
        stored = [
            value
            for value in vars(self.session).values()
            if isinstance(value, (bytes, bytearray)) and len(value) > 1024
        ]
        self.assertEqual(stored, [])


if __name__ == "__main__":
    unittest.main()
