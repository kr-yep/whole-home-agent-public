"""The same YOLO weights, run without PyTorch.

`yolo_detector.YoloDetector` needs Ultralytics, which needs PyTorch, and PyTorch
publishes exactly one macOS wheel per release: `macosx_14_0_arm64`. A teammate on
an Intel Mac, or on anything older than Sonoma, has no wheel to install and pip
falls back to building it from source, which does not finish. That is a packaging
fact rather than a bug in this project, and no amount of retrying `pip install`
gets past it.

So this reads the same network from its ONNX export instead. Ultralytics publishes
those alongside the `.pt` files in its assets releases, `tools/fetch_vision_model.py`
fetches one, and ONNX Runtime still builds for the machines PyTorch dropped, at about
a sixth of its download. Its own window narrows with the hardware -- an Intel Mac tops
out at 1.23.2 and therefore Python 3.13 -- which README.md sets out in a table.

It is the same network, not an approximation of it: fed one identical tensor, the
two runtimes' raw outputs differ by 0.0012 across all 8400 anchors. What differs is
the step before, because the frame is scaled into the square with Pillow here and
with OpenCV there. On a photo of a street that moved every box by an IoU of 0.91 or
better and left every label the same, while confidences came out a few hundredths
higher on this side -- Pillow's downscale is antialiased and smooths the JPEG's own
artefacts away. Slightly more willing to call something a detection, then, and in
the same places.

Needs onnxruntime, numpy and Pillow. Nothing here imports them at module scope, so
a checkout without them still imports this package and simply has no detector.
"""

from __future__ import annotations

import ast
import io
import logging
from pathlib import Path
from typing import Any, Optional

from .yolo_detector import COCO_TRANSLATIONS

logger = logging.getLogger(__name__)

# Ultralytics letterboxes with this grey, and a box's position is measured against
# the padded canvas, so the padding colour has to be the one the network was fed.
PAD_VALUE = 114

# Its own predict defaults, kept so that the two runtimes agree on what counts as a
# detection rather than on what each of them happened to be configured with.
DEFAULT_CONFIDENCE = 0.25
DEFAULT_IOU = 0.7
MAX_DETECTIONS = 300


