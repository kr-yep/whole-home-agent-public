"""Pinned, offline D-FINE Small adapter for synthetic qualification only.

The reviewed artifact is a community conversion to Safetensors.  This module
therefore treats its byte identity and Transformers contract as engineering
evidence only; it does not inherit the original checkpoint's benchmark claims.
"""

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


SUPPORTED_TRANSFORMERS_VERSION = "5.16.1"
SUPPORTED_MODEL_REVISION = "f79e65b5fbb33ceb9d3ebba042955d7410c608f8"
EXPECTED_SCORED_CLASS_IDS = {
    39: "bottle",
    41: "cup",
    43: "knife",
    44: "spoon",
    45: "bowl",
    70: "toaster",
    72: "refrigerator",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verified_file(directory: Path, name: str, size: int, sha256: str) -> Path:
    if Path(name).name != name or name in {"", ".", ".."}:
        raise ValueError("D-FINE artifact filename is invalid")
    path = (directory / name).resolve()
    try:
        path.relative_to(directory)
    except ValueError as error:
        raise ValueError("D-FINE artifact path escaped the model directory") from error
    if (
        not path.is_file()
        or path.stat().st_size != size
        or _sha256(path) != sha256
    ):
        raise ValueError(f"D-FINE {name} does not match configured size/SHA-256")
    return path


@dataclass(frozen=True, slots=True)
class DFineConfig:
    """Resolved local snapshot; aliases and network retrieval are not supported."""

    model_dir: Path
    weights_sha256: str
    weights_bytes: int
    config_sha256: str
    config_bytes: int
    preprocessor_sha256: str
    preprocessor_bytes: int
    class_id_map: tuple[tuple[int, str], ...]
    scored_labels: tuple[str, ...]
    model_revision: str = SUPPORTED_MODEL_REVISION
    transformers_version: str = SUPPORTED_TRANSFORMERS_VERSION
    confidence_threshold: float = 0.25
    device: str = "cuda"
    inference_dtype: str = "float16"

    def __post_init__(self) -> None:
        directory = self.model_dir.resolve()
        if not directory.is_dir():
            raise ValueError("D-FINE model directory must exist locally")
        weights = _verified_file(
            directory, "model.safetensors", self.weights_bytes, self.weights_sha256
        )
        if weights.suffix != ".safetensors":
            raise ValueError("D-FINE qualification permits Safetensors only")
        config_path = _verified_file(
            directory, "config.json", self.config_bytes, self.config_sha256
        )
        preprocessor_path = _verified_file(
            directory,
            "preprocessor_config.json",
            self.preprocessor_bytes,
            self.preprocessor_sha256,
        )
        if self.model_revision != SUPPORTED_MODEL_REVISION:
            raise ValueError("D-FINE model revision must match the reviewed pin")
        if self.transformers_version != SUPPORTED_TRANSFORMERS_VERSION:
            raise ValueError("Transformers version must match the reviewed pin")

        class_ids = tuple(item[0] for item in self.class_id_map)
        class_names = tuple(item[1] for item in self.class_id_map)
        if (
            len(self.class_id_map) != 80
            or class_ids != tuple(range(80))
            or len(set(class_names)) != 80
            or any(not name or name != name.strip() for name in class_names)
            or any(dict(self.class_id_map).get(key) != value for key, value in EXPECTED_SCORED_CLASS_IDS.items())
        ):
            raise ValueError("D-FINE dense COCO class map is invalid")
        if (
            tuple(sorted(self.scored_labels))
            != tuple(sorted(EXPECTED_SCORED_CLASS_IDS.values()))
        ):
            raise ValueError("D-FINE scored-label allowlist is invalid")
        if (
            not math.isfinite(self.confidence_threshold)
            or self.confidence_threshold != 0.25
        ):
            raise ValueError("D-FINE canonical confidence threshold must remain 0.25")
        if self.device not in {"cpu", "cuda"}:
            raise ValueError("D-FINE device must be 'cpu' or 'cuda'")
        if self.inference_dtype not in {"float16", "float32"}:
            raise ValueError("D-FINE inference dtype is not reviewed")
        if self.device == "cpu" and self.inference_dtype != "float32":
            raise ValueError("D-FINE CPU inference must use float32")

        config_document = json.loads(config_path.read_text(encoding="utf-8"))
        configured_map = {
            int(key): value for key, value in config_document.get("id2label", {}).items()
        }
        if (
            config_document.get("architectures") != ["DFineForObjectDetection"]
            or config_document.get("model_type") != "d_fine"
            or config_document.get("num_queries") != 300
            or config_document.get("use_focal_loss") is not True
            or configured_map != dict(self.class_id_map)
        ):
            raise ValueError("D-FINE model config semantics are invalid")
        preprocessor = json.loads(preprocessor_path.read_text(encoding="utf-8"))
        if (
            preprocessor.get("image_processor_type") != "RTDetrImageProcessor"
            or preprocessor.get("size") != {"height": 640, "width": 640}
            or preprocessor.get("do_resize") is not True
            or preprocessor.get("do_rescale") is not True
            or preprocessor.get("rescale_factor") != 1 / 255
            or preprocessor.get("do_normalize") is not False
            or preprocessor.get("do_pad") is not False
        ):
            raise ValueError("D-FINE preprocessor semantics are invalid")


class _TransformersRuntime:
    """Keep all Transformers and Torch values inside the concrete adapter."""

    def __init__(self, config: DFineConfig):
        installed = importlib.metadata.version("transformers")
        if installed != config.transformers_version:
            raise RuntimeError(
                f"installed transformers {installed!r} disagrees with the resolved config"
            )
        import torch
        from transformers import DFineForObjectDetection, RTDetrImageProcessor

        if config.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("configured CUDA D-FINE detector has no available CUDA device")
        directory = str(config.model_dir.resolve())
        self._processor = RTDetrImageProcessor.from_pretrained(
            directory,
            local_files_only=True,
            trust_remote_code=False,
        )
        self._model = DFineForObjectDetection.from_pretrained(
            directory,
            local_files_only=True,
            trust_remote_code=False,
            use_safetensors=True,
        )
        model_map = {int(key): value for key, value in self._model.config.id2label.items()}
        if model_map != dict(config.class_id_map):
            raise RuntimeError("loaded D-FINE class map disagrees with the frozen config")
        self._model.eval()
        self._model.to(config.device)
        if config.inference_dtype == "float16":
            self._model.to(dtype=torch.float16)
        self._torch = torch
        self._device = config.device
        self._dtype = (
            torch.float16 if config.inference_dtype == "float16" else torch.float32
        )
        if config.device == "cuda":
            torch.cuda.reset_peak_memory_stats()

    def infer(self, rgb: object) -> dict[str, object]:
        import numpy as np
        from PIL import Image

        image = np.asarray(rgb)
        height, width = image.shape[:2]
        inputs = self._processor(images=Image.fromarray(image), return_tensors="pt")
        prepared = {
            key: (
                value.to(self._device, dtype=self._dtype)
                if value.is_floating_point()
                else value.to(self._device)
            )
            for key, value in inputs.items()
        }
        with self._torch.inference_mode():
            outputs = self._model(**prepared)
        result = self._processor.post_process_object_detection(
            outputs,
            threshold=0.0,
            target_sizes=[(height, width)],
        )[0]
        if self._device == "cuda":
            self._torch.cuda.synchronize()
        return {
            name: value.detach().cpu().numpy()
            for name, value in result.items()
            if name in {"scores", "labels", "boxes"}
        }

    def peak_vram_bytes(self) -> int:
        if self._device != "cuda":
            return 0
        return int(self._torch.cuda.max_memory_allocated())


class DFineDetector:
    """Translate dense COCO D-FINE reports into canonical detections."""

    def __init__(self, config: DFineConfig, *, runtime_object: object | None = None):
        self._config = config
        config_payload = asdict(config)
        del config_payload["model_dir"]
        config_hash = hashlib.sha256(
            json.dumps(config_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self._producer_ref = ProducerRef(
            component="dfine-small-transformers-community-conversion",
            version=f"{config.transformers_version}@{config.model_revision}",
            artifact_hash=config.weights_sha256,
            config_hash=config_hash,
        )
        self._class_id_to_name = dict(config.class_id_map)
        self._scored_labels = frozenset(config.scored_labels)
        self._runtime = runtime_object or _TransformersRuntime(config)

    @property
    def producer_ref(self) -> ProducerRef:
        return self._producer_ref

    @property
    def device(self) -> str:
        return self._config.device

    def detect(self, frame: VideoFrame) -> tuple[Detection, ...]:
        try:
            import numpy as np
        except ImportError as error:  # pragma: no cover - supplied by video extra.
            raise RuntimeError("D-FINE adapter requires NumPy") from error
        image = np.asarray(frame.rgb)
        if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
            raise ValueError("D-FINE adapter requires one RGB uint8 HWC frame")
        height, width = image.shape[:2]
        result = self._runtime.infer(image)
        if not isinstance(result, dict) or set(result) != {"scores", "labels", "boxes"}:
            raise ValueError("D-FINE runtime returned an invalid result mapping")
        scores = np.asarray(result["scores"])
        labels = np.asarray(result["labels"])
        boxes = np.asarray(result["boxes"])
        if (
            scores.ndim != 1
            or labels.ndim != 1
            or boxes.ndim != 2
            or boxes.shape[1:] != (4,)
            or len(scores) != len(labels)
            or len(scores) != len(boxes)
        ):
            raise ValueError("D-FINE runtime returned invalid output shapes")
        detections: list[Detection] = []
        for score_value, class_id_value, box_values in zip(scores, labels, boxes):
            if not np.issubdtype(type(class_id_value), np.integer):
                raise ValueError("D-FINE returned a non-integer dense class ID")
            class_id = int(class_id_value)
            if class_id not in self._class_id_to_name:
                raise ValueError("D-FINE returned an unknown dense class ID")
            label = self._class_id_to_name[class_id]
            confidence = float(score_value)
            coordinates = tuple(float(value) for value in box_values)
            if not math.isfinite(confidence) or not all(
                math.isfinite(value) for value in coordinates
            ):
                raise ValueError("D-FINE returned non-finite output")
            if (
                label not in self._scored_labels
                or confidence < self._config.confidence_threshold
            ):
                continue
            x_min, y_min, x_max, y_max = coordinates
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
        value = getattr(self._runtime, "peak_vram_bytes", None)
        if value is None:
            return 0 if self._config.device == "cpu" else None
        return int(value())

    def runtime_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "artifact_format": "safetensors",
            "artifact_provenance": "community_converted",
            "inference_dtype": self._config.inference_dtype,
            "model_revision": self._config.model_revision,
            "safetensors_version": _installed_version("safetensors"),
            "transformers_version": _installed_version("transformers"),
        }
        try:
            import torch

            metadata.update(
                {
                    "torch_version": torch.__version__,
                    "cuda_version": torch.version.cuda,
                    "cudnn_version": (
                        str(torch.backends.cudnn.version())
                        if torch.backends.cudnn.is_available()
                        else None
                    ),
                    "gpu_name": (
                        torch.cuda.get_device_name()
                        if self._config.device == "cuda" and torch.cuda.is_available()
                        else None
                    ),
                }
            )
        except (ImportError, RuntimeError):
            metadata.update(
                {
                    "torch_version": _installed_version("torch"),
                    "cuda_version": None,
                    "cudnn_version": None,
                    "gpu_name": None,
                }
            )
        return metadata


def _installed_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None
