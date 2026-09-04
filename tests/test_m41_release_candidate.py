"""Contract and checker tests for the M41 local packaging gate."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import socket
import tarfile
import tempfile
import tomllib
import unittest
from pathlib import Path
import zipfile

from tools.check_m41_release_candidate import (
    CONTRACT,
    ROOT,
    deny_network,
    inspect_artifacts,
    validate_demo,
    validate_fallback,
)


class M41ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_freezes_exact_m40_product_and_inputs(self):
        self.assertEqual(
            self.document["product_revision"],
            "ba0954650586471a737efd9eb829d65e48eea73b",
        )
        self.assertEqual(
            hashlib.sha256((ROOT / self.document["m40_result"]).read_bytes()).hexdigest(),
            self.document["m40_result_sha256"],
        )
        self.assertEqual(
            hashlib.sha256((ROOT / "pyproject.toml").read_bytes()).hexdigest(),
            self.document["pyproject_sha256"],
        )

    def test_one_attempt_is_offline_and_uses_a_fresh_environment(self):
        self.assertEqual(self.document["attempt_limit"], 1)
        self.assertFalse(self.document["additional_retry_allowed"])
        self.assertEqual(self.document["environment"]["network_mode"], "OFFLINE_BUILD_INSTALL_AND_DEMO")
        self.assertFalse(self.document["environment"]["preexisting_project_venv_reuse_allowed"])
        self.assertTrue(self.document["install"]["fresh_virtual_environment_required"])
        self.assertFalse(self.document["install"]["editable_or_source_path_install_allowed"])

    def test_installed_demo_expectations_include_m40_normal_and_fallback(self):
        presentation = self.document["expected_presentation"]
        fallback = self.document["expected_fallback"]
        self.assertEqual(presentation["status"], "PRESENTED")
        self.assertFalse(presentation["fallback_used"])
        self.assertEqual(fallback["status"], "FALLBACK")
        self.assertEqual(fallback["failure_code"], "PRESENTER_FAILURE")
        self.assertTrue(fallback["structured_answer_matches_normal_semantics"])

    def test_every_product_runtime_and_publication_boundary_is_closed(self):
        self.assertTrue(all(value is False for value in self.document["boundaries"].values()))
        self.assertFalse(self.document["network"]["private_registry_credential_or_provider_allowed"])
        self.assertFalse(self.document["decision"]["normal_stop_authorizes_retry"])


def _normal_payload(contract):
    answer = contract["expected_answer"]
    presentation = contract["expected_presentation"]
    return {
        "answer": {
            "status": answer["status"],
            "subject_id": answer["subject_id"],
            "location_id": answer["location_id"],
            "epistemic_status": answer["epistemic_status"],
            "relation_path": [
                {"subject_id": "key", "predicate": "inside", "object_id": "bag"},
                {"subject_id": "bag", "predicate": "at_zone", "object_id": "sofa"},
            ],
        },
        "run_receipt": {"status": answer["run_receipt_status"]},
        "frames": [],
        "governance": {
            "operate": answer["operate"],
            "physical_truth_claimed": answer["physical_truth_claimed"],
        },
        "language_context": {"schema": presentation["context_schema"]},
        "presentation": {
            "schema": presentation["result_schema"],
            "context_schema": presentation["context_schema"],
            "presenter_id": presentation["presenter_id"],
            "status": presentation["status"],
            "fallback_used": presentation["fallback_used"],
            "failure_code": None,
            "text": presentation["text"],
        },
        "answer_summary": presentation["text"],
    }


class M41CheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_normal_and_fallback_payload_validation_is_exact(self):
        normal = _normal_payload(self.contract)
        self.assertEqual(validate_demo(normal, self.contract), [])
        fallback = _normal_payload(self.contract)
        expected = self.contract["expected_fallback"]
        fallback["presentation"] = {
            "status": expected["status"],
            "failure_code": expected["failure_code"],
            "text": expected["text"],
        }
        fallback["answer_summary"] = expected["text"]
        self.assertEqual(validate_fallback(normal, fallback, self.contract), [])

        normal["answer_summary"] = "鑰匙被放進包包，之後移動"
        self.assertIn("TEMPORAL_OVERCLAIM", validate_demo(normal, self.contract))
        fallback["presentation"]["detail"] = "must-not-escape"
        self.assertIn(
            "FALLBACK_EXCEPTION_LEAK",
            validate_fallback(_normal_payload(self.contract), fallback, self.contract),
        )

    def test_archive_inspection_accepts_exact_minimal_members(self):
        presentation_bytes = (ROOT / "src" / "whole_home_agent" / "presentation.py").read_bytes()
        active_contract = copy.deepcopy(self.contract)
        active_contract["presentation_module_sha256"] = hashlib.sha256(
            presentation_bytes
        ).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / "whole_home_agent-0.1.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                for suffix in active_contract["wheel_contract"]["required_suffixes"]:
                    name = suffix if suffix.startswith("whole_home_agent/") else f"data/{suffix}"
                    data = presentation_bytes if name.endswith("whole_home_agent/presentation.py") else b"fixture"
                    archive.writestr(name, data)
            sdist = root / "whole_home_agent-0.1.0.tar.gz"
            with tarfile.open(sdist, "w:gz") as archive:
                for suffix in active_contract["sdist_contract"]["required_suffixes"]:
                    name = f"whole_home_agent-0.1.0/{suffix}"
                    data = presentation_bytes if suffix.endswith("src/whole_home_agent/presentation.py") else b"fixture"
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))

            failures, receipt = inspect_artifacts(wheel, sdist, active_contract)

        self.assertEqual(failures, [])
        self.assertEqual(
            receipt["wheel_presentation_sha256"],
            active_contract["presentation_module_sha256"],
        )
        self.assertEqual(
            receipt["wheel_member_count"],
            len(active_contract["wheel_contract"]["required_suffixes"]),
        )

    def test_archive_inspection_rejects_traversal_and_forbidden_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wheel = root / "bad.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("../escape.py", b"x")
                archive.writestr("whole_home_agent/model.safetensors", b"x")
            sdist = root / "bad.tar.gz"
            with tarfile.open(sdist, "w:gz") as archive:
                info = tarfile.TarInfo("whole_home_agent-0.1.0/.env")
                info.size = 1
                archive.addfile(info, io.BytesIO(b"x"))
            failures, _receipt = inspect_artifacts(wheel, sdist, self.contract)
        self.assertIn("UNSAFE_ARCHIVE_PATH", failures)
        self.assertIn("FORBIDDEN_ARCHIVE_MEMBER", failures)
        self.assertIn("MISSING_REQUIRED_MEMBER", failures)

    def test_network_guard_counts_and_restores_socket_entry_points(self):
        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        original_create = socket.create_connection
        counter = {"attempts": 0}
        with deny_network(counter):
            with self.assertRaises(RuntimeError):
                socket.create_connection(("example.invalid", 443))
        self.assertEqual(counter["attempts"], 1)
        self.assertIs(socket.socket.connect, original_connect)
        self.assertIs(socket.socket.connect_ex, original_connect_ex)
        self.assertIs(socket.create_connection, original_create)


if __name__ == "__main__":
    unittest.main()
