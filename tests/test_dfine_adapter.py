"""Contract tests for the synthetic-only D-FINE Small qualification seam."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from whole_home_agent.adapters.dfine import (
    EXPECTED_SCORED_CLASS_IDS,
    DFineConfig,
    DFineDetector,
)
from whole_home_agent.model import SourcePosition, TimestampBasis
from whole_home_agent.perception import VideoFrame


HAS_NUMPY = importlib.util.find_spec("numpy") is not None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dense_names() -> tuple[str, ...]:
    names = [f"coco-class-{index}" for index in range(80)]
    for class_id, name in EXPECTED_SCORED_CLASS_IDS.items():
        names[class_id] = name
    return tuple(names)


def _build_config(directory: Path, **overrides: object) -> DFineConfig:
    names = _dense_names()
    config_document = {
        "architectures": ["DFineForObjectDetection"],
        "id2label": {str(index): name for index, name in enumerate(names)},
        "model_type": "d_fine",
        "num_queries": 300,
        "use_focal_loss": True,
    }
    preprocessor_document = {
        "do_normalize": False,
        "do_pad": False,
        "do_rescale": True,
        "do_resize": True,
        "image_processor_type": "RTDetrImageProcessor",
        "rescale_factor": 1 / 255,
        "size": {"height": 640, "width": 640},
    }
    weights = directory / "model.safetensors"
    model_config = directory / "config.json"
    preprocessor = directory / "preprocessor_config.json"
    weights.write_bytes(b"fake-safetensors-for-contract-test")
    model_config.write_text(
        json.dumps(config_document, sort_keys=True), encoding="utf-8"
    )
    preprocessor.write_text(
        json.dumps(preprocessor_document, sort_keys=True), encoding="utf-8"
    )
    values: dict[str, object] = {
        "model_dir": directory,
        "weights_sha256": _sha256(weights),
        "weights_bytes": weights.stat().st_size,
        "config_sha256": _sha256(model_config),
        "config_bytes": model_config.stat().st_size,
        "preprocessor_sha256": _sha256(preprocessor),
        "preprocessor_bytes": preprocessor.stat().st_size,
        "class_id_map": tuple(enumerate(names)),
        "scored_labels": tuple(EXPECTED_SCORED_CLASS_IDS.values()),
        "device": "cpu",
        "inference_dtype": "float32",
    }
    values.update(overrides)
    return DFineConfig(**values)


class DFineConfigContractTests(unittest.TestCase):
    def test_artifact_identity_is_checked_before_runtime_construction(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            config = _build_config(directory)
            (directory / "model.safetensors").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "size/SHA-256"):
                DFineConfig(**{
                    **{
                        field: getattr(config, field)
                        for field in config.__dataclass_fields__
                    },
                    "model_dir": directory,
                })

    def test_dense_coco_map_rejects_sparse_bottle_semantics(self):
        with tempfile.TemporaryDirectory() as raw_directory:
            directory = Path(raw_directory)
            names = list(_dense_names())
            names[39], names[44] = names[44], names[39]
            with self.assertRaisesRegex(ValueError, "dense COCO"):
                _build_config(directory, class_id_map=tuple(enumerate(names)))

    def test_module_import_does_not_import_torch_or_transformers(self):
        command = (
            "import sys; import whole_home_agent.adapters.dfine; "
            "assert 'torch' not in sys.modules; assert 'transformers' not in sys.modules"
        )
        result = subprocess.run(
            [sys.executable, "-c", command],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(HAS_NUMPY, "NumPy is an optional video dependency")
class DFineTranslationContractTests(unittest.TestCase):
    @staticmethod
    def _frame(rgb: object) -> VideoFrame:
        return VideoFrame(
            position=SourcePosition(
                source_sequence=0,
                source_offset=0,
                timestamp_basis=TimestampBasis.SOURCE_FRAME_INDEX,
                frame_index=0,
            ),
            rgb=rgb,
        )

    def test_dense_labels_threshold_clipping_and_sorting_are_canonical(self):
        import numpy as np

        class FakeRuntime:
            def infer(self, rgb):
                self.shape = rgb.shape
                return {
                    "scores": np.asarray(
                        [0.25, 0.9, np.nextafter(0.25, 0.0), 0.8]
                    ),
                    "labels": np.asarray([39, 44, 39, 39], dtype=np.int64),
                    "boxes": np.asarray(
                        [
                            [-2.0, 2.0, 20.0, 30.0],
                            [1.0, 1.0, 4.0, 4.0],
                            [2.0, 2.0, 5.0, 5.0],
                            [5.0, 5.0, 5.0, 9.0],
                        ]
                    ),
                }

        with tempfile.TemporaryDirectory() as raw_directory:
            runtime = FakeRuntime()
            detector = DFineDetector(
                _build_config(Path(raw_directory)), runtime_object=runtime
            )
            detections = detector.detect(
                self._frame(np.zeros((16, 12, 3), dtype=np.uint8))
            )
        self.assertEqual(runtime.shape, (16, 12, 3))
        self.assertEqual([item.label for item in detections], ["bottle", "spoon"])
        self.assertEqual(detections[0].confidence, 0.25)
        self.assertEqual(detections[0].bbox.as_xyxy(), (0.0, 2.0, 12.0, 16.0))
        self.assertIn("community-conversion", detections[0].producer_ref.component)

    def test_unknown_non_integer_and_non_finite_outputs_fail_closed(self):
        import numpy as np

        invalid_results = (
            {
                "scores": np.asarray([0.9]),
                "labels": np.asarray([80], dtype=np.int64),
                "boxes": np.asarray([[0.0, 0.0, 2.0, 2.0]]),
            },
            {
                "scores": np.asarray([0.9]),
                "labels": np.asarray([39.0]),
                "boxes": np.asarray([[0.0, 0.0, 2.0, 2.0]]),
            },
            {
                "scores": np.asarray([float("nan")]),
                "labels": np.asarray([39], dtype=np.int64),
                "boxes": np.asarray([[0.0, 0.0, 2.0, 2.0]]),
            },
        )
        with tempfile.TemporaryDirectory() as raw_directory:
            config = _build_config(Path(raw_directory))
            frame = self._frame(np.zeros((4, 4, 3), dtype=np.uint8))
            for result in invalid_results:
                with self.subTest(result=result):
                    runtime = type("FakeRuntime", (), {"infer": lambda self, rgb: result})()
                    with self.assertRaises(ValueError):
                        DFineDetector(config, runtime_object=runtime).detect(frame)

    def test_invalid_rgb_and_shape_mismatch_fail_closed(self):
        import numpy as np

        class FakeRuntime:
            def infer(self, rgb):
                return {
                    "scores": np.asarray([0.9]),
                    "labels": np.asarray([], dtype=np.int64),
                    "boxes": np.empty((0, 4)),
                }

        with tempfile.TemporaryDirectory() as raw_directory:
            detector = DFineDetector(
                _build_config(Path(raw_directory)), runtime_object=FakeRuntime()
            )
            with self.assertRaisesRegex(ValueError, "RGB uint8"):
                detector.detect(self._frame(np.zeros((4, 4, 3), dtype=np.float32)))
            with self.assertRaisesRegex(ValueError, "output shapes"):
                detector.detect(self._frame(np.zeros((4, 4, 3), dtype=np.uint8)))


if __name__ == "__main__":
    unittest.main()
