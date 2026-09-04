"""Synthetic stream producer for pure Python contract testing (Stage R1).

Specification: WHA-WIN-CAPTURE-ROI-001 (Section 24, 26)
"""

from __future__ import annotations

import io
from typing import Mapping, Optional, Sequence

from .wire_protocol import (
    FRAME_BODY_BYTES,
    KIND_END,
    KIND_FRAME,
    KIND_GAP,
    KIND_START,
    StreamDigestCalculator,
    WirePrefix,
    dumps_canonical_json,
)


def create_synthetic_frame_bytes(sequence: int, pattern: str = "solid") -> bytes:
    """Generates deterministic 2,764,800 bytes of RGB24 data without camera dependencies."""
    if pattern == "solid":
        # Cycle through R, G, B channels based on sequence
        r = (sequence * 37) % 256
        g = (sequence * 73) % 256
        b = (sequence * 109) % 256
        pixel = bytes([r, g, b])
        return pixel * (1280 * 720)
    elif pattern == "black":
        return b"\x00" * FRAME_BODY_BYTES
    elif pattern == "white":
        return b"\xff" * FRAME_BODY_BYTES
    else:
        return bytes([sequence % 256]) * FRAME_BODY_BYTES


def pack_wire_message(
    kind_code: int,
    meta: Mapping[str, any],
    body: bytes = b"",
) -> bytes:
    """Encodes a single record with 16-byte fixed prefix, canonical JSON, and body."""
    meta_bytes = dumps_canonical_json(meta)
    prefix = WirePrefix(
        magic=b"WHA1",
        wire_version=1,
        message_kind=kind_code,
        flags=0,
        metadata_length=len(meta_bytes),
        body_length=len(body),
    )
    return prefix.pack() + meta_bytes + body


class SyntheticStreamBuilder:
    """Helper to assemble complete, valid or intentionally corrupted synthetic streams."""

    def __init__(
        self,
        *,
        session_id: str = "00000000-0000-4000-8000-000000000001",
        source_id: str = "synthetic-cam-01",
        capture_config_hash: str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        started_monotonic_ns: int = 1_000_000_000,
    ) -> None:
        self.session_id = session_id
        self.source_id = source_id
        self.capture_config_hash = capture_config_hash
        self.started_ns = started_monotonic_ns

        self.digest_calc = StreamDigestCalculator(
            capture_config_hash=capture_config_hash,
            started_monotonic_ns=started_monotonic_ns,
        )

        self._buf = io.BytesIO()
        self._current_sequence: int = 0
        self._frame_count: int = 0
        self._dropped_count: int = 0
        self._last_monotonic_ns: int = started_monotonic_ns

    def emit_start(self) -> SyntheticStreamBuilder:
        meta = {
            "schema": "whole-home-agent.capture-message.v1",
            "kind": "start",
            "capture_session_id": self.session_id,
            "source_id": self.source_id,
            "source_profile": "generated_stream_d0",
            "capture_config_hash": self.capture_config_hash,
            "width": 1280,
            "height": 720,
            "pixel_format": "rgb24",
            "target_fps_numerator": 10,
            "target_fps_denominator": 1,
            "started_monotonic_ns": self.started_ns,
            "activation_decision_id": None,
            "policy_version": None,
            "raw_retention": "none",
            "audio_enabled": False,
            "network_egress_enabled": False,
        }
        self._buf.write(pack_wire_message(KIND_START, meta))
        return self

    def emit_frame(
        self,
        *,
        sequence: Optional[int] = None,
        captured_ns: Optional[int] = None,
        pattern: str = "solid",
    ) -> SyntheticStreamBuilder:
        seq = self._current_sequence if sequence is None else sequence
        if captured_ns is None:
            c_ns = self.started_ns + (seq + 1) * 100_000_000
        else:
            c_ns = captured_ns

        body = create_synthetic_frame_bytes(seq, pattern=pattern)

        # Update digest
        self.digest_calc.update_frame(
            source_sequence=seq,
            captured_monotonic_ns=c_ns,
            rgb_bytes=body,
        )

        meta = {
            "schema": "whole-home-agent.capture-message.v1",
            "kind": "frame",
            "capture_session_id": self.session_id,
            "source_id": self.source_id,
            "source_sequence": seq,
            "captured_monotonic_ns": c_ns,
            "width": 1280,
            "height": 720,
            "pixel_format": "rgb24",
        }
        self._buf.write(pack_wire_message(KIND_FRAME, meta, body))
        self._current_sequence = seq + 1
        self._frame_count += 1
        self._last_monotonic_ns = c_ns
        return self

    def emit_gap(
        self,
        first_missing: int,
        last_missing: int,
        *,
        detected_ns: Optional[int] = None,
        reason: str = "capture_overrun",
    ) -> SyntheticStreamBuilder:
        if detected_ns is None:
            d_ns = self.started_ns + (last_missing + 1) * 100_000_000
        else:
            d_ns = detected_ns

        self.digest_calc.update_gap(
            first_missing_sequence=first_missing,
            last_missing_sequence=last_missing,
            detected_monotonic_ns=d_ns,
            reason=reason,
        )

        meta = {
            "schema": "whole-home-agent.capture-message.v1",
            "kind": "gap",
            "capture_session_id": self.session_id,
            "source_id": self.source_id,
            "first_missing_sequence": first_missing,
            "last_missing_sequence": last_missing,
            "detected_monotonic_ns": d_ns,
            "reason": reason,
        }
        self._buf.write(pack_wire_message(KIND_GAP, meta))
        count = last_missing - first_missing + 1
        self._current_sequence = last_missing + 1
        self._dropped_count += count
        self._last_monotonic_ns = d_ns
        return self

    def emit_sealed_end(self, *, ended_ns: Optional[int] = None) -> bytes:
        e_ns = self._last_monotonic_ns + 10_000_000 if ended_ns is None else ended_ns
        stream_hash = self.digest_calc.finalize_hex()
        last_seq = (self._current_sequence - 1) if self._current_sequence > 0 else None

        meta = {
            "schema": "whole-home-agent.capture-message.v1",
            "kind": "end",
            "capture_session_id": self.session_id,
            "source_id": self.source_id,
            "status": "SEALED",
            "last_source_sequence": last_seq,
            "frame_count": self._frame_count,
            "dropped_frame_count": self._dropped_count,
            "ended_monotonic_ns": e_ns,
            "stream_sha256": stream_hash,
            "failure_code": None,
        }
        self._buf.write(pack_wire_message(KIND_END, meta))
        return self._buf.getvalue()

    def emit_aborted_end(self, *, ended_ns: Optional[int] = None) -> bytes:
        e_ns = self._last_monotonic_ns + 10_000_000 if ended_ns is None else ended_ns
        last_seq = (self._current_sequence - 1) if self._current_sequence > 0 else None
        meta = {
            "schema": "whole-home-agent.capture-message.v1",
            "kind": "end",
            "capture_session_id": self.session_id,
            "source_id": self.source_id,
            "status": "ABORTED",
            "last_source_sequence": last_seq,
            "frame_count": self._frame_count,
            "dropped_frame_count": self._dropped_count,
            "ended_monotonic_ns": e_ns,
            "stream_sha256": None,
            "failure_code": "CAPTURE_CANCELLED",
        }
        self._buf.write(pack_wire_message(KIND_END, meta))
        return self._buf.getvalue()
