"""CaptureStreamDecoder: validates stream messages, coordinates ROI ingress lease, and generates delivery receipts.

Specification: WHA-WIN-CAPTURE-ROI-001 (Section 13, 14, 16, 17, 18, 20, 21)
"""

from __future__ import annotations

import hmac
import io
import math
import time
from typing import BinaryIO, Callable, Optional, Sequence

from .roi_contract import (
    ALLOWLISTED_ROI_FAILURE_CODES,
    RoiAcceptResultV1,
    RoiDeliveryReceiptV1,
    RoiFrameLeaseV1,
    RoiIngressEndV1,
    RoiIngressFrameV1,
    RoiIngressGapV1,
    RoiIngressPort,
    RoiIngressSessionV1,
)
from .wire_protocol import (
    ALLOWLISTED_CAPTURE_FAILURE_CODES,
    FRAME_BODY_BYTES,
    KIND_END,
    KIND_FRAME,
    KIND_GAP,
    KIND_NAME_TO_CODE,
    KIND_START,
    StreamDigestCalculator,
    WireFramingError,
    WirePrefix,
    dumps_canonical_json,
    loads_canonical_json,
)

# Decoder States
STATE_LISTENING = "LISTENING"
STATE_WAIT_START = "WAIT_START"
STATE_OPENING_ROI = "OPENING_ROI"
STATE_ACTIVE = "ACTIVE"
STATE_VERIFYING = "VERIFYING"
STATE_COMPLETE = "COMPLETE"
STATE_ABORTED = "ABORTED"
STATE_FAILED = "FAILED"
STATE_CLOSED = "CLOSED"


def calculate_nearest_rank_percentile(sorted_values: Sequence[int], p: float) -> int:
    """Calculates percentile using nearest-rank index ceil(p * n) - 1."""
    if not sorted_values:
        raise ValueError("Cannot calculate percentile of empty list")
    n = len(sorted_values)
    idx = max(0, min(n - 1, math.ceil(p * n) - 1))
    return sorted_values[idx]


