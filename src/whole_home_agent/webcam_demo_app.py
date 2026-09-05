r"""Streamlit interactive presentation for Live Windows Webcam Demo (Stage R4).

Displays a continuous live camera feed with no frame-count limit.
Streaming runs in a background thread; click Stop to seal and receipt.

Usage:
    .\.venv\Scripts\streamlit.exe run src/whole_home_agent/webcam_demo_app.py
"""

from __future__ import annotations

import secrets
import threading
import time
from typing import Optional

import numpy as np
from PIL import Image
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

from whole_home_agent.adapters.windows_webcam.decoder import CaptureStreamDecoder
from whole_home_agent.adapters.windows_webcam.live_camera_producer import (
    DEFAULT_CONFIG_HASH,
    LiveCameraProducer,
)
from whole_home_agent.adapters.windows_webcam.pipe_ipc import NamedPipeServer
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

_ROI_CONFIG_HASH = "66f578b8772a8c3d22188ab65bc44ea6f254e0ad84fcfe857f620cb2ec86a11e"

# Module-level shared buffer: background thread writes here; main thread reads on rerun.
# st.session_state CANNOT be written safely from non-main threads.
_FRAME_BUF: dict = {
    "rgb_bytes": None,
    "seq": -1,
    "count": 0,
    "streaming": False,
    "elapsed_start": None,
    "receipt": None,
    "elapsed": None,
}
_FRAME_LOCK = threading.Lock()


class StreamlitRoiIngress(RoiIngressPort):
    """ROI Ingress implementation for Streamlit live presentation."""

    def __init__(self) -> None:
        self.session: Optional[RoiIngressSessionV1] = None
        self.accepted_count = 0
        self.last_mean_val = 0.0
        self.motion_deltas: list[float] = []

    def open_session(self, session: RoiIngressSessionV1) -> None:
        self.session = session

    def accept(self, frame: RoiIngressFrameV1, lease: RoiFrameLeaseV1) -> RoiAcceptResultV1:
        buf = lease.pixel_memory_view
        sample = buf[::10000]
        mean_val = sum(sample) / len(sample) if len(sample) > 0 else 0.0
        delta = abs(mean_val - self.last_mean_val)
        self.last_mean_val = mean_val
        self.motion_deltas.append(delta)
        self.accepted_count += 1
        lease.release()

        config_hash = self.session.roi_config_hash if self.session else "00" * 32
        ingress_ver = self.session.roi_ingress_version if self.session else "windows_webcam_roi/1"
        return RoiAcceptResultV1(
            schema="whole-home-agent.roi-accept-result.v1",
            capture_session_id=frame.capture_session_id,
            source_sequence=frame.source_sequence,
            status="ACCEPTED",
            reason_code=None,
            accepted_monotonic_ns=frame.captured_monotonic_ns + 1_000_000,
            roi_ingress_version=ingress_ver,
            roi_config_hash=config_hash,
        )

    def accept_gap(self, gap: RoiIngressGapV1) -> None:
        pass

    def close_session(self, end: RoiIngressEndV1) -> None:
        pass

    def abort_session(self, failure_code: Optional[str]) -> None:
        pass


