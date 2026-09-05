"""Live Windows webcam stream producer for Stage R4 execution.

Captures real-time frames from local hardware camera (DirectShow UVC),
normalizes to 1280x720 RGB24 contiguous buffer, applies QPC monotonic
timestamps, updates SHA-256 stream digest, and streams over Win32 Named Pipe.

Specification: WHA-WIN-CAPTURE-ROI-001 (Section 10, 11, 12, 14, 23)
Governance: Human-initiated activation, zero raw frame persistence.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from .pipe_ipc import NamedPipeClient
from .qpc import now_qpc_ns
from .synthetic_producer import pack_wire_message
from .wire_protocol import (
    FRAME_BODY_BYTES,
    KIND_END,
    KIND_FRAME,
    KIND_GAP,
    KIND_START,
    StreamDigestCalculator,
)

logger = logging.getLogger("wha.capture.live")

# Default capture configuration hash for windows-webcam-d1-v1
DEFAULT_CONFIG_HASH = "9122af323d482053e7f7f8e7f95b1db64ddee66df37ad9c5d139f1f87e637c6e"


class LiveCameraProducer:
    """Acquires live frames from Windows camera and streams them to SemanticHost.

    Runs continuously until ``request_stop()`` is called (or the camera fails).
    Pass ``max_frames`` only when a hard upper limit is needed (e.g. CLI tests)."""

    def __init__(
        self,
        session_nonce: str,
        *,
        camera_index: int = 0,
        max_frames: Optional[int] = None,
        target_fps: int = 10,
        capture_config_hash: str = DEFAULT_CONFIG_HASH,
        source_id: str = "windows-integrated-webcam-01",
        on_frame_captured: Optional[Callable[[int, int, bytes], None]] = None,
    ) -> None:
        self.session_nonce = session_nonce
        self.camera_index = camera_index
        self.max_frames = max_frames          # None = unlimited
        self.target_fps = target_fps
        self.capture_config_hash = capture_config_hash
        self.source_id = source_id
        self.on_frame_captured = on_frame_captured

        self._stop_event = threading.Event()
        self._pipe_client: Optional[NamedPipeClient] = None
        self._current_sequence = 0
        self._dropped_count = 0
        self._digest_calc: Optional[StreamDigestCalculator] = None


    def request_stop(self) -> None:
        """Signals producer to finish gracefully after current frame."""
        self._stop_event.set()

    def run(self) -> dict[str, any]:
        """Main producer execution loop. Returns capture run summary."""
        import cv2

        self._stop_event.clear()
        self._pipe_client = NamedPipeClient(self.session_nonce)
        self._pipe_client.connect(timeout_s=5.0)

        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            # Fallback to default backend if DSHOW fails
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                self._emit_failed_end("LAUNCH_CAMERA_EXCLUSIVE_CONTROL_UNAVAILABLE")
                raise RuntimeError(f"Failed to open camera device index {self.camera_index}")

        try:
            # Configure 1280x720
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)

            # Warm-up / initial frame check
            ret, initial_frame = cap.read()
            if not ret or initial_frame is None:
                self._emit_failed_end("LAUNCH_CAMERA_FORMAT_VERIFY_FAILED")
                raise RuntimeError("Failed to read initial frame from camera")

            started_monotonic_ns = now_qpc_ns()
            self._digest_calc = StreamDigestCalculator(
                capture_config_hash=self.capture_config_hash,
                width=1280,
                height=720,
                target_fps_numerator=self.target_fps,
                target_fps_denominator=1,
                started_monotonic_ns=started_monotonic_ns,
            )

            # 1. Emit START message
            start_meta = {
                "schema": "whole-home-agent.capture-message.v1",
                "kind": "start",
                "capture_session_id": self.session_nonce,
                "source_id": self.source_id,
                "source_profile": "windows_webcam_d1_v1",
                "capture_config_hash": self.capture_config_hash,
                "width": 1280,
                "height": 720,
                "pixel_format": "rgb24",
                "target_fps_numerator": self.target_fps,
                "target_fps_denominator": 1,
                "started_monotonic_ns": started_monotonic_ns,
                "activation_decision_id": None,
                "policy_version": None,
                "raw_retention": "none",
                "audio_enabled": False,
                "network_egress_enabled": False,
            }
            start_record = pack_wire_message(KIND_START, start_meta)
            self._pipe_client.write(start_record)

            # Pacing setup: interval in ns
            target_interval_ns = 1_000_000_000 // self.target_fps
            last_frame_ns = started_monotonic_ns

            # 2. Main Capture Loop — runs until stop is requested or max_frames reached
            seq = 0
            while not self._stop_event.is_set():
                if self.max_frames is not None and seq >= self.max_frames:
                    logger.info("Live camera capture reached max_frames=%d limit", self.max_frames)
                    break

                ret, frame = cap.read()
                captured_ns = now_qpc_ns()

                if not ret or frame is None:
                    # Capture overrun / driver frame drop
                    self._dropped_count += 1
                    gap_meta = {
                        "schema": "whole-home-agent.capture-message.v1",
                        "kind": "gap",
                        "capture_session_id": self.session_nonce,
                        "source_id": self.source_id,
                        "first_missing_sequence": seq,
                        "last_missing_sequence": seq,
                        "detected_monotonic_ns": captured_ns,
                        "reason": "capture_overrun",
                    }
                    self._digest_calc.update_gap(
                        first_missing_sequence=seq,
                        last_missing_sequence=seq,
                        detected_monotonic_ns=captured_ns,
                        reason="capture_overrun",
                    )
                    gap_record = pack_wire_message(KIND_GAP, gap_meta)
                    self._pipe_client.write(gap_record)
                    seq += 1
                    continue

                # Normalize to 1280x720 RGB24
                if frame.shape[0] != 720 or frame.shape[1] != 1280:
                    frame = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_LINEAR)

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb_bytes = rgb_frame.tobytes()

                if len(rgb_bytes) != FRAME_BODY_BYTES:
                    raise ValueError(f"Invalid frame byte length: {len(rgb_bytes)}")

                # Update digest
                self._digest_calc.update_frame(
                    source_sequence=seq,
                    captured_monotonic_ns=captured_ns,
                    rgb_bytes=rgb_bytes,
                )

                # Emit FRAME message
                frame_meta = {
                    "schema": "whole-home-agent.capture-message.v1",
                    "kind": "frame",
                    "capture_session_id": self.session_nonce,
                    "source_id": self.source_id,
                    "source_sequence": seq,
                    "captured_monotonic_ns": captured_ns,
                    "width": 1280,
                    "height": 720,
                    "pixel_format": "rgb24",
                }
                frame_record = pack_wire_message(KIND_FRAME, frame_meta, rgb_bytes)
                self._pipe_client.write(frame_record)

                self._current_sequence = seq + 1

                # Callback for optional UI preview
                if self.on_frame_captured is not None:
                    try:
                        self.on_frame_captured(seq, captured_ns, rgb_bytes)
                    except Exception as cb_err:
                        logger.warning("Frame preview callback error: %s", cb_err)

                # Rate pacing
                now_ns = now_qpc_ns()
                elapsed_since_last = now_ns - last_frame_ns
                if elapsed_since_last < target_interval_ns:
                    sleep_s = (target_interval_ns - elapsed_since_last) / 1_000_000_000.0
                    if sleep_s > 0.001:
                        time.sleep(sleep_s)
                last_frame_ns = now_qpc_ns()

                seq += 1

            # 3. Emit SEALED END message
            ended_ns = now_qpc_ns()
            stream_sha = self._digest_calc.finalize_hex()
            last_seq = (self._current_sequence - 1) if self._current_sequence > 0 else None

            end_meta = {
                "schema": "whole-home-agent.capture-message.v1",
                "kind": "end",
                "capture_session_id": self.session_nonce,
                "source_id": self.source_id,
                "status": "SEALED",
                "last_source_sequence": last_seq,
                "frame_count": self._current_sequence - self._dropped_count,
                "dropped_frame_count": self._dropped_count,
                "ended_monotonic_ns": ended_ns,
                "stream_sha256": stream_sha,
                "failure_code": None,
            }
            end_record = pack_wire_message(KIND_END, end_meta)
            self._pipe_client.write(end_record)

            return {
                "status": "SEALED",
                "frames_captured": self._current_sequence - self._dropped_count,
                "dropped_frames": self._dropped_count,
                "stream_sha256": stream_sha,
                "duration_ns": ended_ns - started_monotonic_ns,
            }

        except Exception as ex:
            logger.error(f"Live camera capture encountered exception: {ex}")
            self._emit_failed_end("CAPTURE_INTERNAL_FAILED")
            raise
        finally:
            # Deterministic cleanup
            cap.release()
            if self._pipe_client:
                self._pipe_client.close()

    def _emit_failed_end(self, failure_code: str) -> None:
        """Emits an abort/failure END message if pipe is connected."""
        if self._pipe_client and self._pipe_client._handle:
            try:
                ended_ns = now_qpc_ns()
                last_seq = (self._current_sequence - 1) if self._current_sequence > 0 else None
                end_meta = {
                    "schema": "whole-home-agent.capture-message.v1",
                    "kind": "end",
                    "capture_session_id": self.session_nonce,
                    "source_id": self.source_id,
                    "status": "FAILED",
                    "last_source_sequence": last_seq,
                    "frame_count": self._current_sequence,
                    "dropped_frame_count": self._dropped_count,
                    "ended_monotonic_ns": ended_ns,
                    "stream_sha256": None,
                    "failure_code": failure_code,
                }
                end_record = pack_wire_message(KIND_END, end_meta)
                self._pipe_client.write(end_record)
            except Exception:
                pass
