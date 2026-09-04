"""CaptureMessageV1 wire framing, serialization, and stream digest.

Specification: WHA-WIN-CAPTURE-ROI-001 (whole-home-agent.capture-message.v1)
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

WIRE_MAGIC = b"WHA1"
WIRE_VERSION = 1

KIND_START = 1
KIND_FRAME = 2
KIND_GAP = 3
KIND_END = 4

KIND_NAME_TO_CODE: Mapping[str, int] = {
    "start": KIND_START,
    "frame": KIND_FRAME,
    "gap": KIND_GAP,
    "end": KIND_END,
}

KIND_CODE_TO_NAME: Mapping[int, str] = {v: k for k, v in KIND_NAME_TO_CODE.items()}

FIXED_PREFIX_BYTES = 16
MIN_METADATA_BYTES = 2
MAX_METADATA_BYTES = 8192
FRAME_BODY_BYTES = 2764800  # 1280 * 720 * 3
CANONICAL_SCHEMA = "whole-home-agent.capture-message.v1"

REASON_CODES: Mapping[str, int] = {
    "capture_overrun": 0x01,
    "queue_overflow": 0x02,
    "source_unavailable": 0x03,
}
REASON_CODE_TO_NAME: Mapping[int, str] = {v: k for k, v in REASON_CODES.items()}

ALLOWLISTED_CAPTURE_FAILURE_CODES = frozenset({
    "CAPTURE_CANCELLED",
    "CAPTURE_PIPE_FAILED",
    "CAPTURE_DEVICE_LOST",
    "CAPTURE_FORMAT_CHANGED",
    "CAPTURE_TIMEOUT",
    "CAPTURE_RESOURCE_RELEASE_FAILED",
    "CAPTURE_INTERNAL_FAILED",
})


class WireFramingError(ValueError):
    """Raised when wire framing or binary decoding invariants are violated."""


class CanonicalJsonError(ValueError):
    """Raised when canonical JSON validation or re-encoding checks fail."""


@dataclass(frozen=True, slots=True)
class WirePrefix:
    """16-byte fixed prefix preceding every record on the named pipe."""
    magic: bytes
    wire_version: int
    message_kind: int
    flags: int
    metadata_length: int
    body_length: int

    def pack(self) -> bytes:
        return struct.pack(
            ">4sBBHII",
            self.magic,
            self.wire_version,
            self.message_kind,
            self.flags,
            self.metadata_length,
            self.body_length,
        )

    @classmethod
    def unpack(cls, raw: bytes) -> WirePrefix:
        if len(raw) != FIXED_PREFIX_BYTES:
            raise WireFramingError(
                f"Prefix must be exactly {FIXED_PREFIX_BYTES} bytes, got {len(raw)}"
            )
        magic, version, kind, flags, meta_len, body_len = struct.unpack(">4sBBHII", raw)
        if magic != WIRE_MAGIC:
            raise WireFramingError(f"Invalid magic: {magic!r}, expected {WIRE_MAGIC!r}")
        if version != WIRE_VERSION:
            raise WireFramingError(
                f"Unsupported wire version {version}, expected {WIRE_VERSION}"
            )
        if kind not in KIND_CODE_TO_NAME:
            raise WireFramingError(f"Unknown message kind code: {kind}")
        if flags != 0:
            raise WireFramingError(f"Reserved flags must be 0, got {flags}")
        if not (MIN_METADATA_BYTES <= meta_len <= MAX_METADATA_BYTES):
            raise WireFramingError(
                f"Metadata length {meta_len} out of allowed bounds [{MIN_METADATA_BYTES}, {MAX_METADATA_BYTES}]"
            )
        expected_body = FRAME_BODY_BYTES if kind == KIND_FRAME else 0
        if body_len != expected_body:
            raise WireFramingError(
                f"Body length {body_len} invalid for kind {KIND_CODE_TO_NAME[kind]}, expected {expected_body}"
            )
        return cls(
            magic=magic,
            wire_version=version,
            message_kind=kind,
            flags=flags,
            metadata_length=meta_len,
            body_length=body_len,
        )


def _check_no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    res: dict[str, Any] = {}
    for k, v in pairs:
        if k in res:
            raise CanonicalJsonError(f"Duplicate JSON key detected: {k!r}")
        res[k] = v
    return res


def dumps_canonical_json(obj: Mapping[str, Any]) -> bytes:
    """Serializes metadata to canonical UTF-8 JSON bytes (Section 13.2)."""
    # Strict validation of values: no floats allowed in capture metadata
    def validate_node(node: Any) -> None:
        if isinstance(node, float):
            raise CanonicalJsonError("Floating-point numbers are prohibited in metadata")
        if isinstance(node, dict):
            for k, v in node.items():
                if not isinstance(k, str):
                    raise CanonicalJsonError(f"Dictionary key must be str, got {type(k).__name__}")
                validate_node(v)
        elif isinstance(node, (list, tuple)):
            for elem in node:
                validate_node(elem)

    validate_node(obj)
    raw = json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return raw


def loads_canonical_json(raw: bytes) -> dict[str, Any]:
    """Parses and strictly verifies canonical JSON bytes under round-trip equality."""
    if not isinstance(raw, (bytes, bytearray, memoryview)):
        raise CanonicalJsonError("Input must be bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CanonicalJsonError("Invalid UTF-8 sequence") from exc

    if text.startswith("\ufeff"):
        raise CanonicalJsonError("BOM prefix is prohibited")

    try:
        parsed = json.loads(text, object_pairs_hook=_check_no_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise CanonicalJsonError(f"Malformed JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise CanonicalJsonError("Top-level JSON value must be an object")

    # Re-encode and verify byte-for-byte exact match
    try:
        re_encoded = dumps_canonical_json(parsed)
    except CanonicalJsonError as exc:
        raise CanonicalJsonError(f"Canonical re-encoding failed: {exc}") from exc

    if bytes(raw) != re_encoded:
        raise CanonicalJsonError("Parsed JSON does not match canonical re-encoding byte-for-byte")

    return parsed


class StreamDigestCalculator:
    """Computes cross-process incremental SHA-256 stream digest (Section 14)."""

    def __init__(
        self,
        *,
        capture_config_hash: str,
        width: int = 1280,
        height: int = 720,
        target_fps_numerator: int = 10,
        target_fps_denominator: int = 1,
        started_monotonic_ns: int,
    ) -> None:
        if len(capture_config_hash) != 64:
            raise ValueError("capture_config_hash must be 64 hexadecimal characters")
        self._capture_config_hash = capture_config_hash
        self._config_hash_bytes = bytes.fromhex(capture_config_hash)
        self._width = width
        self._height = height
        self._fps_num = target_fps_numerator
        self._fps_den = target_fps_denominator
        self._started_ns = started_monotonic_ns
        self._hasher = hashlib.sha256()

        # Initialize header
        self._hasher.update(b"whole-home-agent.capture-stream.v1\0")
        self._hasher.update(self._config_hash_bytes)
        self._hasher.update(struct.pack(">QQ", self._width, self._height))
        self._hasher.update(struct.pack(">QQ", self._fps_num, self._fps_den))
        self._hasher.update(b"rgb24\0")

    def update_frame(
        self,
        *,
        source_sequence: int,
        captured_monotonic_ns: int,
        rgb_bytes: bytes | memoryview,
    ) -> None:
        """Update stream digest with a frame."""
        offset_ns = captured_monotonic_ns - self._started_ns
        if offset_ns < 0:
            raise ValueError("captured_monotonic_ns cannot precede started_monotonic_ns")
        payload_len = len(rgb_bytes)
        self._hasher.update(b"\x46")
        self._hasher.update(struct.pack(">QQQ", source_sequence, offset_ns, payload_len))
        self._hasher.update(rgb_bytes)

    def update_gap(
        self,
        *,
        first_missing_sequence: int,
        last_missing_sequence: int,
        detected_monotonic_ns: int,
        reason: str,
    ) -> None:
        """Update stream digest with a gap."""
        if reason not in REASON_CODES:
            raise ValueError(f"Unknown gap reason: {reason!r}")
        offset_ns = detected_monotonic_ns - self._started_ns
        if offset_ns < 0:
            raise ValueError("detected_monotonic_ns cannot precede started_monotonic_ns")
        reason_code = REASON_CODES[reason]
        self._hasher.update(b"\x47")
        self._hasher.update(
            struct.pack(
                ">QQQB",
                first_missing_sequence,
                last_missing_sequence,
                offset_ns,
                reason_code,
            )
        )

    def finalize_hex(self) -> str:
        """Returns the lowercase 64-character SHA-256 hexadecimal digest."""
        return self._hasher.hexdigest().lower()
