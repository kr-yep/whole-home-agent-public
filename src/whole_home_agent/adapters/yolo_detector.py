"""YOLO object detector sink for real-time camera ingest.

Uses Ultralytics YOLO with GPU acceleration when available, running in-memory
inference without writing frames to disk (preserving the zero-retention invariant).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Common COCO class translations for household objects
COCO_TRANSLATIONS: dict[str, str] = {
    "cell phone": "手機",
    "bottle": "水瓶",
    "cup": "水杯",
    "backpack": "包包",
    "handbag": "手提包",
    "suitcase": "行李箱",
    "couch": "沙發",
    "chair": "椅子",
    "laptop": "筆記型電腦",
    "mouse": "滑鼠",
    "keyboard": "鍵盤",
    "book": "書籍",
    "clock": "時鐘",
    "scissors": "剪刀",
    "remote": "遙控器",
    "umbrella": "雨傘",
    "tie": "領帶",
    "bed": "床",
    "dining table": "餐桌",
    "tv": "電視",
}


class YoloDetector:
    """Wraps an Ultralytics YOLO model as a callable sink for CameraIngest."""

    def __init__(
        self,
        model_path: str | Path = "yolov8m.pt",
        *,
        confidence: float = 0.25,
        imgsz: int = 1280,
        device: Optional[str] = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.confidence = confidence
        self.imgsz = imgsz
        self._model: Any = None
        self._device = device
        self._load_model()

    def _load_model(self) -> None:
        try:
            from ultralytics import YOLO
            import torch

            if self._device is None:
                self._device = "cuda:0" if torch.cuda.is_available() else "cpu"

            logger.info("Loading YOLO model from %s on %s...", self.model_path, self._device)
            self._model = YOLO(str(self.model_path))
        except Exception as error:
            logger.warning("Failed to initialize Ultralytics YOLO: %s", error)
            self._model = None

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def __call__(self, payload: bytes, width: int, height: int) -> list[dict[str, Any]]:
        """In-memory inference hook. Decodes JPEG, predicts, and drops raw frame."""
        if self._model is None:
            return []

        try:
            from PIL import Image

            # In-memory PIL decode; never written to storage
            image = Image.open(io.BytesIO(payload)).convert("RGB")
            results = self._model.predict(
                image,
                verbose=False,
                conf=self.confidence,
                imgsz=self.imgsz,
                device=self._device,
            )

            detections: list[dict[str, Any]] = []
            if not results:
                return detections

            first = results[0]
            boxes = first.boxes
            if boxes is None:
                return detections

            names = first.names or {}
            for box in boxes:
                xyxy = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                raw_label = names.get(cls_id, str(cls_id))
                display_label = COCO_TRANSLATIONS.get(raw_label, raw_label)

                x = round(xyxy[0], 1)
                y = round(xyxy[1], 1)
                w = round(xyxy[2] - xyxy[0], 1)
                h = round(xyxy[3] - xyxy[1], 1)

                detections.append(
                    {
                        "box": [x, y, w, h],
                        "label": f"{display_label} ({raw_label})",
                        "raw_label": raw_label,
                        "confidence": round(conf, 2),
                    }
                )

            return detections
        except Exception as error:
            logger.error("Error during YOLO inference: %s", error)
            return []