class OnnxDetector:
    """An ONNX YOLO export as a callable sink for CameraIngest.

    The call signature and the shape of what comes back match YoloDetector exactly,
    because CameraIngest holds one sink and does not know which of the two it has.
    """

    def __init__(
        self,
        model_path: str | Path,
        *,
        confidence: float = DEFAULT_CONFIDENCE,
        iou: float = DEFAULT_IOU,
        providers: Optional[list[str]] = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.confidence = confidence
        self.iou = iou
        self._session: Any = None
        self._input_name = ""
        self._side = 640
        self._names: dict[int, str] = {}
        self._load_model(providers)

    def _load_model(self, providers: Optional[list[str]]) -> None:
        try:
            import onnxruntime

            if not self.model_path.exists():
                logger.warning("ONNX model not found at %s", self.model_path)
                return

            # CPU is the point of this path. A machine with a working GPU runtime
            # has a working PyTorch too and should be on the other one.
            chosen = providers or ["CPUExecutionProvider"]
            session = onnxruntime.InferenceSession(str(self.model_path), providers=chosen)
            self._input_name = session.get_inputs()[0].name
            self._side = self._square_side(session)
            self._names = self._class_names(session)
            self._session = session
            logger.info(
                "Loaded ONNX detector from %s at %dx%d with %d classes",
                self.model_path,
                self._side,
                self._side,
                len(self._names),
            )
        except Exception as error:
            logger.warning("Failed to initialize the ONNX detector: %s", error)
            self._session = None

    @staticmethod
    def _square_side(session: Any) -> int:
        """The export fixes its input size; reading it beats assuming 640."""

        shape = session.get_inputs()[0].shape
        side = shape[-1] if len(shape) == 4 else None
        return side if isinstance(side, int) and side > 0 else 640

    @staticmethod
    def _class_names(session: Any) -> dict[int, str]:
        """Ultralytics writes the class table into the file, so use that one.

        A label the bridge does not recognise falls through to its own slug, which
        means an index here rather than a name would put entities like "63" into
        the memory. Taking the names from the model keeps the two runtimes agreeing
        on what a class is called.
        """

        raw = session.get_modelmeta().custom_metadata_map.get("names", "")
        try:
            parsed = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {int(index): str(name) for index, name in parsed.items()}

    @property
    def is_available(self) -> bool:
        return self._session is not None

    @property
    def class_names(self) -> dict[int, str]:
        """The class table read out of the model file, by index."""

        return dict(self._names)

    @property
    def input_side(self) -> int:
        """The square the export wants its frames scaled into."""

        return self._side

    def __call__(self, payload: bytes, width: int, height: int) -> list[dict[str, Any]]:
        """In-memory inference hook. Decodes JPEG, predicts, and drops raw frame."""

        if self._session is None:
            return []

        try:
            import numpy
            from PIL import Image

            # In-memory PIL decode; never written to storage
            image = Image.open(io.BytesIO(payload)).convert("RGB")
            tensor, gain, offset = self._letterbox(image, numpy, Image)
            raw = self._session.run(None, {self._input_name: tensor})[0]
            return self._decode(raw, gain, offset, image.size, numpy)
        except Exception as error:
            logger.error("Error during ONNX inference: %s", error)
            return []

    def _letterbox(self, image: Any, numpy: Any, Image: Any) -> tuple[Any, float, tuple[int, int]]:
        """Fit the frame into the square the export demands, without distorting it.

        Stretching to 640x640 would work and would also move every box, because the
        network sees shapes. Scaling by one factor and padding the short side keeps
        the geometry, and the factor and offset are what turn a box back into frame
        coordinates afterwards.
        """

        side = self._side
        source_width, source_height = image.size
        gain = min(side / source_width, side / source_height)
        scaled = (
            max(1, round(source_width * gain)),
            max(1, round(source_height * gain)),
        )
        offset = ((side - scaled[0]) // 2, (side - scaled[1]) // 2)

        canvas = Image.new("RGB", (side, side), (PAD_VALUE, PAD_VALUE, PAD_VALUE))
        canvas.paste(image.resize(scaled, Image.BILINEAR), offset)
        array = numpy.asarray(canvas, dtype=numpy.float32) / 255.0
        return array.transpose(2, 0, 1)[None], gain, offset

    def _decode(
        self,
        raw: Any,
        gain: float,
        offset: tuple[int, int],
        size: tuple[int, int],
        numpy: Any,
    ) -> list[dict[str, Any]]:
        """Turn one (1, 4 + classes, anchors) tensor into detections in frame pixels.

        The v8 head has no objectness channel: the class scores are the confidence,
        and every anchor reports a box whether or not anything is there. So the class
        maximum is the score, everything under the threshold goes, and what survives
        still overlaps itself several times over and needs suppressing.
        """

        predictions = numpy.asarray(raw)[0].T
        if predictions.ndim != 2 or predictions.shape[1] < 5:
            return []
        if self._names and predictions.shape[1] != 4 + len(self._names):
            # Every detect export is four box channels and one per class. A -seg
            # or -pose export has more, and reading those extra channels as class
            # scores would produce boxes that look ordinary and mean nothing, so
            # a model this cannot decode is refused rather than misread.
            logger.error(
                "%s returns %d channels; %d classes need %d. This is not a detect export.",
                self.model_path.name,
                predictions.shape[1],
                len(self._names),
                4 + len(self._names),
            )
            return []

        scores = predictions[:, 4:]
        best = scores.argmax(axis=1)
        confidence = scores.max(axis=1)
        keep = confidence >= self.confidence
        if not keep.any():
            return []

        boxes = self._to_frame(predictions[keep, :4], gain, offset, size, numpy)
        confidence = confidence[keep]
        best = best[keep]

        detections: list[dict[str, Any]] = []
        for index in self._suppress(boxes, confidence, best, numpy):
            x1, y1, x2, y2 = boxes[index]
            raw_label = self._names.get(int(best[index]), str(int(best[index])))
            display_label = COCO_TRANSLATIONS.get(raw_label, raw_label)
            detections.append(
                {
                    "box": [
                        round(float(x1), 1),
                        round(float(y1), 1),
                        round(float(x2 - x1), 1),
                        round(float(y2 - y1), 1),
                    ],
                    "label": f"{display_label} ({raw_label})",
                    "raw_label": raw_label,
                    "confidence": round(float(confidence[index]), 2),
                }
            )
        return detections

    @staticmethod
    def _to_frame(
        boxes: Any,
        gain: float,
        offset: tuple[int, int],
        size: tuple[int, int],
        numpy: Any,
    ) -> Any:
        """centre/size on the padded square -> corners on the original frame."""

        half_width = boxes[:, 2] / 2
        half_height = boxes[:, 3] / 2
        corners = numpy.stack(
            [
                boxes[:, 0] - half_width,
                boxes[:, 1] - half_height,
                boxes[:, 0] + half_width,
                boxes[:, 1] + half_height,
            ],
            axis=1,
        )
        # A box may extend past the frame where the object does; the camera page
        # draws these, so clamp them to something drawable. Clipping and scaling
        # go in one assignment because `corners[:, [0, 2]]` is a copy -- writing
        # through `out=` on it lands in a temporary and leaves the box unclamped.
        corners[:, [0, 2]] = numpy.clip((corners[:, [0, 2]] - offset[0]) / gain, 0, size[0])
        corners[:, [1, 3]] = numpy.clip((corners[:, [1, 3]] - offset[1]) / gain, 0, size[1])
        return corners

    def _suppress(self, boxes: Any, scores: Any, classes: Any, numpy: Any) -> list[int]:
        """Per-class non-maximum suppression, in the order the caller will read.

        Per class rather than across all of them, because a cup standing on a book
        is two overlapping detections of two different things, and suppressing by
        overlap alone would drop one of them.
        """

        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        kept: list[int] = []
        for label in numpy.unique(classes):
            members = numpy.flatnonzero(classes == label)
            order = members[scores[members].argsort()[::-1]]
            while order.size:
                current = int(order[0])
                kept.append(current)
                if order.size == 1:
                    break
                rest = order[1:]
                left = numpy.maximum(boxes[current, 0], boxes[rest, 0])
                top = numpy.maximum(boxes[current, 1], boxes[rest, 1])
                right = numpy.minimum(boxes[current, 2], boxes[rest, 2])
                bottom = numpy.minimum(boxes[current, 3], boxes[rest, 3])
                overlap = numpy.clip(right - left, 0, None) * numpy.clip(bottom - top, 0, None)
                union = areas[current] + areas[rest] - overlap
                # A zero-area box would divide by zero rather than raise, and the
                # warning it prints belongs to nobody.
                iou = numpy.where(union > 0, overlap / numpy.where(union > 0, union, 1), 0.0)
                order = rest[iou <= self.iou]
        kept.sort(key=lambda index: float(scores[index]), reverse=True)
        return kept[:MAX_DETECTIONS]
