"""Stage R3: Fault injection, adversarial packets, backpressure, and isolation tests.

Specification: WHA-WIN-CAPTURE-ROI-001 (Section 13, 14, 15, 16, 19, 21, 22, 23, 24)
"""

from __future__ import annotations

import io
import os
import secrets
import struct
import sys
import threading
import time
import unittest
from typing import Optional

from whole_home_agent.adapters.windows_webcam.decoder import (
    CaptureStreamDecoder,
    STATE_ABORTED,
    STATE_COMPLETE,
    STATE_FAILED,
)
from whole_home_agent.adapters.windows_webcam.pipe_ipc import (
    NamedPipeClient,
    NamedPipeServer,
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
    FIXED_PREFIX_BYTES,
    FRAME_BODY_BYTES,
    KIND_END,
    KIND_FRAME,
    KIND_GAP,
    KIND_START,
    WIRE_MAGIC,
    WIRE_VERSION,
    WireFramingError,
    WirePrefix,
    dumps_canonical_json,
)

_IS_WINDOWS = sys.platform == "win32"


class FaultInjectingRoiConsumer(RoiIngressPort):
    """Configurable ROI receiver for testing faults, timeouts, leaks, and rejections."""

    def __init__(
        self,
        *,
        delay_on_frame_s: float = 0.0,
        delay_on_gap_s: float = 0.0,
        leak_on_frame: Optional[int] = None,
        reject_frame: Optional[int] = None,
        raise_on_frame: Optional[int] = None,
        raise_on_gap: bool = False,
    ) -> None:
        self.delay_on_frame_s = delay_on_frame_s
        self.delay_on_gap_s = delay_on_gap_s
        self.leak_on_frame = leak_on_frame
        self.reject_frame = reject_frame
        self.raise_on_frame = raise_on_frame
        self.raise_on_gap = raise_on_gap

        self.session_opened: Optional[RoiIngressSessionV1] = None
        self.accepted_frames: list[int] = []
        self.received_gaps: list[RoiIngressGapV1] = []
        self.session_closed: Optional[RoiIngressEndV1] = None
        self.session_aborted: bool = False

    def open_session(self, session: RoiIngressSessionV1) -> None:
        self.session_opened = session

    def accept(self, frame: RoiIngressFrameV1, lease: RoiFrameLeaseV1) -> RoiAcceptResultV1:
        # Check read-only memory view
        view = lease.pixel_memory_view
        if len(view) != FRAME_BODY_BYTES or not view.readonly:
            raise ValueError("Invalid pixel memory view in lease")

        if self.delay_on_frame_s > 0:
            time.sleep(self.delay_on_frame_s)

        if self.raise_on_frame == frame.source_sequence:
            lease.release()
            raise RuntimeError(f"Simulated consumer crash on frame {frame.source_sequence}")

        if self.leak_on_frame != frame.source_sequence:
            lease.release()

        if self.reject_frame == frame.source_sequence:
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
            accepted_monotonic_ns=frame.captured_monotonic_ns + 1_000_000,
            roi_ingress_version="windows_webcam_roi/1",
            roi_config_hash="00" * 32,
        )

    def accept_gap(self, gap: RoiIngressGapV1) -> None:
        if self.delay_on_gap_s > 0:
            time.sleep(self.delay_on_gap_s)
        if self.raise_on_gap:
            raise RuntimeError("Simulated consumer crash on gap")
        self.received_gaps.append(gap)

    def close_session(self, end: RoiIngressEndV1) -> None:
        self.session_closed = end

    def abort_session(self, end: RoiIngressEndV1 | None) -> None:
        self.session_aborted = True


class MockMonotonicClock:
    """Mock clock to deterministically test timing without thread sleeps."""

    def __init__(self, start_ns: int = 1_000_000_000) -> None:
        self.current_ns = start_ns
        self.advance_on_call = 0

    def __call__(self) -> int:
        ret = self.current_ns
        self.current_ns += self.advance_on_call
        return ret


