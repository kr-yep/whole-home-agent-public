"""Hash-pinned, offline RF-DETR adapter with canonical result translation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..model import ProducerRef
from ..perception import BoundingBox, Detection, VideoFrame


SUPPORTED_PACKAGE_VERSION = "1.9.4"
SUPPORTED_VARIANTS = {
    "nano": ("RFDETRNano", "rfdetr-nano"),
    "small": ("RFDETRSmall", "rfdetr-small"),
}


def _file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class RFDetrConfig:
    """Resolved local model configuration; no alias may trigger a download."""

    weights_path: Path
    weights_sha256: str
    weights_md5: str
    weights_bytes: int
    class_id_map: tuple[tuple[int, str], ...]
    scored_labels: tuple[str, ...]
    model_variant: str = "nano"
    package_version: str = SUPPORTED_PACKAGE_VERSION
    confidence_threshold: float = 0.35
    device: str = "cuda"
    inference_compile: bool = False
    inference_dtype: str = "float32"
    inference_inplace: bool = False

    def __post_init__(self) -> None:
        path = self.weights_path.resolve()
        if not path.is_file():
            raise ValueError("RF-DETR weights must be an existing local file")
        if (
            path.stat().st_size != self.weights_bytes
            or _file_hash(path, "sha256") != self.weights_sha256
            or _file_hash(path, "md5") != self.weights_md5
        ):
            raise ValueError("RF-DETR weights do not match configured size/hashes")
        if self.model_variant not in SUPPORTED_VARIANTS:
            raise ValueError("unsupported reviewed RF-DETR variant")
        if self.package_version != SUPPORTED_PACKAGE_VERSION:
            raise ValueError("RF-DETR package version must match the reviewed pin")
        class_ids = tuple(item[0] for item in self.class_id_map)
        class_names = tuple(item[1] for item in self.class_id_map)
        if (
            not self.class_id_map
            or any(type(item) is not int or item < 0 for item in class_ids)
            or tuple(sorted(class_ids)) != class_ids
            or len(set(class_ids)) != len(class_ids)
            or len(set(class_names)) != len(class_names)
            or any(not name or name != name.strip() for name in class_names)
        ):
            raise ValueError("RF-DETR sparse class map is invalid")
        if (
            not self.scored_labels
            or len(set(self.scored_labels)) != len(self.scored_labels)
            or any(name not in set(class_names) for name in self.scored_labels)
        ):
            raise ValueError("RF-DETR scored labels are invalid")
        if (
            not math.isfinite(self.confidence_threshold)
            or not 0.0 <= self.confidence_threshold <= 1.0
        ):
            raise ValueError("RF-DETR confidence threshold must be between zero and one")
        if self.device not in {"cpu", "cuda"}:
            raise ValueError("RF-DETR device must be 'cpu' or 'cuda'")
        if self.inference_dtype not in {"float16", "float32"}:
            raise ValueError("RF-DETR inference dtype is not reviewed")
        if self.inference_compile and self.inference_inplace:
            raise ValueError("compiled RF-DETR inference cannot be in-place")


class RFDetrDetector:
    """Translate RF-DETR SDK results without exposing SDK-native values.

    The normal constructor verifies a local artifact before importing RF-DETR.
    ``model_object`` exists only for adapter contract tests and does not relax the
    artifact hash requirement.
    """

    def __init__(self, config: RFDetrConfig, *, model_object: object | None = None):
        self._config = config
        config_payload = asdict(config)
        # The local path is an allowlisting concern at composition time, not part
        # of the portable semantic identity of identical checkpoint bytes.
        del config_payload["weights_path"]
        config_hash = hashlib.sha256(
            json.dumps(config_payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        model_symbol, producer_component = SUPPORTED_VARIANTS[config.model_variant]
        self._producer_ref = ProducerRef(
            component=producer_component,
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
            import rfdetr

            model_class = getattr(rfdetr, model_symbol)
            model_object = model_class(
                pretrain_weights=str(config.weights_path.resolve()),
                device=config.device,
                trust_checkpoint=False,
            )
            model_object.inference(
                compile=config.inference_compile,
                dtype=config.inference_dtype,
                inplace=config.inference_inplace,
            )
            if config.device == "cuda":
                import torch

                torch.cuda.reset_peak_memory_stats()
        self._model = model_object
        self._class_id_to_name = dict(config.class_id_map)
        self._scored_labels = frozenset(config.scored_labels)

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
        # RF-DETR applies ``score > threshold`` internally. Asking for the
        # preceding representable float and then applying the canonical filter
        # below gives this adapter an explicit ``score >= threshold`` contract.
        sdk_threshold = math.nextafter(
            self._config.confidence_threshold, -math.inf
        )
        result = self._model.predict(
            Image.fromarray(image_array),
            threshold=sdk_threshold,
            include_source_image=False,
        )
        boxes = np.asarray(result.xyxy)
        confidences = np.asarray(result.confidence)
        class_ids = np.asarray(result.class_id)
        result_data = getattr(result, "data", None)
        returned_names = None
        if isinstance(result_data, dict) and "class_name" in result_data:
            returned_names = np.asarray(result_data["class_name"])
        if (
            boxes.ndim != 2
            or boxes.shape[1:] != (4,)
            or len(boxes) != len(confidences)
            or len(boxes) != len(class_ids)
            or (returned_names is not None and len(boxes) != len(returned_names))
        ):
            raise ValueError("RF-DETR returned an invalid result shape")
        detections: list[Detection] = []
        for index, (box_values, confidence_value, class_id_value) in enumerate(
            zip(boxes, confidences, class_ids)
        ):
            class_id = int(class_id_value)
            confidence = float(confidence_value)
            label = self._class_id_to_name.get(class_id)
            if label is None:
                raise ValueError("RF-DETR returned a class outside the configured map")
            if returned_names is not None and str(returned_names[index]) != label:
                raise ValueError("RF-DETR class name disagrees with the frozen sparse map")
            if (
                label not in self._scored_labels
                or not math.isfinite(confidence)
                or confidence < self._config.confidence_threshold
            ):
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
                    label=label,
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
        package_metadata = {
            name.replace("-", "_") + "_version": _installed_version(name)
            for name in (
                "pydantic",
                "rfdetr",
                "supervision",
                "transformers",
            )
        }
        package_metadata.update(
            {
                "inference_compile": self._config.inference_compile,
                "inference_dtype": self._config.inference_dtype,
                "inference_inplace": self._config.inference_inplace,
                "model_variant": self._config.model_variant,
            }
        )
        if self._config.device != "cuda":
            return {
                **package_metadata,
                "cuda_version": None,
                "cudnn_version": None,
                "gpu_name": None,
                "torch_version": _installed_version("torch"),
            }
        try:
            import torch

            return {
                **package_metadata,
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
                **package_metadata,
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
