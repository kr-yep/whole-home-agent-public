"""Tests for Windows Webcam IPC wire framing and canonical JSON (WHA-WIN-CAPTURE-ROI-001)."""

from __future__ import annotations

import struct
import unittest

from whole_home_agent.adapters.windows_webcam.wire_protocol import (
    FIXED_PREFIX_BYTES,
    FRAME_BODY_BYTES,
    KIND_END,
    KIND_FRAME,
    KIND_GAP,
    KIND_START,
    WIRE_MAGIC,
    WIRE_VERSION,
    CanonicalJsonError,
    StreamDigestCalculator,
    WireFramingError,
    WirePrefix,
    dumps_canonical_json,
    loads_canonical_json,
)


class TestWirePrefix(unittest.TestCase):
    def test_valid_prefix_pack_unpack(self) -> None:
        prefix = WirePrefix(
            magic=WIRE_MAGIC,
            wire_version=WIRE_VERSION,
            message_kind=KIND_FRAME,
            flags=0,
            metadata_length=120,
            body_length=FRAME_BODY_BYTES,
        )
        packed = prefix.pack()
        self.assertEqual(len(packed), FIXED_PREFIX_BYTES)
        unpacked = WirePrefix.unpack(packed)
        self.assertEqual(unpacked, prefix)

    def test_reject_invalid_magic(self) -> None:
        bad_magic = b"XYZ1" + struct.pack(">BBHII", 1, KIND_START, 0, 50, 0)
        with self.assertRaises(WireFramingError) as ctx:
            WirePrefix.unpack(bad_magic)
        self.assertIn("Invalid magic", str(ctx.exception))

    def test_reject_wrong_version(self) -> None:
        bad_version = WIRE_MAGIC + struct.pack(">BBHII", 2, KIND_START, 0, 50, 0)
        with self.assertRaises(WireFramingError) as ctx:
            WirePrefix.unpack(bad_version)
        self.assertIn("Unsupported wire version", str(ctx.exception))

    def test_reject_nonzero_flags(self) -> None:
        bad_flags = WIRE_MAGIC + struct.pack(">BBHII", 1, KIND_START, 1, 50, 0)
        with self.assertRaises(WireFramingError) as ctx:
            WirePrefix.unpack(bad_flags)
        self.assertIn("flags must be 0", str(ctx.exception))

    def test_reject_oversized_metadata(self) -> None:
        bad_meta = WIRE_MAGIC + struct.pack(">BBHII", 1, KIND_START, 0, 9000, 0)
        with self.assertRaises(WireFramingError) as ctx:
            WirePrefix.unpack(bad_meta)
        self.assertIn("bounds", str(ctx.exception))

    def test_reject_frame_with_wrong_body_length(self) -> None:
        bad_body = WIRE_MAGIC + struct.pack(">BBHII", 1, KIND_FRAME, 0, 100, 1000)
        with self.assertRaises(WireFramingError) as ctx:
            WirePrefix.unpack(bad_body)
        self.assertIn("Body length", str(ctx.exception))


class TestCanonicalJson(unittest.TestCase):
    def test_canonical_json_roundtrip(self) -> None:
        data = {
            "schema": "whole-home-agent.capture-message.v1",
            "kind": "frame",
            "source_sequence": 42,
            "captured_monotonic_ns": 1234567890,
            "is_valid": True,
            "extra": None,
        }
        encoded = dumps_canonical_json(data)
        decoded = loads_canonical_json(encoded)
        self.assertEqual(decoded, data)

    def test_key_sorting(self) -> None:
        data = {"z": 1, "a": 2, "m": 3}
        encoded = dumps_canonical_json(data)
        self.assertEqual(encoded, b'{"a":2,"m":3,"z":1}')

    def test_reject_float(self) -> None:
        with self.assertRaises(CanonicalJsonError):
            dumps_canonical_json({"fps": 10.5})

    def test_reject_duplicate_keys(self) -> None:
        raw_with_dups = b'{"a":1,"a":2}'
        with self.assertRaises(CanonicalJsonError) as ctx:
            loads_canonical_json(raw_with_dups)
        self.assertIn("Duplicate JSON key", str(ctx.exception))

    def test_reject_non_canonical_whitespace(self) -> None:
        raw_whitespace = b'{"a": 1, "b": 2}'
        with self.assertRaises(CanonicalJsonError) as ctx:
            loads_canonical_json(raw_whitespace)
        self.assertIn("does not match canonical re-encoding", str(ctx.exception))

    def test_reject_bom(self) -> None:
        raw_bom = b'\xef\xbb\xbf{"a":1}'
        with self.assertRaises(CanonicalJsonError):
            loads_canonical_json(raw_bom)


class TestStreamDigestCalculator(unittest.TestCase):
    def test_deterministic_stream_digest(self) -> None:
        calc1 = StreamDigestCalculator(
            capture_config_hash="00" * 32,
            started_monotonic_ns=1_000_000_000,
        )
        calc2 = StreamDigestCalculator(
            capture_config_hash="00" * 32,
            started_monotonic_ns=1_000_000_000,
        )
        fake_frame = b"\xaa" * FRAME_BODY_BYTES
        calc1.update_frame(source_sequence=0, captured_monotonic_ns=1_100_000_000, rgb_bytes=fake_frame)
        calc2.update_frame(source_sequence=0, captured_monotonic_ns=1_100_000_000, rgb_bytes=fake_frame)

        digest1 = calc1.finalize_hex()
        digest2 = calc2.finalize_hex()
        self.assertEqual(digest1, digest2)
        self.assertEqual(len(digest1), 64)

    def test_gap_affects_digest(self) -> None:
        calc1 = StreamDigestCalculator(
            capture_config_hash="00" * 32,
            started_monotonic_ns=1_000_000_000,
        )
        calc2 = StreamDigestCalculator(
            capture_config_hash="00" * 32,
            started_monotonic_ns=1_000_000_000,
        )
        calc1.update_gap(first_missing_sequence=1, last_missing_sequence=2, detected_monotonic_ns=1_200_000_000, reason="capture_overrun")
        calc2.update_gap(first_missing_sequence=1, last_missing_sequence=2, detected_monotonic_ns=1_200_000_000, reason="queue_overflow")

        self.assertNotEqual(calc1.finalize_hex(), calc2.finalize_hex())


if __name__ == "__main__":
    unittest.main()