class TestStageR3FaultsAndIsolation(unittest.TestCase):
    """Comprehensive test suite for Stage R3 fault injection and adversarial packets."""

    # 1. Backpressure and Queue Overflow
    def test_queue_saturation_overflow_gaps(self) -> None:
        """Simulates queue drops under backpressure: 5 frames -> 10 dropped gap -> 5 frames."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)
        builder = SyntheticStreamBuilder()
        builder.emit_start()

        # Frames 0 to 4
        for i in range(5):
            builder.emit_frame()

        # Drop 10 frames (seq 5 to 14) due to queue overflow backpressure
        builder.emit_gap(5, 14, reason="queue_overflow")

        # Frames 15 to 19
        for i in range(15, 20):
            builder.emit_frame(sequence=i)

        stream_bytes = builder.emit_sealed_end()
        receipt = decoder.process_stream(io.BytesIO(stream_bytes))

        self.assertEqual(receipt.status, "COMPLETE")
        self.assertEqual(receipt.acquisition_positions, 20)
        self.assertEqual(receipt.frame_messages_received, 10)
        self.assertEqual(receipt.roi_frames_accepted, 10)
        self.assertEqual(receipt.gap_positions, 10)
        self.assertEqual(receipt.queue_overflow_positions, 10)
        self.assertEqual(receipt.last_source_sequence, 19)
        self.assertIsNone(receipt.failure_code)
        self.assertTrue(receipt.resource_release_ok)
        self.assertEqual(len(roi.received_gaps), 1)
        # Gap >= 3 requires temporal reset
        self.assertTrue(roi.received_gaps[0].reset_temporal_state)

    # 2. 100ms Consumer Timeout on Frame
    def test_slow_roi_consumer_timeout_on_frame(self) -> None:
        """ROI accept exceeding 100ms triggers ROI_CONSUMER_TIMEOUT and FAILED receipt."""
        clock = MockMonotonicClock(1_000_000_000)
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(
            roi,
            roi_config_hash="00" * 32,
            time_monotonic_ns_fn=clock,
        )
        builder = SyntheticStreamBuilder()
        builder.emit_start().emit_frame()
        raw = builder.emit_sealed_end()

        # Set clock to advance by 105ms (105_000_000 ns) between t_start and t_end
        clock.advance_on_call = 105_000_000

        receipt = decoder.process_stream(io.BytesIO(raw))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_CONSUMER_TIMEOUT")
        self.assertTrue(roi.session_aborted)
        self.assertTrue(receipt.resource_release_ok)

    # 3. 100ms Consumer Timeout on Gap
    def test_slow_roi_consumer_timeout_on_gap(self) -> None:
        """ROI accept_gap exceeding 100ms triggers ROI_CONSUMER_TIMEOUT."""
        clock = MockMonotonicClock(1_000_000_000)
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(
            roi,
            roi_config_hash="00" * 32,
            time_monotonic_ns_fn=clock,
        )
        builder = SyntheticStreamBuilder()
        builder.emit_start()
        builder.emit_gap(0, 1, reason="capture_overrun")
        builder.emit_frame(sequence=2)
        raw = builder.emit_sealed_end()

        clock.advance_on_call = 105_000_000

        receipt = decoder.process_stream(io.BytesIO(raw))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_CONSUMER_TIMEOUT")
        self.assertTrue(roi.session_aborted)

    # 4. Pipe Break Mid-Stream (Real Win32 Named Pipe)
    @unittest.skipUnless(_IS_WINDOWS, "Requires Windows platform for Win32 Named Pipes")
    def test_pipe_break_mid_stream(self) -> None:
        """Abrupt client close mid-stream fails closed with ROI_PIPE_CLOSED."""
        nonce = secrets.token_hex(16)
        server = NamedPipeServer(nonce)
        client = NamedPipeClient(nonce)
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        builder = SyntheticStreamBuilder(session_id=nonce)
        builder.emit_start().emit_frame()
        partial_bytes = builder._buf.getvalue()

        receipt_holder = []

        def server_run() -> None:
            server.wait_for_connection()
            stream = server.as_stream()
            r = decoder.process_stream(stream)
            receipt_holder.append(r)

        t = threading.Thread(target=server_run, daemon=True)
        t.start()

        client.connect(timeout_s=3.0)
        client.write(partial_bytes)
        # Abruptly close client without END
        client.close()

        t.join(timeout=3.0)
        server.close()

        self.assertEqual(len(receipt_holder), 1)
        receipt = receipt_holder[0]
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_PIPE_CLOSED")
        self.assertTrue(roi.session_aborted)
        self.assertTrue(receipt.resource_release_ok)

    # 5. Malformed Metadata Rejection (Adversarial JSON)
    def test_malformed_metadata_rejection_invalid_syntax(self) -> None:
        """Malformed JSON syntax fails closed with ROI_SCHEMA_INVALID."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        # Wire prefix with invalid JSON body
        bad_json = b"{this is broken: json, [1, 2]"
        prefix = WirePrefix(
            magic=WIRE_MAGIC,
            wire_version=WIRE_VERSION,
            message_kind=KIND_START,
            flags=0,
            metadata_length=len(bad_json),
            body_length=0,
        )
        payload = prefix.pack() + bad_json

        receipt = decoder.process_stream(io.BytesIO(payload))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_SCHEMA_INVALID")

    def test_malformed_metadata_rejection_duplicate_keys(self) -> None:
        """Duplicate JSON keys fail closed with ROI_SCHEMA_INVALID."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        dup_json = b'{"schema":"v1","capture_session_id":"abc","schema":"v2"}'
        # Pad to at least 64 bytes
        dup_json = dup_json.ljust(64, b" ")
        prefix = WirePrefix(
            magic=WIRE_MAGIC,
            wire_version=WIRE_VERSION,
            message_kind=KIND_START,
            flags=0,
            metadata_length=len(dup_json),
            body_length=0,
        )
        payload = prefix.pack() + dup_json

        receipt = decoder.process_stream(io.BytesIO(payload))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_SCHEMA_INVALID")

    def test_malformed_metadata_rejection_floats(self) -> None:
        """Floating point values in metadata fail closed with ROI_SCHEMA_INVALID."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        float_json = b'{"schema":"v1","target_fps_numerator":10.5}'
        float_json = float_json.ljust(64, b" ")
        prefix = WirePrefix(
            magic=WIRE_MAGIC,
            wire_version=WIRE_VERSION,
            message_kind=KIND_START,
            flags=0,
            metadata_length=len(float_json),
            body_length=0,
        )
        payload = prefix.pack() + float_json

        receipt = decoder.process_stream(io.BytesIO(payload))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_SCHEMA_INVALID")

    # 6. Oversize and Undersize Metadata Rejection
    def test_oversize_metadata_rejection(self) -> None:
        """Metadata length > 8192 bytes raises framing error -> ROI_SCHEMA_INVALID."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        # Build raw 16-byte prefix claiming 8193 metadata length
        raw_prefix = struct.pack(
            ">4sBBHII",
            WIRE_MAGIC,
            WIRE_VERSION,
            KIND_START,
            0,
            8193,  # Out of bounds (> 8192)
            0,
        )
        receipt = decoder.process_stream(io.BytesIO(raw_prefix))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_SCHEMA_INVALID")

    def test_undersize_metadata_rejection(self) -> None:
        """Metadata length < 2 bytes raises framing error -> ROI_SCHEMA_INVALID."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        raw_prefix = struct.pack(
            ">4sBBHII",
            WIRE_MAGIC,
            WIRE_VERSION,
            KIND_START,
            0,
            1,  # Out of bounds (< 2)
            0,
        )
        receipt = decoder.process_stream(io.BytesIO(raw_prefix))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_SCHEMA_INVALID")

    # 7. Body Size Mismatch Rejection
    def test_body_size_mismatch_rejection(self) -> None:
        """KIND_FRAME with incorrect body length fails with ROI_SCHEMA_INVALID or ROI_PAYLOAD_SIZE_INVALID."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        # Prefix claiming 1000 bytes for FRAME
        raw_prefix = struct.pack(
            ">4sBBHII",
            WIRE_MAGIC,
            WIRE_VERSION,
            KIND_FRAME,
            0,
            128,
            1000,  # Invalid body length for frame
        )
        receipt = decoder.process_stream(io.BytesIO(raw_prefix))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_SCHEMA_INVALID")

    # 8. Single Bitflip Digest Corruption
    def test_digest_corruption_bitflip(self) -> None:
        """A single bit flip in frame payload triggers ROI_DIGEST_MISMATCH."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        builder = SyntheticStreamBuilder()
        builder.emit_start()
        for i in range(5):
            builder.emit_frame()
        valid_stream = builder.emit_sealed_end()

        # Tamper frame 2's payload: flip one bit at byte 2,000,000
        tampered = bytearray(valid_stream)
        tampered[2_000_000] ^= 0x01

        receipt = decoder.process_stream(io.BytesIO(tampered))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_DIGEST_MISMATCH")
        self.assertTrue(roi.session_aborted)

    # 9. Unexplained Sequence Gap Rejection
    def test_unexplained_sequence_gap_rejection(self) -> None:
        """Sequence jump (e.g. seq 0 to seq 2 without GAP) fails closed with ROI_SEQUENCE_INVALID."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        builder = SyntheticStreamBuilder()
        builder.emit_start()
        builder.emit_frame(sequence=0)
        # Directly send frame 2 without GAP for 1
        builder.emit_frame(sequence=2)
        raw = builder.emit_sealed_end()

        receipt = decoder.process_stream(io.BytesIO(raw))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_SEQUENCE_INVALID")
        self.assertTrue(roi.session_aborted)

    # 10. Memory Leak and Lease Misuse
    def test_lease_double_release_raises(self) -> None:
        """RoiFrameLeaseV1 raises ValueError on duplicate release."""
        buf = bytearray(FRAME_BODY_BYTES)
        lease = RoiFrameLeaseV1(buf)
        lease.release()
        with self.assertRaises(ValueError):
            lease.release()

    def test_lease_leak_caught_by_decoder(self) -> None:
        """Unreleased lease is caught and triggers ROI_BUFFER_LEAK."""
        leaky_roi = FaultInjectingRoiConsumer(leak_on_frame=0)
        decoder = CaptureStreamDecoder(leaky_roi, roi_config_hash="00" * 32)

        builder = SyntheticStreamBuilder()
        builder.emit_start().emit_frame()
        raw = builder.emit_sealed_end()

        receipt = decoder.process_stream(io.BytesIO(raw))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_BUFFER_LEAK")
        self.assertTrue(leaky_roi.session_aborted)

    # 11. Peer Identity / Wrong Package Verification
    @unittest.skipUnless(_IS_WINDOWS, "Requires Windows platform for Win32 Named Pipes")
    def test_peer_identity_wrong_package_and_pid(self) -> None:
        """Server identity check rejects wrong PID or non-AppContainer process."""
        nonce = secrets.token_hex(16)
        server = NamedPipeServer(nonce)
        client = NamedPipeClient(nonce)

        t = threading.Thread(target=server.wait_for_connection, daemon=True)
        t.start()

        client.connect(timeout_s=3.0)
        t.join(timeout=3.0)

        real_pid = client.get_client_pid() if hasattr(client, "get_client_pid") else os.getpid()

        # 1. Matching PID succeeds
        self.assertTrue(server.verify_client_identity(expected_pid=real_pid))

        # 2. Mismatched PID fails
        self.assertFalse(server.verify_client_identity(expected_pid=real_pid + 8888))

        # 3. Standard user process is not in AppContainer package -> must be False
        self.assertFalse(server.verify_client_identity(require_app_container=True))

        # 4. Disconnect client cleanly
        server.disconnect_client()
        client.close()
        server.close()

    # 12. Rapid Repeated Launch Clean Cleanup (10 Consecutive Sessions)
    @unittest.skipUnless(_IS_WINDOWS, "Requires Windows platform for Win32 Named Pipes")
    def test_rapid_repeated_launch_clean_cleanup(self) -> None:
        """10 consecutive sessions rapidly opened and closed over Win32 pipes without leaks."""
        for i in range(10):
            nonce = secrets.token_hex(16)
            server = NamedPipeServer(nonce)
            client = NamedPipeClient(nonce)
            roi = FaultInjectingRoiConsumer()
            decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

            builder = SyntheticStreamBuilder(session_id=nonce)
            builder.emit_start()
            builder.emit_frame(sequence=0)
            builder.emit_frame(sequence=1)
            raw = builder.emit_sealed_end()

            receipt_holder = []

            def s_run(s=server, d=decoder) -> None:
                s.wait_for_connection()
                st = s.as_stream()
                r = d.process_stream(st)
                receipt_holder.append(r)

            t = threading.Thread(target=s_run, daemon=True)
            t.start()

            client.connect(timeout_s=3.0)
            client.write(raw)
            client.close()

            t.join(timeout=3.0)
            server.close()

            self.assertEqual(len(receipt_holder), 1)
            receipt = receipt_holder[0]
            self.assertEqual(receipt.status, "COMPLETE", f"Iteration {i} failed with {receipt.failure_code}")
            self.assertEqual(receipt.frame_messages_received, 2)
            self.assertTrue(receipt.resource_release_ok)

    # 13. Cancellation in Every State
    def test_cancellation_in_wait_start_state(self) -> None:
        """Empty stream before START fails closed with ROI_EARLY_END."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        receipt = decoder.process_stream(io.BytesIO(b""))
        self.assertEqual(receipt.status, "FAILED")
        self.assertEqual(receipt.failure_code, "ROI_EARLY_END")

    def test_cancellation_in_active_state_aborted(self) -> None:
        """Abort signal in ACTIVE state produces ABORTED receipt with capture failure code."""
        roi = FaultInjectingRoiConsumer()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        builder = SyntheticStreamBuilder()
        builder.emit_start().emit_frame()
        # Aborted end with CAPTURE_CANCELLED
        raw = builder.emit_aborted_end(failure_code="CAPTURE_CANCELLED")

        receipt = decoder.process_stream(io.BytesIO(raw))
        self.assertEqual(receipt.status, "ABORTED")
        self.assertEqual(receipt.source_end_status, "ABORTED")
        self.assertEqual(receipt.source_failure_code, "CAPTURE_CANCELLED")
        self.assertTrue(roi.session_aborted)
        self.assertTrue(receipt.resource_release_ok)

    # 14. Zero Retention and Privacy Audit
    def test_zero_retention_audit_after_failures(self) -> None:
        """Verifies zero raw video/image files and zero SQLite writes occur on failure."""
        forbidden_extensions = (".raw", ".rgb", ".bmp", ".jpg", ".jpeg", ".png", ".mp4", ".avi", ".sqlite", ".db")
        initial_files = set()
        for root, _, files in os.walk("."):
            for f in files:
                if f.endswith(forbidden_extensions):
                    initial_files.add(os.path.join(root, f))

        # Run several fault scenarios
        self.test_digest_corruption_bitflip()
        self.test_unexplained_sequence_gap_rejection()
        self.test_malformed_metadata_rejection_invalid_syntax()

        # Verify no new forbidden files created
        current_files = set()
        for root, _, files in os.walk("."):
            for f in files:
                if f.endswith(forbidden_extensions):
                    current_files.add(os.path.join(root, f))

        new_files = current_files - initial_files
        self.assertEqual(new_files, set(), f"Forbidden raw files or SQLite detected: {new_files}")


if __name__ == "__main__":
    unittest.main()
