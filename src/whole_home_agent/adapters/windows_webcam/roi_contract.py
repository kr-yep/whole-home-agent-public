"""ROI Ingress interface, immutable types, lease, and delivery receipt.

Specification: WHA-WIN-CAPTURE-ROI-001 (Section 16, 20, 21)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

ALLOWLISTED_ROI_FAILURE_CODES = frozenset({
    "ROI_SCHEMA_INVALID",
    "ROI_SESSION_MISMATCH",
    "ROI_SEQUENCE_INVALID",
    "ROI_DIMENSION_MISMATCH",
    "ROI_PIXEL_FORMAT_INVALID",
    "ROI_LAYOUT_INVALID",
    "ROI_PAYLOAD_SIZE_INVALID",
    "ROI_QUEUE_FULL",
    "ROI_CONSUMER_TIMEOUT",
    "ROI_CONSUMER_REJECTED",
    "ROI_BUFFER_LEAK",
    "ROI_DIGEST_MISMATCH",
    "ROI_PIPE_CLOSED",
    "ROI_EARLY_END",
    "ROI_RESOURCE_RELEASE_FAILED",
})

ALLOWLISTED_ROI_REJECTION_CODES = frozenset({
    "ROI_REJECT_CAPACITY",
    "ROI_REJECT_UNAVAILABLE",
    "ROI_REJECT_INTERNAL",
})

ALLOWLISTED_LAUNCH_FAILURE_CODES = frozenset({
    "LAUNCH_CAMERA_EXCLUSIVE_CONTROL_UNAVAILABLE",
    "LAUNCH_CAMERA_FORMAT_NOT_FOUND",
    "LAUNCH_CAMERA_FORMAT_AMBIGUOUS",
    "LAUNCH_CAMERA_FORMAT_SET_FAILED",
    "LAUNCH_CAMERA_FORMAT_VERIFY_FAILED",
})


@dataclass(frozen=True, slots=True)
class RoiIngressSessionV1:
    """Represents an established session at the ROI ingress (Section 16.1)."""
    schema: str
    capture_session_id: str
    source_id: str
    source_profile: str
    capture_config_hash: str
    roi_profile: str
    roi_config_hash: str
    roi_ingress_version: str
    started_monotonic_ns: int
    width: int = 1280
    height: int = 720
    pixel_format: str = "rgb24"
    layout: str = "HWC_CONTIGUOUS"
    row_stride_bytes: int = 3840
    origin: str = "top_left"
    x_axis: str = "right"
    y_axis: str = "down"
    rotation_degrees: int = 0
    mirrored: bool = False
    color_interpretation: str = "srgb"
    target_fps_numerator: int = 10
    target_fps_denominator: int = 1
    max_positions: int = 300
    max_gap_frames: int = 2
    raw_retention: str = "none"


@dataclass(frozen=True, slots=True)
class RoiIngressFrameV1:
    """Metadata descriptor for a single full frame delivered to ROI (Section 16.2)."""
    schema: str
    capture_session_id: str
    source_sequence: int
    source_offset_ns: int
    captured_monotonic_ns: int
    width: int = 1280
    height: int = 720
    pixel_format: str = "rgb24"
    layout: str = "HWC_CONTIGUOUS"
    row_stride_bytes: int = 3840
    origin: str = "top_left"
    rotation_degrees: int = 0
    mirrored: bool = False
    payload_length: int = 2764800

    def __repr__(self) -> str:
        # Guarantee raw pixels never leak into repr output (Section 16.2)
        return (
            f"RoiIngressFrameV1(seq={self.source_sequence}, "
            f"captured_ns={self.captured_monotonic_ns}, "
            f"shape=({self.height},{self.width},3), "
            f"payload_bytes={self.payload_length})"
        )


class RoiFrameLeaseV1:
    """Provides a single-use synchronous read-only view of pixel memory (Section 16.3)."""

    def __init__(self, buffer: bytearray | bytes | memoryview) -> None:
        if len(buffer) != 2764800:
            raise ValueError(f"Lease buffer must be exactly 2,764,800 bytes, got {len(buffer)}")
        # Store read-only view
        self._view = memoryview(buffer).toreadonly()
        self._released: bool = False
        self._release_count: int = 0

    @property
    def is_released(self) -> bool:
        return self._released

    @property
    def release_count(self) -> int:
        return self._release_count

    @property
    def pixel_memory_view(self) -> memoryview:
        if self._released:
            raise BufferError("Cannot access pixel_memory_view after lease has been released")
        return self._view

    def release(self) -> None:
        """Release the read-only lease. Must be called exactly once."""
        if self._released:
            self._release_count += 1
            raise ValueError("RoiFrameLeaseV1 has already been released (double release)")
        self._released = True
        self._release_count = 1
        # Release underlying memoryview handle
        self._view.release()


@dataclass(frozen=True, slots=True)
class RoiIngressGapV1:
    """Represents a range of missing positions at the ROI ingress (Section 16.4)."""
    schema: str
    capture_session_id: str
    source_id: str
    first_missing_sequence: int
    last_missing_sequence: int
    detected_monotonic_ns: int
    source_offset_ns: int
    reason: str
    reset_temporal_state: bool


@dataclass(frozen=True, slots=True)
class RoiIngressEndV1:
    """Represents the termination of a session at the ROI ingress."""
    schema: str
    capture_session_id: str
    source_id: str
    status: str
    ended_monotonic_ns: int
    stream_sha256: str | None
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class RoiAcceptResultV1:
    """Verdict returned by ROI ingress accept() call (Section 16.5)."""
    schema: str
    capture_session_id: str
    source_sequence: int
    status: str  # "ACCEPTED" or "REJECTED"
    reason_code: str | None
    accepted_monotonic_ns: int | None
    roi_ingress_version: str
    roi_config_hash: str


@dataclass(frozen=True, slots=True)
class RoiDeliveryReceiptV1:
    """Final delivery receipt generated at session end (Section 21)."""
    schema: str
    capture_session_id: str
    source_id: str
    capture_config_hash: str
    roi_config_hash: str
    roi_ingress_version: str
    stream_sha256: str | None
    source_end_status: str
    source_failure_code: str | None
    status: str  # "COMPLETE", "ABORTED", or "FAILED"
    first_source_sequence: int | None
    last_source_sequence: int | None
    acquisition_positions: int
    frame_messages_received: int
    roi_frames_accepted: int
    gap_positions: int
    roi_frames_rejected: int
    capture_overrun_positions: int
    queue_overflow_positions: int
    source_unavailable_positions: int
    delivery_latency_p50_ns: int | None
    delivery_latency_p95_ns: int | None
    delivery_latency_max_ns: int | None
    peak_application_frame_slots: int
    clock_basis_verified: bool
    resource_release_ok: bool
    failure_code: str | None
    raw_retention: str = "none"


@runtime_checkable
class RoiIngressPort(Protocol):
    """Downstream consumer interface boundary (Section 16)."""

    def open_session(self, session: RoiIngressSessionV1) -> None:
        """Initialize session at ROI ingress."""
        ...

    def accept(self, frame: RoiIngressFrameV1, lease: RoiFrameLeaseV1) -> RoiAcceptResultV1:
        """Synchronous frame delivery. Lease must be released before returning."""
        ...

    def accept_gap(self, gap: RoiIngressGapV1) -> None:
        """Accept notice of dropped or missing positions."""
        ...

    def close_session(self, end: RoiIngressEndV1) -> None:
        """Called exactly once upon normal SEALED completion."""
        ...

    def abort_session(self, end: RoiIngressEndV1 | None) -> None:
        """Called upon abnormal session failure or abort. Must be idempotent."""
        ...