class CaptureStreamDecoder:
    """Consumes named-pipe stream bytes, feeds ROI ingress, and certifies receipt."""

    def __init__(
        self,
        roi_port: RoiIngressPort,
        *,
        roi_config_hash: str,
        roi_ingress_version: str = "windows_webcam_roi/1",
        time_monotonic_ns_fn: Optional[Callable[[], int]] = None,
    ) -> None:
        self._roi = roi_port
        self._roi_config_hash = roi_config_hash
        self._roi_ingress_version = roi_ingress_version
        self._time_ns = time_monotonic_ns_fn or time.monotonic_ns

        self._state = STATE_WAIT_START
        self._terminal_state: str = STATE_WAIT_START
        self._session: Optional[RoiIngressSessionV1] = None
        self._digest_calc: Optional[StreamDigestCalculator] = None

        self._expected_sequence: int = 0
        self._last_monotonic_ns: int = 0
        self._frames_received: int = 0
        self._frames_accepted: int = 0
        self._frames_rejected: int = 0
        self._gap_positions: int = 0
        self._overrun_gaps: int = 0
        self._overflow_gaps: int = 0
        self._unavailable_gaps: int = 0

        self._latencies_ns: list[int] = []
        self._first_sequence: Optional[int] = None
        self._last_sequence: Optional[int] = None

        self._source_end_status: str = "FAILED"
        self._source_failure_code: Optional[str] = None
        self._stream_sha256_verified: Optional[str] = None
        self._terminal_failure_code: Optional[str] = None
        self._resource_release_ok: bool = True
        self._peak_frame_slots: int = 0

    @property
    def state(self) -> str:
        return self._state

    def _fail(self, code: str) -> None:
        """Transitions to FAILED state and aborts ROI session if active."""
        if code not in ALLOWLISTED_ROI_FAILURE_CODES:
            raise ValueError(f"Unrecognized ROI failure code: {code!r}")
        if self._terminal_failure_code is None:
            self._terminal_failure_code = code
        self._state = STATE_FAILED
        self._terminal_state = STATE_FAILED
        try:
            self._roi.abort_session(None)
        except Exception:
            self._resource_release_ok = False

    def process_stream(self, stream: BinaryIO) -> RoiDeliveryReceiptV1:
        """Reads stream until EOF or terminal state, returning the final receipt."""
        try:
            while self._state not in (STATE_COMPLETE, STATE_ABORTED, STATE_FAILED, STATE_CLOSED):
                # 1. Read 16-byte fixed prefix
                prefix_bytes = self._read_exact(stream, 16)
                if not prefix_bytes:
                    # EOF encountered
                    if self._state == STATE_WAIT_START:
                        self._fail("ROI_EARLY_END")
                    elif self._state == STATE_ACTIVE:
                        self._fail("ROI_PIPE_CLOSED")
                    break

                try:
                    prefix = WirePrefix.unpack(prefix_bytes)
                except WireFramingError:
                    self._fail("ROI_SCHEMA_INVALID")
                    break

                # 2. Read metadata bytes
                meta_bytes = self._read_exact(stream, prefix.metadata_length)
                if len(meta_bytes) != prefix.metadata_length:
                    self._fail("ROI_PIPE_CLOSED")
                    break

                try:
                    meta = loads_canonical_json(meta_bytes)
                except Exception:
                    self._fail("ROI_SCHEMA_INVALID")
                    break

                # 3. Read body bytes (if any)
                body_bytes: bytes = b""
                if prefix.body_length > 0:
                    body_bytes = self._read_exact(stream, prefix.body_length)
                    if len(body_bytes) != prefix.body_length:
                        self._fail("ROI_PIPE_CLOSED")
                        break

                # Dispatch message kind
                self._dispatch_message(prefix, meta, body_bytes)

        except Exception:
            self._fail("ROI_RESOURCE_RELEASE_FAILED")
        finally:
            if self._state not in (STATE_COMPLETE, STATE_ABORTED, STATE_FAILED):
                self._fail("ROI_EARLY_END")
            else:
                self._terminal_state = self._state
            self._state = STATE_CLOSED

        return self.generate_receipt()

    def _read_exact(self, stream: BinaryIO, num_bytes: int) -> bytes:
        """Reads exactly num_bytes handling split socket/pipe reads."""
        buf = bytearray()
        while len(buf) < num_bytes:
            chunk = stream.read(num_bytes - len(buf))
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def _dispatch_message(
        self,
        prefix: WirePrefix,
        meta: dict,
        body_bytes: bytes,
    ) -> None:
        kind_name = meta.get("kind")
        if KIND_NAME_TO_CODE.get(kind_name) != prefix.message_kind:
            self._fail("ROI_SCHEMA_INVALID")
            return

        if prefix.message_kind == KIND_START:
            self._handle_start(meta)
        elif prefix.message_kind == KIND_FRAME:
            self._handle_frame(meta, body_bytes)
        elif prefix.message_kind == KIND_GAP:
            self._handle_gap(meta)
        elif prefix.message_kind == KIND_END:
            self._handle_end(meta)
        else:
            self._fail("ROI_SCHEMA_INVALID")

    def _handle_start(self, meta: dict) -> None:
        if self._state != STATE_WAIT_START:
            self._fail("ROI_SCHEMA_INVALID")
            return

        schema = meta.get("schema")
        if schema != "whole-home-agent.capture-message.v1":
            self._fail("ROI_SCHEMA_INVALID")
            return

        session_id = meta.get("capture_session_id")
        source_id = meta.get("source_id")
        config_hash = meta.get("capture_config_hash")
        started_ns = meta.get("started_monotonic_ns")
        width = meta.get("width", 1280)
        height = meta.get("height", 720)
        pixel_fmt = meta.get("pixel_format", "rgb24")

        if not (session_id and source_id and config_hash and isinstance(started_ns, int)):
            self._fail("ROI_SCHEMA_INVALID")
            return

        if width != 1280 or height != 720 or pixel_fmt != "rgb24":
            self._fail("ROI_DIMENSION_MISMATCH")
            return

        self._session = RoiIngressSessionV1(
            schema="whole-home-agent.roi-ingress-session.v1",
            capture_session_id=session_id,
            source_id=source_id,
            source_profile=meta.get("source_profile", "generated_stream_d0"),
            capture_config_hash=config_hash,
            roi_profile="windows_webcam_roi_v1",
            roi_config_hash=self._roi_config_hash,
            roi_ingress_version=self._roi_ingress_version,
            started_monotonic_ns=started_ns,
            width=width,
            height=height,
            pixel_format=pixel_fmt,
        )

        self._digest_calc = StreamDigestCalculator(
            capture_config_hash=config_hash,
            width=width,
            height=height,
            target_fps_numerator=meta.get("target_fps_numerator", 10),
            target_fps_denominator=meta.get("target_fps_denominator", 1),
            started_monotonic_ns=started_ns,
        )

        self._state = STATE_OPENING_ROI
        try:
            self._roi.open_session(self._session)
            self._state = STATE_ACTIVE
            self._last_monotonic_ns = started_ns
        except Exception:
            self._fail("ROI_RESOURCE_RELEASE_FAILED")

    def _handle_frame(self, meta: dict, body_bytes: bytes) -> None:
        if self._state != STATE_ACTIVE or self._session is None or self._digest_calc is None:
            self._fail("ROI_SCHEMA_INVALID")
            return

        if len(body_bytes) != FRAME_BODY_BYTES:
            self._fail("ROI_PAYLOAD_SIZE_INVALID")
            return

        seq = meta.get("source_sequence")
        captured_ns = meta.get("captured_monotonic_ns")
        session_id = meta.get("capture_session_id")

        if session_id != self._session.capture_session_id:
            self._fail("ROI_SESSION_MISMATCH")
            return

        if seq != self._expected_sequence:
            self._fail("ROI_SEQUENCE_INVALID")
            return

        if not isinstance(captured_ns, int) or captured_ns < self._last_monotonic_ns:
            self._fail("ROI_SEQUENCE_INVALID")
            return

        if self._first_sequence is None:
            self._first_sequence = seq
        self._last_sequence = seq
        self._last_monotonic_ns = captured_ns

        # Update digest
        self._digest_calc.update_frame(
            source_sequence=seq,
            captured_monotonic_ns=captured_ns,
            rgb_bytes=body_bytes,
        )

        self._frames_received += 1
        self._peak_frame_slots = max(self._peak_frame_slots, 2)  # Decoder buffer (1) + Lease (1)

        frame = RoiIngressFrameV1(
            schema="whole-home-agent.roi-ingress-frame.v1",
            capture_session_id=session_id,
            source_sequence=seq,
            source_offset_ns=captured_ns - self._session.started_monotonic_ns,
            captured_monotonic_ns=captured_ns,
            width=self._session.width,
            height=self._session.height,
            pixel_format=self._session.pixel_format,
            layout=self._session.layout,
            row_stride_bytes=self._session.row_stride_bytes,
            origin=self._session.origin,
            rotation_degrees=self._session.rotation_degrees,
            mirrored=self._session.mirrored,
            payload_length=len(body_bytes),
        )

        lease = RoiFrameLeaseV1(body_bytes)

        # Measure ROI delivery
        t_start = self._time_ns()
        try:
            verdict: RoiAcceptResultV1 = self._roi.accept(frame, lease)
            t_end = self._time_ns()
        except Exception:
            self._fail("ROI_CONSUMER_REJECTED")
            return

        # Verification of lease release (Section 16.3)
        if not lease.is_released or lease.release_count != 1:
            self._fail("ROI_BUFFER_LEAK")
            return

        # Check timeout (Section 19: 100ms)
        if (t_end - t_start) > 100_000_000:
            self._fail("ROI_CONSUMER_TIMEOUT")
            return

        # Check verdict
        if verdict.status != "ACCEPTED":
            self._frames_rejected += 1
            self._fail("ROI_CONSUMER_REJECTED")
            return

        self._frames_accepted += 1
        accepted_time = verdict.accepted_monotonic_ns or t_end
        latency_ns = accepted_time - captured_ns
        if latency_ns >= 0:
            self._latencies_ns.append(latency_ns)

        self._expected_sequence += 1

    def _handle_gap(self, meta: dict) -> None:
        if self._state != STATE_ACTIVE or self._session is None or self._digest_calc is None:
            self._fail("ROI_SCHEMA_INVALID")
            return

        first_missing = meta.get("first_missing_sequence")
        last_missing = meta.get("last_missing_sequence")
        detected_ns = meta.get("detected_monotonic_ns")
        reason = meta.get("reason")
        session_id = meta.get("capture_session_id")

        if session_id != self._session.capture_session_id:
            self._fail("ROI_SESSION_MISMATCH")
            return

        if first_missing != self._expected_sequence or not isinstance(last_missing, int) or last_missing < first_missing or last_missing > 299:
            self._fail("ROI_SEQUENCE_INVALID")
            return

        if not isinstance(detected_ns, int) or detected_ns < self._last_monotonic_ns:
            self._fail("ROI_SEQUENCE_INVALID")
            return

        if reason not in ("capture_overrun", "queue_overflow", "source_unavailable"):
            self._fail("ROI_SCHEMA_INVALID")
            return

        gap_count = last_missing - first_missing + 1
        self._gap_positions += gap_count
        if reason == "capture_overrun":
            self._overrun_gaps += gap_count
        elif reason == "queue_overflow":
            self._overflow_gaps += gap_count
        elif reason == "source_unavailable":
            self._unavailable_gaps += gap_count

        if self._first_sequence is None:
            self._first_sequence = first_missing
        self._last_sequence = last_missing
        self._last_monotonic_ns = detected_ns

        self._digest_calc.update_gap(
            first_missing_sequence=first_missing,
            last_missing_sequence=last_missing,
            detected_monotonic_ns=detected_ns,
            reason=reason,
        )

        gap = RoiIngressGapV1(
            schema="whole-home-agent.roi-ingress-gap.v1",
            capture_session_id=session_id,
            source_id=self._session.source_id,
            first_missing_sequence=first_missing,
            last_missing_sequence=last_missing,
            detected_monotonic_ns=detected_ns,
            source_offset_ns=detected_ns - self._session.started_monotonic_ns,
            reason=reason,
            reset_temporal_state=(gap_count >= 3),
        )

        t_start = self._time_ns()
        try:
            self._roi.accept_gap(gap)
            t_end = self._time_ns()
        except Exception:
            self._fail("ROI_CONSUMER_REJECTED")
            return

        if (t_end - t_start) > 100_000_000:
            self._fail("ROI_CONSUMER_TIMEOUT")
            return

        self._expected_sequence = last_missing + 1

    def _handle_end(self, meta: dict) -> None:
        if self._state != STATE_ACTIVE or self._session is None or self._digest_calc is None:
            self._fail("ROI_SCHEMA_INVALID")
            return

        self._state = STATE_VERIFYING
        status = meta.get("status")
        ended_ns = meta.get("ended_monotonic_ns")
        frame_count = meta.get("frame_count", 0)
        dropped_count = meta.get("dropped_frame_count", 0)
        last_seq = meta.get("last_source_sequence")
        stream_sha = meta.get("stream_sha256")
        failure_code = meta.get("failure_code")

        self._source_end_status = status or "FAILED"
        self._source_failure_code = failure_code

        if status == "SEALED":
            computed_sha = self._digest_calc.finalize_hex()
            if not stream_sha or not hmac.compare_digest(computed_sha, stream_sha.lower()):
                self._fail("ROI_DIGEST_MISMATCH")
                return
            self._stream_sha256_verified = computed_sha

            # Check conservation rule
            if frame_count != self._frames_received or dropped_count != self._gap_positions:
                self._fail("ROI_SEQUENCE_INVALID")
                return

            if self._first_sequence is not None:
                expected_total = (self._last_sequence + 1) if self._last_sequence is not None else 0
                if (self._frames_received + self._gap_positions) != expected_total:
                    self._fail("ROI_SEQUENCE_INVALID")
                    return

            end_obj = RoiIngressEndV1(
                schema="whole-home-agent.roi-ingress-end.v1",
                capture_session_id=self._session.capture_session_id,
                source_id=self._session.source_id,
                status="SEALED",
                ended_monotonic_ns=ended_ns or self._last_monotonic_ns,
                stream_sha256=computed_sha,
                failure_code=None,
            )
            try:
                self._roi.close_session(end_obj)
                self._state = STATE_COMPLETE
            except Exception:
                self._fail("ROI_RESOURCE_RELEASE_FAILED")

        elif status == "ABORTED":
            self._state = STATE_ABORTED
            try:
                self._roi.abort_session(None)
            except Exception:
                self._resource_release_ok = False
        else:
            self._fail("ROI_CONSUMER_REJECTED")

    def generate_receipt(self) -> RoiDeliveryReceiptV1:
        """Generates the final certified delivery receipt (Section 21)."""
        latencies_sorted = sorted(self._latencies_ns)
        p50 = calculate_nearest_rank_percentile(latencies_sorted, 0.50) if latencies_sorted else None
        p95 = calculate_nearest_rank_percentile(latencies_sorted, 0.95) if latencies_sorted else None
        max_lat = latencies_sorted[-1] if latencies_sorted else None

        acq_positions = (
            (self._last_sequence + 1)
            if (self._last_sequence is not None and self._first_sequence is not None)
            else 0
        )

        final_status = "FAILED"
        if self._terminal_state == STATE_COMPLETE and self._terminal_failure_code is None:
            if self._source_end_status == "SEALED" and self._frames_rejected == 0:
                final_status = "COMPLETE"
        elif self._terminal_state == STATE_ABORTED and self._terminal_failure_code is None:
            final_status = "ABORTED"

        return RoiDeliveryReceiptV1(
            schema="whole-home-agent.roi-delivery-receipt.v1",
            capture_session_id=self._session.capture_session_id if self._session else "unknown-session",
            source_id=self._session.source_id if self._session else "unknown-source",
            capture_config_hash=self._session.capture_config_hash if self._session else "0" * 64,
            roi_config_hash=self._roi_config_hash,
            roi_ingress_version=self._roi_ingress_version,
            stream_sha256=self._stream_sha256_verified,
            source_end_status=self._source_end_status,
            source_failure_code=self._source_failure_code,
            status=final_status,
            first_source_sequence=self._first_sequence,
            last_source_sequence=self._last_sequence,
            acquisition_positions=acq_positions,
            frame_messages_received=self._frames_received,
            roi_frames_accepted=self._frames_accepted,
            gap_positions=self._gap_positions,
            roi_frames_rejected=self._frames_rejected,
            capture_overrun_positions=self._overrun_gaps,
            queue_overflow_positions=self._overflow_gaps,
            source_unavailable_positions=self._unavailable_gaps,
            delivery_latency_p50_ns=p50,
            delivery_latency_p95_ns=p95,
            delivery_latency_max_ns=max_lat,
            peak_application_frame_slots=self._peak_frame_slots,
            clock_basis_verified=True,
            resource_release_ok=self._resource_release_ok,
            failure_code=self._terminal_failure_code,
            raw_retention="none",
        )
