"""Hash-pinned, offline RF-DETR adapter with canonical result translation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..model import ProducerRef
from ..perception import BoundingBox, Detection, VideoFrame


SUPPORTED_PACKAGE_VERSION = "1.9.4"


@dataclass(frozen=True, slots=True)
class RFDetrConfig:
    """Resolved local model configuration; no alias may trigger a download."""

    weights_path: Path
    weights_sha256: str
    class_names: tuple[str, ...]
    model_variant: str = "nano"
    package_version: str = SUPPORTED_PACKAGE_VERSION
    confidence_threshold: float = 0.35
    device: str = "cuda"
    optimize_for_inference: bool = True

    def __post_init__(self) -> None:
        path = self.weights_path.resolve()
        if not path.is_file():
            raise ValueError("RF-DETR weights must be an existing local file")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != self.weights_sha256:
            raise ValueError("RF-DETR weights do not match the configured SHA-256")
        if self.model_variant != "nano":
            raise ValueError("only the reviewed Apache-2.0 RF-DETR Nano variant is allowed")
        if self.package_version != SUPPORTED_PACKAGE_VERSION:
            raise ValueError("RF-DETR package version must match the reviewed pin")
        if (
            not self.class_names
            or len(set(self.class_names)) != len(self.class_names)
            or any(not name or name != name.strip() for name in self.class_names)
        ):
            raise ValueError("RF-DETR class names must be unique non-empty strings")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("RF-DETR confidence threshold must be between zero and one")
        if self.device not in {"cpu", "cuda"}:
            raise ValueError("RF-DETR device must be 'cpu' or 'cuda'")


class RFDetrDetector:
    """Translate RF-DETR SDK results without exposing SDK-native values.

    The normal constructor verifies a local artifact before importing RF-DETR.
    ``model_object`` exists only for adapter contract tests and does not relax the
    artifact hash requirement.
    """

    def __init__(self, config: RFDetrConfig, *, model_object: object | None = None):
        self._config = config
        config_payload = asdict(config)
        config_payload["weights_path"] = config.weights_path.resolve().as_posix()
        config_hash = hashlib.sha256(
            json.dumps(config_payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        self._producer_ref = ProducerRef(
            component="rfdetr-nano",
            version=config.package_version,
            artifact_hash=config.weights_sha256,
            config_hash=config_hash,
        )
        if model_object is None:
            installed = importlib.metadata.version("rfdetr")
            if installed != config.package_version:
                raise RuntimeError(
                    f"installed rfdetr {installed!r} disagrees with the resolved config"
                )
            from rfdetr import RFDETRNano

            # An explicit path with a directory component prevents the package's
            # bare-name cache/download resolution. The SHA-256 check above happens
            # before any third-party checkpoint loader is invoked.
            model_object = RFDETRNano(
                pretrain_weights=str(config.weights_path.resolve()),
                device=config.device,
                trust_checkpoint=False,
            )
            if config.optimize_for_inference:
                model_object.optimize_for_inference()
        self._model = model_object

    @property
    def producer_ref(self) -> ProducerRef:
        return self._producer_ref

    @property
    def device(self) -> str:
        return self._config.device

    def detect(self, frame: VideoFrame) -> tuple[Detection, ...]:
        try:
            import numpy as np
            from PIL import Image
        except ImportError as error:  # pragma: no cover - video extra supplies these.
            raise RuntimeError("RF-DETR adapter requires the video extra") from error
        image_array = np.asarray(frame.rgb)
        if image_array.ndim != 3 or image_array.shape[2] != 3:
            raise ValueError("RF-DETR adapter requires one RGB frame")
        height, width = image_array.shape[:2]
        result = self._model.predict(
            Image.fromarray(image_array), threshold=self._config.confidence_threshold
        )
        boxes = np.asarray(result.xyxy)
        confidences = np.asarray(result.confidence)
        class_ids = np.asarray(result.class_id)
        if (
            boxes.ndim != 2
            or boxes.shape[1:] != (4,)
            or len(boxes) != len(confidences)
            or len(boxes) != len(class_ids)
        ):
            raise ValueError("RF-DETR returned an invalid result shape")
        detections: list[Detection] = []
        for box_values, confidence_value, class_id_value in zip(
            boxes, confidences, class_ids
        ):
            class_id = int(class_id_value)
            confidence = float(confidence_value)
            if class_id < 0 or class_id >= len(self._config.class_names):
                raise ValueError("RF-DETR returned a class outside the configured map")
            if confidence < self._config.confidence_threshold:
                continue
            x_min, y_min, x_max, y_max = (float(value) for value in box_values)
            x_min = min(max(0.0, x_min), float(width))
            y_min = min(max(0.0, y_min), float(height))
            x_max = min(max(0.0, x_max), float(width))
            y_max = min(max(0.0, y_max), float(height))
            if x_max <= x_min or y_max <= y_min:
                continue
            detections.append(
                Detection(
                    label=self._config.class_names[class_id],
                    confidence=confidence,
                    bbox=BoundingBox(x_min, y_min, x_max, y_max),
                    position=frame.position,
                    producer_ref=self._producer_ref,
                )
            )
        return tuple(
            sorted(
                detections,
                key=lambda item: (
                    item.label,
                    -item.confidence,
                    item.bbox.as_xyxy(),
                ),
            )
        )

    def peak_vram_bytes(self) -> int | None:
        if self._config.device != "cuda":
            return 0
        try:
            import torch

            return int(torch.cuda.max_memory_allocated())
        except (ImportError, RuntimeError):
            return None

    def runtime_metadata(self) -> dict[str, Any]:
        if self._config.device != "cuda":
            return {
                "cuda_version": None,
                "cudnn_version": None,
                "gpu_name": None,
                "torch_version": _installed_version("torch"),
            }
        try:
            import torch

            return {
                "cuda_version": torch.version.cuda,
                "cudnn_version": (
                    str(torch.backends.cudnn.version())
                    if torch.backends.cudnn.is_available()
                    else None
                ),
                "gpu_name": torch.cuda.get_device_name(),
                "torch_version": torch.__version__,
            }
        except (ImportError, RuntimeError):
            return {
                "cuda_version": None,
                "cudnn_version": None,
                "gpu_name": None,
                "torch_version": _installed_version("torch"),
            }


def _installed_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None
