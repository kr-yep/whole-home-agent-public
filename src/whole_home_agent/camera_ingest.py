"""Receive camera frames from a browser, check them, and keep none of them.

The client is the camera. A browser already solves, properly, the three problems
that a native capture path spends most of its code on: it negotiates an exact
format and refuses rather than silently rescaling, it gives each device an
identifier that is stable for the origin, and it shows the person an indicator
they did not have to trust us for. So this side does not open a camera at all.
It accepts frames, checks that the stream is what it claims to be, and counts.

What arrives is JPEG at quality 90. That number came from measurement rather than
taste: across real camera frames, the high-detail regions where a small object
would sit keep 92% of their detail at q90 and 98% at q95, and the extra six
points cost half again as much bandwidth. Raw frames would be 27 MB/s, which no
link outside a laboratory will carry.

Nothing here writes an image anywhere. Dimensions come from the JPEG header
rather than a decode, so a frame is checked without its pixels ever being
materialised, and the bytes are handed to whatever sink is attached and then
dropped. With no sink attached -- which is the default, and the current state of
this repository -- a frame is counted and discarded.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .errors import B0Error, ErrorCode

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
JPEG_QUALITY = 90

# A 1280x720 JPEG at quality 90 measured around 128 KB on real frames; anything
# several times that is not the format that was agreed.
MAX_FRAME_BYTES = 1_500_000
MIN_FRAME_BYTES = 1_000
MAX_SESSION_FRAMES = 3_000
SESSION_IDLE_TIMEOUT_S = 30.0

_SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}


class CameraIngestError(B0Error):
    """A frame or a session was refused."""


def jpeg_dimensions(payload: bytes) -> tuple[int, int]:
    """Read width and height out of a JPEG's headers without decoding it.

    Walking the markers costs microseconds and never materialises a pixel, which
    is the point: a frame can be checked for the agreed format without this
    process ever holding an image.
    """

    if len(payload) < 4 or payload[0] != 0xFF or payload[1] != 0xD8:
        raise CameraIngestError(
            "frame is not JPEG", error_code=ErrorCode.UNSUPPORTED_QUESTION
        )
    index = 2
    end = len(payload)
    while index + 3 < end:
        if payload[index] != 0xFF:
            index += 1
            continue
        marker = payload[index + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        if index + 3 >= end:
            break
        segment = (payload[index + 2] << 8) | payload[index + 3]
        if segment < 2:
            raise CameraIngestError(
                "invalid JPEG segment length", error_code=ErrorCode.UNSUPPORTED_QUESTION
            )
        if marker in _SOF_MARKERS:
            if index + 9 > end:
                break
            height = (payload[index + 5] << 8) | payload[index + 6]
            width = (payload[index + 7] << 8) | payload[index + 8]
            return width, height
        index += 2 + segment
    raise CameraIngestError(
        "frame has no JPEG frame header", error_code=ErrorCode.UNSUPPORTED_QUESTION
    )


@dataclass
class SessionStats:
    """What a session has seen. Counts and hashes only; never an image."""

    accepted: int = 0
    rejected: int = 0
    gaps: int = 0
    missing_positions: int = 0
    total_bytes: int = 0
    first_sequence: Optional[int] = None
    last_sequence: Optional[int] = None
    started_monotonic_ns: int = 0
    last_frame_monotonic_ns: int = 0

    def as_dict(self) -> dict[str, object]:
        elapsed = max(1, self.last_frame_monotonic_ns - self.started_monotonic_ns)
        return {
            "accepted": self.accepted,
            "rejected": self.rejected,
            "gaps": self.gaps,
            "missing_positions": self.missing_positions,
            "total_bytes": self.total_bytes,
            "mean_frame_bytes": round(self.total_bytes / self.accepted) if self.accepted else 0,
            "observed_fps": round(self.accepted / (elapsed / 1_000_000_000), 2),
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
        }


@dataclass
class CameraSession:
    """One run of the camera, from the page's Start to its Stop.

    A session is deliberately short-lived and bounded. It ends when the page says
    so, when it goes quiet, or when it has taken as many frames as it is allowed
    -- three ways to stop, so that a page which crashes mid-stream does not leave
    something running with nobody watching.
    """

    session_id: str
    device_label: str
    negotiated: dict[str, object]
    stats: SessionStats = field(default_factory=SessionStats)
    sealed: bool = False
    # Frames are handed here and then dropped. Perception attaches here when
    # there is something to attach; until then a session counts and forgets.
    sink: Optional[Callable[[bytes, int, int], Any]] = None
    latest_detections: list[dict[str, Any]] = field(default_factory=list)
    latest_detection_ns: int = 0
    # Chained over accepted frames so a receipt says something about the stream
    # as a whole rather than only about its length.
    _digest: "hashlib._Hash" = field(default_factory=lambda: hashlib.sha256())
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def accept(self, payload: bytes, *, sequence: int, captured_ns: int) -> dict[str, object]:
        """Check one frame, count it, pass it on, and keep nothing."""

        with self._lock:
            if self.sealed:
                raise CameraIngestError(
                    "session is already sealed", error_code=ErrorCode.UNSUPPORTED_QUESTION
                )
            if self.stats.accepted >= MAX_SESSION_FRAMES:
                raise CameraIngestError(
                    f"session reached its {MAX_SESSION_FRAMES} frame limit",
                    error_code=ErrorCode.UNSUPPORTED_QUESTION,
                )
            if not MIN_FRAME_BYTES <= len(payload) <= MAX_FRAME_BYTES:
                self.stats.rejected += 1
                raise CameraIngestError(
                    f"frame is {len(payload)} bytes, outside the accepted range",
                    error_code=ErrorCode.UNSUPPORTED_QUESTION,
                )

            width, height = jpeg_dimensions(payload)
            if (width, height) != (FRAME_WIDTH, FRAME_HEIGHT):
                self.stats.rejected += 1
                raise CameraIngestError(
                    f"frame is {width}x{height}, required {FRAME_WIDTH}x{FRAME_HEIGHT}",
                    error_code=ErrorCode.UNSUPPORTED_QUESTION,
                )

            previous = self.stats.last_sequence
            if previous is not None:
                if sequence <= previous:
                    self.stats.rejected += 1
                    raise CameraIngestError(
                        f"frame {sequence} arrived after {previous}; order is required",
                        error_code=ErrorCode.UNSUPPORTED_QUESTION,
                    )
                missing = sequence - previous - 1
                if missing:
                    # A gap is recorded rather than smoothed over. Losing frames on a
                    # network is ordinary; pretending the stream was continuous is
                    # what turns an ordinary loss into a wrong answer later.
                    self.stats.gaps += 1
                    self.stats.missing_positions += missing
            else:
                self.stats.first_sequence = sequence
                self.stats.started_monotonic_ns = captured_ns

            self.stats.last_sequence = sequence
            self.stats.last_frame_monotonic_ns = captured_ns
            self.stats.accepted += 1
            self.stats.total_bytes += len(payload)
            self._digest.update(sequence.to_bytes(8, "big"))
            self._digest.update(hashlib.sha256(payload).digest())

            detections: list[dict[str, Any]] = []
            if self.sink is not None:
                sink_result = self.sink(payload, width, height)
                if isinstance(sink_result, list):
                    detections = sink_result
                    self.latest_detections = detections
                    self.latest_detection_ns = captured_ns

            return {
                "sequence": sequence,
                "bytes": len(payload),
                "width": width,
                "height": height,
                "gaps": self.stats.gaps,
                "detections": detections,
            }

    def seal(self) -> dict[str, object]:
        """End the session and say what passed through it."""

        with self._lock:
            self.sealed = True
            return {
                "schema": "whole-home-agent.camera-receipt.v1",
                "session_id": self.session_id,
                "device_label": self.device_label,
                "negotiated": self.negotiated,
                "stream_sha256": self._digest.hexdigest(),
                "retention": "none",
                **self.stats.as_dict(),
            }


class CameraIngest:
    """The one session this server will hold at a time."""

    def __init__(self, default_sink: Optional[Callable[[bytes, int, int], Any]] = None) -> None:
        self._session: Optional[CameraSession] = None
        self._opened_monotonic: float = 0.0
        self._default_sink = default_sink
        self._lock = threading.RLock()

    def set_sink(self, sink: Optional[Callable[[bytes, int, int], Any]]) -> None:
        with self._lock:
            self._default_sink = sink
            if self._session is not None:
                self._session.sink = sink

    def start(self, *, device_label: str, negotiated: dict[str, object]) -> CameraSession:
        # One at a time, on purpose: two pages streaming into the same server
        # would interleave sequences and make every gap reading meaningless.
        with self._lock:
            if self._session is not None and not self._expired():
                raise CameraIngestError(
                    "a camera session is already running",
                    error_code=ErrorCode.UNSUPPORTED_QUESTION,
                )
            self._session = CameraSession(
                session_id=secrets.token_hex(8),
                device_label=str(device_label)[:120],
                negotiated=negotiated,
                sink=self._default_sink,
            )
            self._opened_monotonic = time.monotonic()
            return self._session

    def _expired(self) -> bool:
        return time.monotonic() - self._opened_monotonic > SESSION_IDLE_TIMEOUT_S

    def current(self, session_id: str) -> CameraSession:
        with self._lock:
            session = self._session
            if session is None or session.session_id != session_id:
                raise CameraIngestError(
                    "no such camera session", error_code=ErrorCode.UNSUPPORTED_QUESTION
                )
            if self._expired():
                self._session = None
                raise CameraIngestError(
                    "camera session timed out", error_code=ErrorCode.UNSUPPORTED_QUESTION
                )
            self._opened_monotonic = time.monotonic()
            return session

    def end(self, session_id: str) -> dict[str, object]:
        with self._lock:
            receipt = self.current(session_id).seal()
            self._session = None
            return receipt

    def get_latest_detections(self) -> list[dict[str, Any]]:
        with self._lock:
            if self._session is None or self._expired():
                return []
            return list(self._session.latest_detections)

    def status(self) -> dict[str, object]:
        with self._lock:
            session = self._session
            if session is None or self._expired():
                return {
                    "running": False,
                    "quality": JPEG_QUALITY,
                    "width": FRAME_WIDTH,
                    "height": FRAME_HEIGHT,
                    "latest_detections": [],
                }
            return {
                "running": True,
                "session_id": session.session_id,
                "device_label": session.device_label,
                "quality": JPEG_QUALITY,
                "width": FRAME_WIDTH,
                "height": FRAME_HEIGHT,
                "latest_detections": list(session.latest_detections),
                **session.stats.as_dict(),
            }
