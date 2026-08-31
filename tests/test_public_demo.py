"""Closed CLI and presentation boundary for the public prerecorded demo."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from whole_home_agent import public_demo
from whole_home_agent.cli import main as cli_main
from whole_home_agent.errors import SourceError
from whole_home_agent.public_demo import (
    PUBLIC_MANIFEST,
    REPOSITORY_ROOT,
    load_public_demo_media,
    run_public_demo,
)
from whole_home_agent.video_manifest import load_video_manifest


HAS_VIDEO = importlib.util.find_spec("av") is not None and importlib.util.find_spec(
    "numpy"
) is not None
HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None


class DemoBundleResolutionTests(unittest.TestCase):
    def test_wheel_shared_data_root_is_resolved_without_repo_bundle(self):
        relative_manifest = Path(
            "examples/media/generated/key_bag_sofa_v2.manifest.json"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            missing_repository_root = temporary_root / "missing-clone"
            installed_root = temporary_root / "venv" / "wha"
            installed_manifest = installed_root / relative_manifest
            installed_manifest.parent.mkdir(parents=True)
            installed_manifest.write_text("{}", encoding="utf-8")
            with (
                mock.patch.object(
                    public_demo, "REPOSITORY_ROOT", missing_repository_root
                ),
                mock.patch.object(
                    public_demo,
                    "PUBLIC_MANIFEST",
                    missing_repository_root / relative_manifest,
                ),
                mock.patch.object(
                    public_demo.sys, "prefix", str(temporary_root / "venv")
                ),
            ):
                self.assertEqual(public_demo._resolve_demo_root(), installed_root)


@unittest.skipUnless(HAS_VIDEO, "video optional dependencies are not installed")
class PublicDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_public_demo(
            replay_run_id="public-demo-test", include_frames=True
        )

    def test_presentation_contains_scoped_answer_evidence_and_limits(self):
        result = self.result
        self.assertEqual(result["governance"]["operate"], "DISABLED")
        self.assertFalse(result["governance"]["physical_truth_claimed"])
        self.assertEqual(result["answer"]["status"], "FOUND")
        self.assertEqual(result["answer"]["location_id"], "sofa")
        self.assertEqual(result["answer"]["epistemic_status"], "estimated")
        self.assertEqual(len(result["claims"]), 2)
        self.assertTrue(all(item["evidence"] for item in result["claims"]))
        self.assertEqual(len(result["frames"]), 80)
        self.assertEqual(result["relation_evaluation"]["quality"]["f1"], 1.0)
        self.assertTrue(result["warnings"])

    def test_media_bytes_match_the_allowlisted_manifest(self):
        manifest = load_video_manifest(PUBLIC_MANIFEST, repository_root=REPOSITORY_ROOT)
        self.assertEqual(
            hashlib.sha256(load_public_demo_media()).hexdigest(),
            manifest.descriptor.content_hash,
        )

    def test_cli_compact_mode_omits_frames_and_emits_json(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "demo-recorded",
                    "--compact",
                    "--run-id",
                    "public-demo-cli-test",
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["frames"], [])
        self.assertEqual(payload["run_receipt"]["status"], "COMPLETE")

    def test_subject_outside_manifest_allowlist_fails_closed(self):
        with self.assertRaises(SourceError):
            run_public_demo(subject_id="../camera", include_frames=False)

    def test_streamlit_source_has_no_upload_or_camera_widget(self):
        source = (
            REPOSITORY_ROOT / "src" / "whole_home_agent" / "streamlit_app.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("file_uploader", source)
        self.assertNotIn("camera_input", source)
        self.assertNotIn("text_input", source)
        self.assertNotIn("chat_input", source)


@unittest.skipUnless(HAS_STREAMLIT and HAS_VIDEO, "demo extra is not installed")
class StreamlitSmokeTests(unittest.TestCase):
    def test_app_renders_without_exception(self):
        from streamlit.testing.v1 import AppTest

        app_path = (
            REPOSITORY_ROOT / "src" / "whole_home_agent" / "streamlit_app.py"
        )
        app = AppTest.from_file(str(app_path)).run(timeout=30)
        self.assertEqual(app.exception, [])
        self.assertTrue(any("Whole Home Agent" in item.value for item in app.title))


if __name__ == "__main__":
    unittest.main()
