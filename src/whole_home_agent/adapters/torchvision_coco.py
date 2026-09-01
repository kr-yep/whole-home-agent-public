"""Hash-pinned torchvision COCO detectors for offline comparison only."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..model import ProducerRef
from ..perception import BoundingBox, Detection, VideoFrame


SUPPORTED_PACKAGE_BASE_VERSION = "0.26.0"
SUPPORTED_VARIANTS = {
    "ssdlite320_mobilenet_v3_large",
    "retinanet_resnet50_fpn_v2",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class TorchvisionCocoConfig:
    model_id: str
    variant: str
    weights_path: Path
    weights_sha256: str
    weights_bytes: int
    scored_labels: tuple[str, ...]
    package_base_version: str = SUPPORTED_PACKAGE_BASE_VERSION
    confidence_threshold: float = 0.25
    device: str = "cuda"

    def __post_init__(self) -> None:
        path = self.weights_path.resolve()
        if not path.is_file():
            raise ValueError("torchvision weights must be an existing local file")
        if path.stat().st_size != self.weights_bytes or _sha256(path) != self.weights_sha256:
            raise ValueError("torchvision weights do not match configured size/SHA-256")
        if self.variant not in SUPPORTED_VARIANTS:
            raise ValueError("unsupported torchvision detector variant")
        if self.package_base_version != SUPPORTED_PACKAGE_BASE_VERSION:
            raise ValueError("torchvision package base version must match the reviewed pin")
        if (
            not self.model_id
            or not self.scored_labels
            or len(set(self.scored_labels)) != len(self.scored_labels)
            or any(not item or item != item.strip() for item in self.scored_labels)
        ):
            raise ValueError("torchvision model ID or scored labels are invalid")
        if not math.isfinite(self.confidence_threshold) or not 0 <= self.confidence_threshold <= 1:
            raise ValueError("torchvision confidence threshold must be between zero and one")
        if self.device not in {"cpu", "cuda"}:
            raise ValueError("torchvision device must be 'cpu' or 'cuda'")


def load_torchvision_coco_configs(
    path: str | Path,
    *,
    repository_root: str | Path,
    device: str = "cuda",
) -> tuple[TorchvisionCocoConfig, ...]:
    root = Path(repository_root).resolve()
    config_path = Path(path).resolve()
    try:
        config_path.relative_to(root)
    except ValueError as error:
        raise ValueError("torchvision config must be inside the repository") from error
    document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    expected = {
        "schema_version",
        "status",
        "package_base_version",
        "license_id",
        "license_url",
        "selection_split",
        "test_tuning_allowed",
        "confidence_threshold",
        "scored_labels",
        "model",
    }
    if set(document) != expected or document.get("schema_version") != 1:
        raise ValueError("torchvision baseline config schema is invalid")
    if (
        document.get("status") != "FROZEN_BASELINE"
        or document.get("package_base_version") != SUPPORTED_PACKAGE_BASE_VERSION
        or document.get("license_id") != "BSD-3-Clause"
        or document.get("selection_split") != "validation"
        or document.get("test_tuning_allowed") is not False
    ):
        raise ValueError("torchvision baseline comparison envelope was loosened")
    scored_labels = document["scored_labels"]
    if not isinstance(scored_labels, list) or any(
        not isinstance(item, str) for item in scored_labels
    ):
        raise ValueError("torchvision scored label list is invalid")
    model_documents = document["model"]
    if not isinstance(model_documents, list) or not model_documents:
        raise ValueError("torchvision baseline config requires models")
    model_keys = {
        "model_id",
        "variant",
        "weights_url",
        "weights_path",
        "weights_bytes",
        "weights_sha256",
    }
    configs: list[TorchvisionCocoConfig] = []
    ids: set[str] = set()
    for item in model_documents:
        if not isinstance(item, dict) or set(item) != model_keys:
            raise ValueError("torchvision model config schema is invalid")
        model_id = item["model_id"]
        url = urlparse(item["weights_url"])
        relative_path = Path(item["weights_path"])
        if (
            not isinstance(model_id, str)
            or not model_id
            or model_id in ids
            or url.scheme != "https"
            or url.hostname != "download.pytorch.org"
            or relative_path.is_absolute()
            or any(part in {"", ".", ".."} for part in relative_path.parts)
        ):
            raise ValueError("torchvision model identity, URL, or path is invalid")
        ids.add(model_id)
        weights_path = (root / relative_path).resolve()
        try:
            weights_path.relative_to(root)
        except ValueError as error:
            raise ValueError("torchvision weights path escaped the repository") from error
        configs.append(
            TorchvisionCocoConfig(
                model_id=model_id,
                variant=item["variant"],
                weights_path=weights_path,
                weights_sha256=item["weights_sha256"],
                weights_bytes=item["weights_bytes"],
                scored_labels=tuple(scored_labels),
                package_base_version=document["package_base_version"],
                confidence_threshold=float(document["confidence_threshold"]),
                device=device,
            )
        )
    return tuple(configs)


class TorchvisionCocoDetector:
    """Translate one reviewed torchvision detector into canonical detections.

    The normal path constructs an architecture with no pretrained/backbone aliases,
    loads a previously hash-checked local state dict with ``weights_only=True``, and
    never calls a downloader. ``model_object`` is a contract-test seam only.
    """

    def __init__(
        self,
        config: TorchvisionCocoConfig,
        *,
        model_object: object | None = None,
        test_class_names: tuple[str, ...] | None = None,
    ):
        self._config = config
        config_payload = {
            "confidence_threshold": config.confidence_threshold,
            "device": config.device,
            "model_id": config.model_id,
            "package_base_version": config.package_base_version,
            "scored_labels": list(config.scored_labels),
            "variant": config.variant,
            "weights_sha256": config.weights_sha256,
        }
        config_hash = hashlib.sha256(
            json.dumps(config_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self._producer_ref = ProducerRef(
            component=f"torchvision-{config.variant}",
            version=config.package_base_version,
            artifact_hash=config.weights_sha256,
            config_hash=config_hash,
        )
        self._test_model = model_object is not None
        if model_object is not None:
            if not test_class_names:
                raise ValueError("test class names are required with a fake model")
            self._model = model_object
            self._class_names = test_class_names
            self._torch = None
            return
        installed = importlib.metadata.version("torchvision")
        if installed.split("+", 1)[0] != config.package_base_version:
            raise RuntimeError(
                f"installed torchvision {installed!r} disagrees with the resolved config"
            )
        import torch
        from torchvision.models.detection import (
            RetinaNet_ResNet50_FPN_V2_Weights,
            SSDLite320_MobileNet_V3_Large_Weights,
            retinanet_resnet50_fpn_v2,
            ssdlite320_mobilenet_v3_large,
        )

        if config.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("configured CUDA detector has no available CUDA device")
        if config.variant == "ssdlite320_mobilenet_v3_large":
            model = ssdlite320_mobilenet_v3_large(
                weights=None,
                weights_backbone=None,
            )
            categories = SSDLite320_MobileNet_V3_Large_Weights.COCO_V1.meta[
                "categories"
            ]
        else:
            model = retinanet_resnet50_fpn_v2(
                weights=None,
                weights_backbone=None,
            )
            categories = RetinaNet_ResNet50_FPN_V2_Weights.COCO_V1.meta["categories"]
        state_dict = torch.load(
            config.weights_path.resolve(),
            map_location="cpu",
            weights_only=True,
        )
        model.load_state_dict(state_dict, strict=True)
        model.eval()
        model.to(config.device)
        if config.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        self._model = model
        self._class_names = tuple(categories)
        self._torch = torch

    @property
    def producer_ref(self) -> ProducerRef:
        return self._producer_ref

    @property
    def device(self) -> str:
        return self._config.device

    @staticmethod
    def _array(value: object):
        try:
            value = value.detach().cpu()
        except AttributeError:
            pass
        try:
            import numpy as np
        except ImportError as error:  # pragma: no cover - supplied by the video extra.
            raise RuntimeError("torchvision adapter requires NumPy") from error
        return np.asarray(value)

    def detect(self, frame: VideoFrame) -> tuple[Detection, ...]:
        try:
            import numpy as np
        except ImportError as error:  # pragma: no cover - supplied by the video extra.
            raise RuntimeError("torchvision adapter requires NumPy") from error
        image = np.asarray(frame.rgb)
        if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
            raise ValueError("torchvision adapter requires one uint8 RGB frame")
        height, width = image.shape[:2]
        if self._test_model:
            result = self._model.predict(image)
        else:
            tensor = (
                self._torch.from_numpy(image.copy())
                .permute(2, 0, 1)
                .to(device=self._config.device, dtype=self._torch.float32)
                .div_(255.0)
            )
            with self._torch.inference_mode():
                result = self._model([tensor])[0]
        if not isinstance(result, dict) or set(result) < {"boxes", "labels", "scores"}:
            raise ValueError("torchvision detector returned an invalid result")
        boxes = self._array(result["boxes"])
        labels = self._array(result["labels"])
        scores = self._array(result["scores"])
        if (
            boxes.ndim != 2
            or boxes.shape[1:] != (4,)
            or labels.ndim != 1
            or scores.ndim != 1
            or len(boxes) != len(labels)
            or len(boxes) != len(scores)
        ):
            raise ValueError("torchvision detector returned invalid result shapes")
        allowed = set(self._config.scored_labels)
        detections: list[Detection] = []
        for box_values, class_id_value, confidence_value in zip(boxes, labels, scores):
            class_id = int(class_id_value)
            confidence = float(confidence_value)
            if class_id < 0 or class_id >= len(self._class_names):
                raise ValueError("torchvision detector returned an unknown class ID")
            label = self._class_names[class_id]
            if label not in allowed or confidence < self._config.confidence_threshold:
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
                key=lambda item: (item.label, -item.confidence, item.bbox.as_xyxy()),
            )
        )

    def peak_vram_bytes(self) -> int | None:
        if self._config.device != "cuda":
            return 0
        if self._torch is None:
            return None
        return int(self._torch.cuda.max_memory_allocated())

    def runtime_metadata(self) -> dict[str, Any]:
        metadata = {
            "model_id": self._config.model_id,
            "torch_version": _installed_version("torch"),
            "torchvision_version": _installed_version("torchvision"),
        }
        if self._config.device != "cuda" or self._torch is None:
            return {
                **metadata,
                "cuda_version": None,
                "cudnn_version": None,
                "gpu_name": None,
            }
        return {
            **metadata,
            "cuda_version": self._torch.version.cuda,
            "cudnn_version": (
                str(self._torch.backends.cudnn.version())
                if self._torch.backends.cudnn.is_available()
                else None
            ),
            "gpu_name": self._torch.cuda.get_device_name(),
        }


def _installed_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None
