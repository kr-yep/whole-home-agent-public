"""The detector that runs where PyTorch will not install.

Two things are checked here. First, that the fetcher and the server agree on where
weights live: the fetcher writes into models/ and the server reads a fixed list of
candidates, and nothing but a test connects the two, so a rename on either side
would leave a downloaded model sitting somewhere nothing looks for it.

Second, the decoding. An ONNX export hands back one (1, 4 + classes, anchors)
tensor of raw numbers and everything that makes it a detection -- undoing the
letterbox padding, reading the class table out of the file, suppressing the
duplicates -- is arithmetic written here rather than in a library. A box that is
off by the padding still looks like a plausible box, so the round trip is pinned
to exact pixel values against a frame whose answer is known.

The decoding tests need numpy and Pillow and skip without them; the fetcher tests
are standard library, which is what CI installs.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from whole_home_agent import web_app

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "fetch_vision_model", ROOT / "tools" / "fetch_vision_model.py"
)
fetch_vision_model = importlib.util.module_from_spec(_spec)
sys.modules["fetch_vision_model"] = fetch_vision_model
_spec.loader.exec_module(fetch_vision_model)

_HAS_NUMPY = importlib.util.find_spec("numpy") is not None
_HAS_PILLOW = importlib.util.find_spec("PIL") is not None


class WeightsLocationTests(unittest.TestCase):
    def test_every_fetchable_model_is_somewhere_the_server_looks(self):
        """A fetched model the server never finds is a download for nothing."""

        candidates = {str(path) for path in web_app.DETECTOR_CANDIDATES}
        for name in fetch_vision_model.WEIGHTS:
            with self.subTest(model=name):
                relative = fetch_vision_model.model_path(name).relative_to(ROOT)
                self.assertIn(str(relative), candidates)

    def test_the_default_is_one_of_the_models_it_knows(self):
        self.assertIn(fetch_vision_model.DEFAULT_MODEL, fetch_vision_model.WEIGHTS)

    def test_each_model_carries_a_size_and_a_digest(self):
        """Without both, a truncated download would be accepted as the model."""

        for name, (size, digest) in fetch_vision_model.WEIGHTS.items():
            with self.subTest(model=name):
                self.assertGreater(size, 1 << 20)
                self.assertEqual(len(digest), 64)
                self.assertEqual(digest, digest.lower().strip())
                int(digest, 16)

    def test_a_file_of_the_wrong_length_is_rejected(self):
        with TemporaryDirectory() as directory:
            impostor = Path(directory) / "yolov8n.onnx"
            impostor.write_bytes(b"not a model")
            size, digest = fetch_vision_model.WEIGHTS["yolov8n"]
            self.assertTrue(fetch_vision_model._verify(impostor, size, digest))

    def test_the_release_is_pinned_to_a_tag(self):
        """A digest is only worth recording if the bytes behind the URL stay put."""

        self.assertNotIn("/latest/", fetch_vision_model.RELEASE)
        self.assertRegex(fetch_vision_model.RELEASE, r"/download/v\d+\.\d+\.\d+$")


class _FakeSession:
    """Enough of an onnxruntime session to exercise everything around it."""

    def __init__(self, output, *, side=640, names=None):
        self._output = output
        self._side = side
        self._names = names if names is not None else {0: "person", 67: "cell phone"}
        self.seen: dict = {}

    def get_inputs(self):
        return [type("Input", (), {"name": "images", "shape": [1, 3, self._side, self._side]})()]

    def get_outputs(self):
        return [type("Output", (), {"name": "output0", "shape": [1, 84, 8400]})()]

    def get_modelmeta(self):
        return type(
            "Meta", (), {"custom_metadata_map": {"names": repr(self._names)}}
        )()

    def run(self, _outputs, feed):
        self.seen = feed
        return [self._output]


@unittest.skipUnless(_HAS_NUMPY and _HAS_PILLOW, "needs numpy and Pillow")
class OnnxDecodingTests(unittest.TestCase):
    """Boxes in, boxes out, with the padding put back where it came from."""

    FRAME = (1280, 720)

    def setUp(self):
        import numpy

        self.numpy = numpy
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.model = Path(self.directory.name) / "yolov8n.onnx"
        self.model.write_bytes(b"placeholder; the fake session never reads it")

    def _frame(self) -> bytes:
        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", self.FRAME, (30, 40, 50)).save(buffer, format="JPEG", quality=90)
        return buffer.getvalue()

    def _tensor(self, rows: list[tuple[float, float, float, float, int, float]]):
        """One (1, 84, anchors) output holding exactly the rows asked for."""

        anchors = max(len(rows), 1)
        raw = self.numpy.zeros((1, 84, anchors), dtype=self.numpy.float32)
        for index, (cx, cy, width, height, label, score) in enumerate(rows):
            raw[0, 0, index] = cx
            raw[0, 1, index] = cy
            raw[0, 2, index] = width
            raw[0, 3, index] = height
            raw[0, 4 + label, index] = score
        return raw

    def _detector(self, rows, **kwargs):
        from whole_home_agent.adapters.onnx_detector import OnnxDetector

        session = _FakeSession(self._tensor(rows), **kwargs)
        sys.modules["onnxruntime"] = type(
            "FakeRuntime", (), {"InferenceSession": lambda path, providers: session}
        )
        self.addCleanup(sys.modules.pop, "onnxruntime", None)
        detector = OnnxDetector(self.model)
        return detector, session

    def test_the_model_is_loaded_and_reports_itself_available(self):
        detector, _ = self._detector([])
        self.assertTrue(detector.is_available)

    def test_the_frame_is_letterboxed_into_the_square_the_export_wants(self):
        """1280x720 into 640x640 is a 0.5 scale and 140 rows of grey top and bottom."""

        detector, session = self._detector([])
        detector(self._frame(), *self.FRAME)

        tensor = session.seen["images"]
        self.assertEqual(tensor.shape, (1, 3, 640, 640))
        self.assertEqual(str(tensor.dtype), "float32")
        # The padding is the grey the network was trained to ignore, not black.
        self.assertAlmostEqual(float(tensor[0, 0, 0, 0]), 114 / 255, places=4)
        # And the picture itself sits between the two bands.
        self.assertLess(float(tensor[0, 0, 320, 320]), 114 / 255)

    def test_a_box_comes_back_in_the_coordinates_of_the_original_frame(self):
        """Centre of the 640 square, half its width: the middle half of the frame."""

        detector, _ = self._detector([(320.0, 320.0, 320.0, 180.0, 67, 0.9)])
        found = detector(self._frame(), *self.FRAME)

        self.assertEqual(len(found), 1)
        # gain 0.5, 140px of padding on top: x spans 320..960, y spans 180..540.
        self.assertEqual(found[0]["box"], [320.0, 180.0, 640.0, 360.0])

    def test_a_box_running_off_the_frame_is_clamped_to_it(self):
        detector, _ = self._detector([(60.0, 320.0, 400.0, 900.0, 0, 0.9)])
        found = detector(self._frame(), *self.FRAME)

        x, y, width, height = found[0]["box"]
        self.assertEqual([x, y], [0.0, 0.0])
        self.assertLessEqual(x + width, self.FRAME[0])
        self.assertLessEqual(y + height, self.FRAME[1])

    def test_the_label_comes_from_the_models_own_class_table(self):
        """Falling back to the index would put entities like "67" into the memory."""

        detector, _ = self._detector([(320.0, 320.0, 100.0, 100.0, 67, 0.9)])
        found = detector(self._frame(), *self.FRAME)

        self.assertEqual(found[0]["raw_label"], "cell phone")
        self.assertEqual(found[0]["label"], "手機 (cell phone)")
        self.assertEqual(found[0]["confidence"], 0.9)

    def test_the_shape_of_a_detection_matches_the_pytorch_detector(self):
        """CameraIngest holds one sink and cannot tell which of the two it has."""

        detector, _ = self._detector([(320.0, 320.0, 100.0, 100.0, 0, 0.9)])
        found = detector(self._frame(), *self.FRAME)

        self.assertEqual(set(found[0]), {"box", "label", "raw_label", "confidence"})
        self.assertEqual(len(found[0]["box"]), 4)
        json.dumps(found)  # it is sent to the browser, so it has to survive that

    def test_anything_under_the_threshold_is_not_a_detection(self):
        detector, _ = self._detector([(320.0, 320.0, 100.0, 100.0, 0, 0.2)])
        self.assertEqual(detector(self._frame(), *self.FRAME), [])

    def test_the_same_object_found_twice_is_reported_once(self):
        detector, _ = self._detector(
            [
                (320.0, 320.0, 100.0, 100.0, 0, 0.9),
                (325.0, 322.0, 104.0, 98.0, 0, 0.7),
            ]
        )
        found = detector(self._frame(), *self.FRAME)

        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["confidence"], 0.9)

    def test_two_different_things_in_the_same_place_both_survive(self):
        """A phone lying on a book is two detections, not one duplicated."""

        detector, _ = self._detector(
            [
                (320.0, 320.0, 100.0, 100.0, 0, 0.9),
                (322.0, 321.0, 98.0, 102.0, 67, 0.8),
            ]
        )
        found = detector(self._frame(), *self.FRAME)

        self.assertEqual({d["raw_label"] for d in found}, {"person", "cell phone"})

    def test_detections_come_back_most_confident_first(self):
        detector, _ = self._detector(
            [
                (100.0, 100.0, 40.0, 40.0, 0, 0.4),
                (400.0, 400.0, 40.0, 40.0, 67, 0.95),
                (500.0, 200.0, 40.0, 40.0, 0, 0.6),
            ]
        )
        scores = [d["confidence"] for d in detector(self._frame(), *self.FRAME)]

        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_a_runtime_failure_costs_the_frame_and_not_the_server(self):
        """A sink that raises would take the camera down with it."""

        detector, session = self._detector([])

        def explode(*_args, **_kwargs):
            raise RuntimeError("inference failed")

        session.run = explode
        self.assertEqual(detector(self._frame(), *self.FRAME), [])

    def test_a_model_that_is_not_there_is_reported_rather_than_raised(self):
        from whole_home_agent.adapters.onnx_detector import OnnxDetector

        self.assertFalse(OnnxDetector(self.model.parent / "absent.onnx").is_available)


if __name__ == "__main__":
    unittest.main()
