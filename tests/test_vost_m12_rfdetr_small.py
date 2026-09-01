"""Executable safeguards for the single M12 development screen."""

from __future__ import annotations

import importlib.util
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from whole_home_agent.perception import BoundingBox


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "run_vost_m12_rfdetr_small.py"
SPEC = importlib.util.spec_from_file_location("run_vost_m12_rfdetr_small", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
M12 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M12
SPEC.loader.exec_module(M12)


class M12ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = M12.load_contract()

    def test_contract_freezes_small_sparse_coco_and_development_only(self):
        self.assertEqual(self.contract.document["candidate_count"], 1)
        self.assertEqual(self.contract.document["model_variant"], "small")
        self.assertEqual(dict(self.contract.class_id_map)[44], "bottle")
        self.assertEqual(len(self.contract.class_id_map), 80)
        self.assertEqual(
            self.contract.document["source"]["sequence_id"],
            "3518_unscrew_bottle",
        )
        self.assertFalse(
            self.contract.document["source"]["reserved_bytes_allowed"]
        )
        self.assertEqual(
            self.contract.document["runtime"]["inference_dtype"], "float16"
        )
        self.assertFalse(
            self.contract.document["environment"]["uv_lock_reproduces_gpu_environment"]
        )

    def test_gate_uses_strict_cost_bounds(self):
        passed = M12.evaluate_gate(0.60, 99.999, 1073741823, contract=self.contract)
        p95_boundary = M12.evaluate_gate(0.60, 100.0, 1, contract=self.contract)
        vram_boundary = M12.evaluate_gate(
            0.60, 1.0, 1073741824, contract=self.contract
        )
        self.assertTrue(passed["passed"])
        self.assertFalse(p95_boundary["passed"])
        self.assertFalse(vram_boundary["passed"])

    def test_pairing_is_descriptive_and_matches_frame_indexes(self):
        target = SimpleNamespace(label="bottle", bbox=BoundingBox(0, 0, 10, 10))
        prediction = SimpleNamespace(label="bottle", bbox=BoundingBox(0, 0, 10, 10))
        ground_truth = {index: (target,) for index in range(51)}
        predictions = {index: (prediction,) for index in (0, 3, 9)}
        result = M12.paired_recovery(
            predictions, ground_truth, contract=self.contract
        )
        self.assertEqual(result["matched_frame_count"], 3)
        self.assertEqual(
            result["by_prior_m11_category"]["m11_confidence_filtered"]["matched_now"],
            1,
        )
        self.assertEqual(
            result["by_prior_m11_category"]["m11_localization_miss"]["matched_now"],
            1,
        )
        self.assertEqual(result["status"], "DESCRIPTIVE_NOT_A_GATE")

    def test_network_guard_denies_and_restores_python_connections(self):
        original = socket.create_connection
        guard = M12.OfflineNetworkGuard()
        with guard:
            with self.assertRaisesRegex(RuntimeError, "NETWORK_CONNECTION_DENIED"):
                socket.create_connection(("example.invalid", 443))
        self.assertIs(socket.create_connection, original)
        self.assertEqual(guard.attempts, ["python_socket_connection"])

    def test_attempt_marker_is_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempt.json"
            M12._write_json(path, {"status": "STARTED"}, exclusive=True)
            with self.assertRaises(FileExistsError):
                M12._write_json(path, {"status": "STARTED"}, exclusive=True)


if __name__ == "__main__":
    unittest.main()
