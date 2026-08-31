"""Deterministic pixel detector for the generated D0 smoke replay only."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from ..model import ProducerRef
from ..perception import BoundingBox, Detection, VideoFrame


@dataclass(frozen=True, slots=True)
class ColorTarget:
    label: str
    rgb: tuple[int, int, int]
    tolerance: int
    minimum_pixels: int
    padding_left: int = 0
    padding_top: int = 0
    padding_right: int = 0
    padding_bottom: int = 0


_TOP_LEVEL_FIELDS = {"schema_version", "scope", "width", "height", "targets"}
_TARGET_FIELDS = {
    "label",
    "rgb",
    "tolerance",
    "minimum_pixels",
    "padding_left",
    "padding_top",
    "padding_right",
    "padding_bottom",
}


def load_synthetic_color_config(
    path: str | Path, *, repository_root: str | Path
) -> tuple[int, int, tuple[ColorTarget, ...]]:
    """Load the one versioned synthetic-only detector configuration."""

    root = Path(repository_root).resolve(strict=True)
    allowed_directory = (root / "configs" / "perception").resolve(strict=True)
    config_path = Path(path).resolve(strict=True)
    if config_path.parent != allowed_directory or config_path.suffix != ".toml":
        raise ValueError("synthetic detector config is outside configs/perception")
    document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    if set(document) != _TOP_LEVEL_FIELDS:
        raise ValueError("synthetic detector config does not match the closed schema")
    if document["schema_version"] != 1 or document["scope"] != "D0_SYNTHETIC_ONLY":
        raise ValueError("synthetic detector config has an unsupported scope/version")
    width = document["width"]
    height = document["height"]
    records = document["targets"]
    if (
        type(width) is not int
        or width <= 0
        or type(height) is not int
        or height <= 0
        or not isinstance(records, list)
        or not records
    ):
        raise ValueError("synthetic detector dimensions or targets are invalid")
    targets: list[ColorTarget] = []
    for record in records:
        if not isinstance(record, dict) or set(record) != _TARGET_FIELDS:
            raise ValueError("synthetic detector target does not match the closed schema")
        rgb = record["rgb"]
        if not isinstance(rgb, list) or len(rgb) != 3:
            raise ValueError("synthetic detector RGB target is invalid")
        targets.append(
            ColorTarget(
                label=record["label"],
                rgb=tuple(rgb),
                tolerance=record["tolerance"],
                minimum_pixels=record["minimum_pixels"],
                padding_left=record["padding_left"],
                padding_top=record["padding_top"],
                padding_right=record["padding_right"],
                padding_bottom=record["padding_bottom"],
            )
        )
    return width, height, tuple(targets)


class SyntheticColorDetector:
    """A measured pixel-path baseline, intentionally scoped to generated art.

    It is useful because it consumes decoded RGB rather than annotations or event
    labels. It is not evidence that color thresholding transfers to real homes.
    """

    def __init__(
        self,
        *,
        width: int,
        height: int,
        targets: tuple[ColorTarget, ...],
    ) -> None:
        if width <= 0 or height <= 0 or not targets:
            raise ValueError("synthetic color detector configuration is invalid")
        labels = [target.label for target in targets]
        if len(labels) != len(set(labels)):
            raise ValueError("synthetic color target labels must be unique")
        for target in targets:
            if (
                type(target.label) is not str
                or not target.label
                or target.label != target.label.strip()
                or any(type(channel) is not int or not 0 <= channel <= 255 for channel in target.rgb)
                or type(target.tolerance) is not int
                or target.tolerance < 0
                or type(target.minimum_pixels) is not int
                or target.minimum_pixels <= 0
                or any(
                    type(value) is not int
                    for value in (
                        target.padding_left,
                        target.padding_top,
                        target.padding_right,
                        target.padding_bottom,
                    )
                )
                or min(
                    target.padding_left,
                    target.padding_top,
                    target.padding_right,
                    target.padding_bottom,
                )
                < 0
            ):
                raise ValueError("synthetic color target is invalid")
        config = {
            "coordinate_space": "pixel_xyxy_exclusive",
            "height": height,
            "targets": [asdict(target) for target in targets],
            "width": width,
        }
        source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        config_hash = hashlib.sha256(
            json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self._producer_ref = ProducerRef(
            component="synthetic-color-detector",
            version="1",
            artifact_hash=source_hash,
            config_hash=config_hash,
        )
        self._width = width
        self._height = height
        self._targets = targets

    @property
    def producer_ref(self) -> ProducerRef:
        return self._producer_ref

    @property
    def device(self) -> str:
        return "cpu"

    def detect(self, frame: VideoFrame) -> tuple[Detection, ...]:
        try:
            import numpy as np
        except ImportError as error:  # pragma: no cover - covered by optional CI job.
            raise RuntimeError("synthetic detector requires the video extra") from error
        image = np.asarray(frame.rgb)
        if image.shape != (self._height, self._width, 3):
            raise ValueError("frame dimensions disagree with detector configuration")
        # Use int32 so squaring an 8-bit color delta cannot overflow.
        pixels = image.astype(np.int32, copy=False)
        detections: list[Detection] = []
        for target in self._targets:
            color = np.asarray(target.rgb, dtype=np.int32)
            difference = pixels - color
            mask = np.sum(difference * difference, axis=2, dtype=np.int32) <= (
                target.tolerance * target.tolerance
            )
            ys, xs = np.nonzero(mask)
            if xs.size < target.minimum_pixels:
                continue
            x_min = max(0, int(xs.min()) - target.padding_left)
            y_min = max(0, int(ys.min()) - target.padding_top)
            x_max = min(self._width, int(xs.max()) + 1 + target.padding_right)
            y_max = min(self._height, int(ys.max()) + 1 + target.padding_bottom)
            box = BoundingBox(float(x_min), float(y_min), float(x_max), float(y_max))
            confidence = min(0.99, 0.5 + 0.5 * xs.size / target.minimum_pixels)
            detections.append(
                Detection(
                    label=target.label,
                    confidence=confidence,
                    bbox=box,
                    position=frame.position,
                    producer_ref=self._producer_ref,
                )
            )
        return tuple(sorted(detections, key=lambda item: item.label))

    def peak_vram_bytes(self) -> int:
        return 0

    def runtime_metadata(self) -> dict[str, object]:
        return {
            "cuda_version": None,
            "cudnn_version": None,
            "gpu_name": None,
            "torch_version": None,
        }
