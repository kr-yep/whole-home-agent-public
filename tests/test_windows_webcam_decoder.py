"""Contract and integration tests for CaptureStreamDecoder and ROI Ingress (WHA-WIN-CAPTURE-ROI-001)."""

from __future__ import annotations

import io
import unittest
from typing import Optional

from whole_home_agent.adapters.windows_webcam.decoder import (
    CaptureStreamDecoder,
    STATE_ABORTED,
    STATE_COMPLETE,
    STATE_FAILED,
)
from whole_home_agent.adapters.windows_webcam.roi_contract import (
    RoiAcceptResultV1,
    RoiDeliveryReceiptV1,
    RoiFrameLeaseV1,
    RoiIngressEndV1,
    RoiIngressFrameV1,
    RoiIngressGapV1,
    RoiIngressPort,
    RoiIngressSessionV1,
)
from whole_home_agent.adapters.windows_webcam.synthetic_producer import (
    SyntheticStreamBuilder,
    pack_wire_message,
)
from whole_home_agent.adapters.windows_webcam.wire_protocol import (
    FRAME_BODY_BYTES,
    KIND_FRAME,
    KIND_START,
)


class FakeRoiConsumer(RoiIngressPort):
    """Test double for ROI Ingress stage."""

    def __init__(
        self,
        *,
        reject_sequence: Optional[int] = None,
        simulate_timeout: bool = False,
        simulate_leak: bool = False,
    ) -> None:
        self.reject_sequence = reject_sequence
        self.simulate_timeout = simulate_timeout
        self.simulate_leak = simulate_leak

        self.session_opened: Optional[RoiIngressSessionV1] = None
        self.accepted_frames: list[int] = []
        self.recorded_gaps: list[tuple[int, int]] = []
        self.session_closed: Optional[RoiIngressEndV1] = None
        self.session_aborted: bool = False

    def open_session(self, session: RoiIngressSessionV1) -> None:
        self.session_opened = session

    def accept(self, frame: RoiIngressFrameV1, lease: RoiFrameLeaseV1) -> RoiAcceptResultV1:
        # Read from memoryview safely
        view = lease.pixel_memory_view
        _ = len(view)

        if not self.simulate_leak:
            lease.release()

        if self.reject_sequence == frame.source_sequence:
            return RoiAcceptResultV1(
                schema="whole-home-agent.roi-accept-result.v1",
                capture_session_id=frame.capture_session_id,
                source_sequence=frame.source_sequence,
                status="REJECTED",
                reason_code="ROI_REJECT_CAPACITY",
                accepted_monotonic_ns=None,
                roi_ingress_version="windows_webcam_roi/1",
                roi_config_hash="00" * 32,
            )

        self.accepted_frames.append(frame.source_sequence)
        return RoiAcceptResultV1(
            schema="whole-home-agent.roi-accept-result.v1",
            capture_session_id=frame.capture_session_id,
            source_sequence=frame.source_sequence,
            status="ACCEPTED",
            reason_code=None,
            accepted_monotonic_ns=frame.captured_monotonic_ns + 5_000_000,
            roi_ingress_version="windows_webcam_roi/1",
            roi_config_hash="00" * 32,
        )

    def accept_gap(self, gap: RoiIngressGapV1) -> None:
        self.recorded_gaps.append((gap.first_missing_sequence, gap.last_missing_sequence))

    def close_session(self, end: RoiIngressEndV1) -> None:
        self.session_closed = end

    def abort_session(self, end: RoiIngressEndV1 | None) -> None:
        self.session_aborted = True


class TestRoiFrameLease(unittest.TestCase):
    def test_lease_read_and_release(self) -> None:
        buf = bytearray(FRAME_BODY_BYTES)
        buf[0] = 0xAA
        lease = RoiFrameLeaseV1(buf)
        self.assertFalse(lease.is_released)
        view = lease.pixel_memory_view
        self.assertEqual(view[0], 0xAA)
        self.assertTrue(view.readonly)

        lease.release()
        self.assertTrue(lease.is_released)

        # Attempting to access view after release raises BufferError
        with self.assertRaises(BufferError):
            _ = lease.pixel_memory_view

    def test_double_release_raises(self) -> None:
        buf = bytearray(FRAME_BODY_BYTES)
        lease = RoiFrameLeaseV1(buf)
        lease.release()
        with self.assertRaises(ValueError) as ctx:
            lease.release()
        self.assertIn("already been released", str(ctx.exception))


