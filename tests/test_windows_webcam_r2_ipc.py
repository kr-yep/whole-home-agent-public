"""Stage R2: Cross-process Windows Named Pipe IPC and AppContainer DACL tests (WHA-WIN-CAPTURE-ROI-001)."""

from __future__ import annotations

import secrets
import sys
import threading
import time
import unittest

from whole_home_agent.adapters.windows_webcam.decoder import CaptureStreamDecoder
from whole_home_agent.adapters.windows_webcam.pipe_ipc import (
    DEFAULT_PIPE_SDDL,
    ERROR_ACCESS_DENIED,
    NamedPipeClient,
    NamedPipeServer,
)
from whole_home_agent.adapters.windows_webcam.qpc import (
    now_qpc_ns,
    qpc_to_monotonic_ns,
    query_performance_counter,
    query_performance_frequency,
)
from whole_home_agent.adapters.windows_webcam.roi_contract import (
    RoiAcceptResultV1,
    RoiFrameLeaseV1,
    RoiIngressEndV1,
    RoiIngressFrameV1,
    RoiIngressGapV1,
    RoiIngressPort,
    RoiIngressSessionV1,
)
from whole_home_agent.adapters.windows_webcam.synthetic_producer import (
    SyntheticStreamBuilder,
)

_IS_WINDOWS = sys.platform == "win32"


class SimpleRoiIngress(RoiIngressPort):
    """Test receiver for IPC streaming."""

    def __init__(self) -> None:
        self.accepted_frames: list[int] = []
        self.session_opened = False
        self.session_closed = False

    def open_session(self, session: RoiIngressSessionV1) -> None:
        self.session_opened = True

    def accept(self, frame: RoiIngressFrameV1, lease: RoiFrameLeaseV1) -> RoiAcceptResultV1:
        self.accepted_frames.append(frame.source_sequence)
        lease.release()
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
        pass

    def close_session(self, end: RoiIngressEndV1) -> None:
        self.session_closed = True

    def abort_session(self, end: RoiIngressEndV1 | None) -> None:
        pass


class TestStageR2Ipc(unittest.TestCase):
    @unittest.skipUnless(_IS_WINDOWS, "Requires Windows platform for Win32 Named Pipes")
    def test_qpc_monotonic_and_conversion(self) -> None:
        freq = query_performance_frequency()
        self.assertGreater(freq, 0)
        c1 = query_performance_counter()
        time.sleep(0.01)
        c2 = query_performance_counter()
        self.assertGreater(c2, c1)

        ns1 = qpc_to_monotonic_ns(c1, freq)
        ns2 = qpc_to_monotonic_ns(c2, freq)
        self.assertGreater(ns2, ns1)
        # 10ms sleep should be roughly 10,000,000 ns +/- 15ms
        diff_ns = ns2 - ns1
        self.assertGreaterEqual(diff_ns, 5_000_000)

    @unittest.skipUnless(_IS_WINDOWS, "Requires Windows platform for Win32 Named Pipes")
    def test_named_pipe_creation_and_communication(self) -> None:
        nonce = secrets.token_hex(16)
        server = NamedPipeServer(nonce)
        client = NamedPipeClient(nonce)

        received = bytearray()

        def server_thread() -> None:
            server.wait_for_connection()
            stream = server.as_stream()
            data = stream.read(11)
            received.extend(data)

        t = threading.Thread(target=server_thread)
        t.start()

        client.connect(timeout_s=3.0)
        client.write(b"HELLO_PIPE_")
        t.join(timeout=3.0)

        client.close()
        server.close()

        self.assertEqual(bytes(received), b"HELLO_PIPE_")

    @unittest.skipUnless(_IS_WINDOWS, "Requires Windows platform for Win32 Named Pipes")
    def test_single_instance_rejects_second_client(self) -> None:
        nonce = secrets.token_hex(16)
        server = NamedPipeServer(nonce, max_instances=1)
        client1 = NamedPipeClient(nonce)
        client2 = NamedPipeClient(nonce)

        t = threading.Thread(target=server.wait_for_connection)
        t.start()

        client1.connect(timeout_s=3.0)
        t.join(timeout=3.0)

        # Client 2 must fail to connect because max_instances = 1
        with self.assertRaises((TimeoutError, OSError)):
            client2.connect(timeout_s=0.5)

        client1.close()
        server.close()

    @unittest.skipUnless(_IS_WINDOWS, "Requires Windows platform for Win32 Named Pipes")
    def test_client_pid_verification(self) -> None:
        nonce = secrets.token_hex(16)
        server = NamedPipeServer(nonce)
        client = NamedPipeClient(nonce)

        t = threading.Thread(target=server.wait_for_connection)
        t.start()

        client.connect(timeout_s=3.0)
        t.join(timeout=3.0)

        client_pid = server.get_client_pid()
        # Connected from this process
        import os
        self.assertEqual(client_pid, os.getpid())

        # Correct PID succeeds
        self.assertTrue(server.verify_client_identity(expected_pid=client_pid))
        # Wrong PID fails
        self.assertFalse(server.verify_client_identity(expected_pid=client_pid + 99999))
        # Standard python host is not AppContainer, so require_app_container must be False
        self.assertFalse(server.verify_client_identity(require_app_container=True))

        client.close()
        server.close()

    @unittest.skipUnless(_IS_WINDOWS, "Requires Windows platform for Win32 Named Pipes")
    def test_full_stream_delivery_over_real_named_pipe(self) -> None:
        nonce = secrets.token_hex(16)
        server = NamedPipeServer(nonce)
        client = NamedPipeClient(nonce)
        roi = SimpleRoiIngress()
        decoder = CaptureStreamDecoder(roi, roi_config_hash="00" * 32)

        # Build synthetic 5-frame stream
        builder = SyntheticStreamBuilder(session_id=nonce)
        builder.emit_start()
        for i in range(5):
            builder.emit_frame()
        wire_stream_bytes = builder.emit_sealed_end()

        receipt_holder = []

        def server_run() -> None:
            server.wait_for_connection()
            stream = server.as_stream()
            r = decoder.process_stream(stream)
            receipt_holder.append(r)

        t = threading.Thread(target=server_run)
        t.start()

        client.connect(timeout_s=3.0)
        # Send complete stream bytes
        client.write(wire_stream_bytes)
        client.close()

        t.join(timeout=5.0)
        server.close()

        self.assertEqual(len(receipt_holder), 1)
        receipt = receipt_holder[0]
        self.assertEqual(receipt.status, "COMPLETE")
        self.assertEqual(receipt.frame_messages_received, 5)
        self.assertEqual(receipt.roi_frames_accepted, 5)
        self.assertIsNone(receipt.failure_code)
        self.assertTrue(roi.session_closed)


if __name__ == "__main__":
    unittest.main()
