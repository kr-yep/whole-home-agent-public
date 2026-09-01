"""Executable safeguards for the one-attempt M13 synthetic preflight."""

from __future__ import annotations

import hashlib
import importlib.util
import socket
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "run_m13_dfine_small_synthetic.py"
SPEC = importlib.util.spec_from_file_location("run_m13_dfine_small_synthetic", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
M13 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M13
SPEC.loader.exec_module(M13)
HAS_NUMPY = importlib.util.find_spec("numpy") is not None


class M13StaticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = ROOT / "configs" / "evaluation" / "m13-dfine-small-synthetic-v1.toml"
        cls.document = tomllib.loads(cls.path.read_text(encoding="utf-8"))

    def test_exactly_one_community_conversion_is_synthetic_only(self):
        self.assertEqual(self.document["candidate_count"], 1)
        self.assertEqual(
            self.document["intended_use"], "SYNTHETIC_ONLY_ENGINEERING_QUALIFICATION"
        )
        self.assertEqual(
            self.document["artifact"]["provenance"],
            "COMMUNITY_CONVERTED_NOT_DFINE_AUTHOR_RELEASE",
        )
        self.assertFalse(self.document["artifact"]["original_equivalence_verified"])
        self.assertTrue(self.document["runtime"]["local_files_only"])
        self.assertFalse(self.document["runtime"]["trust_remote_code"])
        self.assertTrue(self.document["runtime"]["use_safetensors"])
        self.assertFalse(
            self.document["runtime"]["uv_lock_reproduces_gpu_environment"]
        )

    def test_dense_allowlist_and_canonical_threshold_are_frozen(self):
        semantics = self.document["semantics"]
        self.assertEqual(semantics["scored_class_ids"], [39, 41, 43, 44, 45, 70, 72])
        self.assertEqual(semantics["confidence_threshold"], 0.25)
        self.assertEqual(semantics["confidence_operator"], ">=")
        self.assertEqual(semantics["postprocessor_threshold"], 0.0)

    def test_all_operational_and_source_boundaries_remain_disabled(self):
        self.assertTrue(
            all(value is False for value in self.document["boundaries"].values())
        )
        self.assertFalse(
            self.document["fixture"]["public_or_private_media_bytes_allowed"]
        )
        self.assertEqual(self.document["attempt"]["maximum_real_load_attempts"], 1)

    def test_adapter_hash_and_strict_cost_bounds_are_frozen(self):
        adapter = ROOT / self.document["implementation"]["adapter_path"]
        self.assertEqual(
            hashlib.sha256(adapter.read_bytes()).hexdigest(),
            self.document["implementation"]["adapter_sha256"],
        )
        self.assertEqual(
            self.document["gate"]["detector_p95_ms_strictly_less_than"], 100.0
        )
        self.assertEqual(
            self.document["gate"]["peak_vram_bytes_strictly_less_than"],
            1_073_741_824,
        )

    def test_nearest_rank_p95_uses_observation_49_of_51(self):
        values = [float(index) for index in range(1, 52)]
        self.assertEqual(M13._nearest_rank_p95(values), 49.0)
        with self.assertRaises(ValueError):
            M13._nearest_rank_p95([])

    def test_canonical_digest_accepts_domain_producer_identity(self):
        detection = SimpleNamespace(
            bbox=SimpleNamespace(as_xyxy=lambda: (0.0, 1.0, 2.0, 3.0)),
            confidence=0.25,
            label="bottle",
            producer_ref=SimpleNamespace(
                identity_payload=lambda: ("dfine", "1", "a" * 64, "b" * 64)
            ),
        )
        self.assertEqual(len(M13._canonical_digest((detection,))), 64)

    def test_network_guard_denies_and_restores_connections(self):
        original = socket.create_connection
        guard = M13.OfflineNetworkGuard()
        with guard:
            with self.assertRaisesRegex(RuntimeError, "NETWORK_CONNECTION_DENIED"):
                socket.create_connection(("example.invalid", 443))
        self.assertIs(socket.create_connection, original)
        self.assertEqual(guard.attempts, ["python_socket_connection"])

    def test_attempt_marker_is_exclusive(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "attempt.json"
            M13._write_json(path, {"status": "STARTED"}, exclusive=True)
            with self.assertRaises(FileExistsError):
                M13._write_json(path, {"status": "STARTED"}, exclusive=True)

    @unittest.skipUnless(HAS_NUMPY, "NumPy is an optional video dependency")
    def test_generated_fixture_has_frozen_byte_identity(self):
        contract = SimpleNamespace(document=self.document)
        image = M13._generated_fixture(contract)
        self.assertEqual(image.shape, (540, 960, 3))
        self.assertEqual(
            hashlib.sha256(image.tobytes()).hexdigest(),
            self.document["fixture"]["rgb_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