class TestCaptureStreamDecoderHappyPaths(unittest.TestCase):
    def setUp(self) -> None:
        self.roi = FakeRoiConsumer()
        self.decoder = CaptureStreamDecoder(
            self.roi,
            roi_config_hash="00" * 32,
        )

    def test_empty_sealed_session(self) -> None:
        builder = SyntheticStreamBuilder()
        builder.emit_start()
        stream_bytes = builder.emit_sealed_end()

        receipt = self.decoder.process_stream(io.BytesIO(stream_bytes))
        self.assertEqual(receipt.status, "COMPLETE")
        self.assertEqual(receipt.acquisition_positions, 0)
        self.assertEqual(receipt.frame_messages_received, 0)
        self.assertIsNone(receipt.failure_code)
        self.assertTrue(receipt.resource_release_ok)

    def test_single_frame_session(self) -> None:
        builder = SyntheticStreamBuilder()
        builder.emit_start().emit_frame()
        stream_bytes = builder.emit_sealed_end()

        receipt = self.decoder.process_stream(io.BytesIO(stream_bytes))
        self.assertEqual(receipt.status, "COMPLETE")
        self.assertEqual(receipt.acquisition_positions, 1)
        self.assertEqual(receipt.frame_messages_received, 1)
        self.assertEqual(receipt.roi_frames_accepted, 1)
        self.assertIsNotNone(receipt.delivery_latency_p50_ns)
        self.assertEqual(self.roi.accepted_frames, [0])

    def test_full_300_frames_session(self) -> None:
        builder = SyntheticStreamBuilder()
        builder.emit_start()
        for i in range(300):
            builder.emit_frame()
        stream_bytes = builder.emit_sealed_end()

        receipt = self.decoder.process_stream(io.BytesIO(stream_bytes))
        self.assertEqual(receipt.status, "COMPLETE")
        self.assertEqual(receipt.acquisition_positions, 300)
        self.assertEqual(receipt.frame_messages_received, 300)
        self.assertEqual(receipt.roi_frames_accepted, 300)
        self.assertEqual(receipt.gap_positions, 0)
        self.assertEqual(receipt.last_source_sequence, 299)
        self.assertIsNone(receipt.failure_code)

    def test_session_with_tolerated_gap(self) -> None:
        builder = SyntheticStreamBuilder()
        builder.emit_start()
        builder.emit_frame()  # seq 0
        builder.emit_gap(1, 2, reason="queue_overflow")  # missing 1, 2
        builder.emit_frame(sequence=3)  # seq 3
        stream_bytes = builder.emit_sealed_end()

        receipt = self.decoder.process_stream(io.BytesIO(stream_bytes))
        self.assertEqual(receipt.status, "COMPLETE")
        self.assertEqual(receipt.acquisition_positions, 4)
        self.assertEqual(receipt.frame_messages_received, 2)
        self.assertEqual(receipt.gap_positions, 2)
        self.assertEqual(receipt.queue_overflow_positions, 2)
        self.assertEqual(self.roi.recorded_gaps, [(1, 2)])

    def test_aborted_session(self) -> None:
        builder = SyntheticStreamBuilder()
        builder.emit_start()
        builder.emit_frame()
        stream_bytes = builder.emit_aborted_end()

        receipt = self.decoder.process_stream(io.BytesIO(stream_bytes))
        self.assertEqual(receipt.status, "ABORTED")
        self.assertEqual(receipt.source_end_status, "ABORTED")
        self.assertTrue(self.roi.session_aborted)


class TestCaptureStreamDecoderFailurePaths(unittest.TestCase):
    def setUp(self) -> None:
        self.roi = FakeRoiConsumer()
        self.decoder = CaptureStreamDecoder(
            self.roi,
            roi_config_hash="00" * 32,
        )

    def test_digest_mismatch_fails_session(self) -> None:
        builder = SyntheticStreamBuilder()
        builder.emit_start()
        builder.emit_frame()
        raw = builder.emit_sealed_end()

        # Tamper with the frame byte inside body (offset 1000 is inside RGB24 frame)
        tampered = bytearray(raw)
        tampered[1000] ^= 0xFF

        receipt = self.decoder.process_stream(io.BytesIO(tampered))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_DIGEST_MISMATCH")
        self.assertTrue(self.roi.session_aborted)

    def test_unexplained_sequence_skip_fails(self) -> None:
        builder = SyntheticStreamBuilder()
        builder.emit_start()
        builder.emit_frame(sequence=0)
        # Skip seq 1 directly without a gap message
        builder.emit_frame(sequence=2)
        raw = builder.emit_sealed_end()

        receipt = self.decoder.process_stream(io.BytesIO(raw))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_SEQUENCE_INVALID")

    def test_lease_leak_triggers_buffer_leak_failure(self) -> None:
        leaky_roi = FakeRoiConsumer(simulate_leak=True)
        decoder = CaptureStreamDecoder(leaky_roi, roi_config_hash="00" * 32)
        builder = SyntheticStreamBuilder()
        builder.emit_start().emit_frame()
        raw = builder.emit_sealed_end()

        receipt = decoder.process_stream(io.BytesIO(raw))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_BUFFER_LEAK")

    def test_roi_rejection_fails_session(self) -> None:
        rejecting_roi = FakeRoiConsumer(reject_sequence=0)
        decoder = CaptureStreamDecoder(rejecting_roi, roi_config_hash="00" * 32)
        builder = SyntheticStreamBuilder()
        builder.emit_start().emit_frame()
        raw = builder.emit_sealed_end()

        receipt = decoder.process_stream(io.BytesIO(raw))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_CONSUMER_REJECTED")

    def test_premature_pipe_closure(self) -> None:
        builder = SyntheticStreamBuilder()
        builder.emit_start().emit_frame()
        # Cut stream before end message
        raw = builder._buf.getvalue()

        receipt = self.decoder.process_stream(io.BytesIO(raw))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_PIPE_CLOSED")


if __name__ == "__main__":
    unittest.main()