def _init_session_state() -> None:
    defaults: dict = {
        "streaming": False,         # mirrors _FRAME_BUF["streaming"] for UI branching
        "last_frame_img": None,     # PIL Image shown after streaming ends
        "producer": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _start_streaming(camera_idx: int) -> None:
    """Creates server, decoder, producer and launches background threads."""
    with _FRAME_LOCK:
        if _FRAME_BUF["streaming"]:
            return  # Prevent spawning duplicate threads if already streaming
        _FRAME_BUF["rgb_bytes"] = None
        _FRAME_BUF["seq"] = -1
        _FRAME_BUF["count"] = 0
        _FRAME_BUF["streaming"] = True
        _FRAME_BUF["elapsed_start"] = time.time()
        _FRAME_BUF["receipt"] = None
        _FRAME_BUF["elapsed"] = None

    session_nonce = secrets.token_hex(16)
    server = NamedPipeServer(session_nonce=session_nonce)
    roi_port = StreamlitRoiIngress()
    decoder = CaptureStreamDecoder(roi_port, roi_config_hash=_ROI_CONFIG_HASH)

    receipt_holder: list[Optional[RoiDeliveryReceiptV1]] = [None]

    def _decoder_worker() -> None:
        server.wait_for_connection()
        stream = server.as_stream()
        receipt_holder[0] = decoder.process_stream(stream)

    decoder_thread = threading.Thread(target=_decoder_worker, daemon=True)
    add_script_run_ctx(decoder_thread)
    decoder_thread.start()

    def _on_frame(seq: int, captured_ns: int, rgb_bytes: bytes) -> None:
        # Write to module-level buffer — safe from any thread
        with _FRAME_LOCK:
            _FRAME_BUF["rgb_bytes"] = rgb_bytes
            _FRAME_BUF["seq"] = seq
            _FRAME_BUF["count"] = seq + 1

    producer = LiveCameraProducer(
        session_nonce,
        camera_index=camera_idx,
        max_frames=None,          # unlimited
        target_fps=10,
        capture_config_hash=DEFAULT_CONFIG_HASH,
        on_frame_captured=_on_frame,
    )

    # Store producer reference so Stop button can call request_stop()
    st.session_state.producer = producer

    def _producer_worker() -> None:
        try:
            producer.run()
        finally:
            elapsed_start = _FRAME_BUF.get("elapsed_start") or time.time()
            with _FRAME_LOCK:
                _FRAME_BUF["streaming"] = False
                _FRAME_BUF["elapsed"] = time.time() - elapsed_start
                _FRAME_BUF["receipt"] = receipt_holder[0]
            server.close()

    producer_thread = threading.Thread(target=_producer_worker, daemon=True)
    add_script_run_ctx(producer_thread)
    producer_thread.start()
    st.session_state.producer_thread = producer_thread


def _stop_streaming() -> None:
    """Signals the producer to stop and waits for the camera thread to finish."""
    producer: Optional[LiveCameraProducer] = st.session_state.get("producer")
    if producer is not None:
        producer.request_stop()
    producer_thread: Optional[threading.Thread] = st.session_state.get("producer_thread")
    if producer_thread is not None and producer_thread.is_alive():
        producer_thread.join(timeout=2.0)
    with _FRAME_LOCK:
        _FRAME_BUF["streaming"] = False


def main() -> None:
    st.set_page_config(
        page_title="Whole Home Agent — Live Webcam Demo",
        page_icon="📷",
        layout="wide",
    )
    _init_session_state()

    st.title("Whole Home Agent · Live Windows Webcam Demo")
    st.caption("Physical Hardware Webcam → Named Pipe IPC → ROI Ingress Lease (Stage R4)")

    st.info(
        "**Real Hardware Pipeline Active**: Captures real-time frames from your machine's integrated "
        "`HD Webcam` at 1280×720 RGB24, transmitting across a secure Win32 Named Pipe into ROI Ingress. "
        "All frames use single-use synchronous read-only memory leases with zero disk retention."
    )

    col1, col2 = st.columns([1, 2])

    # Sync the main-thread session flag from the shared buffer every rerun
    with _FRAME_LOCK:
        is_streaming = _FRAME_BUF["streaming"]
    st.session_state.streaming = is_streaming

    with col1:
        st.subheader("1 · Demo Controls")
        camera_idx = st.number_input("Camera Index", min_value=0, max_value=5, value=0, disabled=is_streaming)

        if not is_streaming:
            start_btn = st.button("▶ Start Live Webcam Stream", type="primary", width="stretch")
            test_cam_btn = st.button("🔍 Test Camera Connection (Single Frame)", width="stretch")
        else:
            start_btn = False
            test_cam_btn = False
            stop_btn = st.button("⏹ Stop Streaming", type="primary", width="stretch")
            if stop_btn:
                _stop_streaming()
                st.rerun()

        st.markdown("---")

        # Live metrics while streaming
        if is_streaming:
            with _FRAME_LOCK:
                count = _FRAME_BUF["count"]
                elapsed_start = _FRAME_BUF["elapsed_start"] or time.time()
            elapsed = time.time() - elapsed_start
            st.metric("Frames Captured", count)
            st.metric("Elapsed", f"{elapsed:.1f} s")
            st.metric("Avg FPS", f"{count / max(elapsed, 0.1):.1f}")

        st.markdown("**Hardware Camera Profile:**")
        st.code(
            "Device: SunplusIT HD Webcam\n"
            "Resolution: 1280 x 720 (720p HD)\n"
            "Pixel Format: RGB24 (3,840 stride)\n"
            "Transport: Win32 Named Pipe\n"
            "Retention: None (In-Memory Only)",
            language="yaml",
        )

    with col2:
        st.subheader("2 · Live Stream & Ingress Feed")
        preview_container = st.empty()
        status_container = st.empty()
        receipt_container = st.empty()

        # Single-frame camera test
        if test_cam_btn:
            import cv2
            cap = cv2.VideoCapture(int(camera_idx), cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb)
                st.session_state.last_frame_img = img
                status_container.success(
                    f"✓ Camera #{camera_idx} connected! Shape: {frame.shape}, Brightness mean: {frame.mean():.1f}"
                )
            else:
                status_container.error(f"Failed to read from camera #{camera_idx}.")

        # Start streaming
        if start_btn:
            _start_streaming(int(camera_idx))
            st.rerun()

        # Display live frame while streaming
        if is_streaming:
            with _FRAME_LOCK:
                rgb_bytes = _FRAME_BUF["rgb_bytes"]
                seq = _FRAME_BUF["seq"]
                count = _FRAME_BUF["count"]
                elapsed_start = _FRAME_BUF["elapsed_start"] or time.time()

            if rgb_bytes is not None:
                arr = np.frombuffer(rgb_bytes, dtype=np.uint8).reshape((720, 1280, 3))
                img = Image.fromarray(arr, "RGB")
                st.session_state.last_frame_img = img
                elapsed = time.time() - elapsed_start
                preview_container.image(
                    img,
                    caption=f"🔴 LIVE — Frame #{seq + 1} | {count} frames | {elapsed:.1f} s",
                    width="stretch",
                )
            else:
                preview_container.info("📷 Connecting to camera, first frame incoming...")

            # Trigger rerun to pull the next frame from the background thread
            time.sleep(0.12)   # ~8 fps UI refresh
            st.rerun()

        elif st.session_state.last_frame_img is not None:
            # Show last captured frame after streaming stops
            preview_container.image(
                st.session_state.last_frame_img,
                caption="Last Captured Frame (1280×720 RGB24)",
                width="stretch",
            )
        else:
            preview_container.markdown(
                """
                <div style="border: 2px dashed #4B5563; border-radius: 10px; padding: 60px 20px; text-align: center; background-color: #1F2937; color: #E5E7EB;">
                    <div style="font-size: 48px; margin-bottom: 12px;">📷</div>
                    <div style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">相機待命中 (Camera Standby)</div>
                    <div style="font-size: 14px; color: #9CA3AF;">
                        請點擊左側 <b>「▶ Start Live Webcam Stream」</b> 啟動無限串流，<br>
                        或點擊 <b>「🔍 Test Camera Connection」</b> 進行單格快照測試。
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Receipt display: read from _FRAME_BUF after streaming ends
        with _FRAME_LOCK:
            receipt: Optional[RoiDeliveryReceiptV1] = _FRAME_BUF["receipt"]
            elapsed_done = _FRAME_BUF["elapsed"] or 0.0

        if receipt is not None and not is_streaming:
            if receipt.status == "COMPLETE":
                status_container.success(
                    f"✓ Session SEALED in {elapsed_done:.2f} s | {receipt.roi_frames_accepted} frames accepted"
                )
            else:
                status_container.warning(
                    f"Session ended: {receipt.status} | failure: {receipt.failure_code}"
                )

            with receipt_container.container():
                st.subheader("3 · Cryptographic Delivery Receipt")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Status", receipt.status)
                m2.metric("Accepted Frames", f"{receipt.roi_frames_accepted}/{receipt.frame_messages_received}")
                m3.metric(
                    "P50 Latency",
                    f"{receipt.delivery_latency_p50_ns / 1_000_000:.2f} ms" if receipt.delivery_latency_p50_ns else "N/A",
                )
                m4.metric("Peak Memory", f"{receipt.peak_application_frame_slots} slots")

                st.markdown("**Receipt Verification Details:**")
                st.json({
                    "capture_session_id": receipt.capture_session_id,
                    "source_id": receipt.source_id,
                    "stream_sha256": receipt.stream_sha256,
                    "frames_received": receipt.frame_messages_received,
                    "frames_accepted": receipt.roi_frames_accepted,
                    "frames_rejected": receipt.roi_frames_rejected,
                    "gap_positions": receipt.gap_positions,
                    "resource_release_ok": receipt.resource_release_ok,
                    "raw_retention": receipt.raw_retention,
                })


if __name__ == "__main__":
    main()
