"""Test-only detector backed by exact synthetic annotations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from ..model import ProducerRef
from ..perception import BoundingBox, Detection, VideoFrame
from ..video_manifest import VideoSourceManifest


@dataclass(frozen=True, slots=True)
class _AnnotatedObject:
    label: str
    bbox: BoundingBox


class AnnotationOracleDetector:
    """Exercise plumbing without claiming pixel-based perception quality.

    Construction requires an explicit ``test_only=True`` acknowledgement so this
    adapter cannot be mistaken for a deployable perception implementation.
    """

    def __init__(self, manifest: VideoSourceManifest, *, test_only: bool = False):
        if not test_only:
            raise ValueError("annotation oracle requires test_only=True")
        document = json.loads(manifest.annotation_path.read_text(encoding="utf-8"))
        if (
            document.get("schema_version") != 1
            or document.get("coordinate_space") != "pixel_xyxy_exclusive"
            or document.get("width") != manifest.width
            or document.get("height") != manifest.height
        ):
            raise ValueError("annotation document disagrees with the video manifest")
        frames = document.get("frames")
        if not isinstance(frames, list) or len(frames) != manifest.frame_count:
            raise ValueError("annotation frame count is invalid")
        parsed: dict[int, tuple[_AnnotatedObject, ...]] = {}
        for expected_index, record in enumerate(frames):
            if not isinstance(record, dict) or record.get("frame_index") != expected_index:
                raise ValueError("annotation frames must be complete and ordered")
            objects = record.get("objects")
            if not isinstance(objects, dict):
                raise ValueError("annotation objects must be a mapping")
            annotations: list[_AnnotatedObject] = []
            for label, coordinates in sorted(objects.items()):
                if coordinates is None:
                    continue
                if (
                    not isinstance(label, str)
                    or not isinstance(coordinates, list)
                    or len(coordinates) != 4
                    or any(type(value) not in {int, float} for value in coordinates)
                ):
                    raise ValueError("annotation object has an invalid box")
                box = BoundingBox(*(float(value) for value in coordinates))
                if not box.within(width=manifest.width, height=manifest.height):
                    raise ValueError("annotation box exceeds original-frame bounds")
                annotations.append(_AnnotatedObject(label=label, bbox=box))
            parsed[expected_index] = tuple(annotations)
        config_payload = f"{manifest.descriptor.source_id}@{manifest.descriptor.source_revision}"
        self._producer_ref = ProducerRef(
            component="annotation-oracle-test-only",
            version="1",
            artifact_hash=manifest.annotation_hash,
            config_hash=hashlib.sha256(config_payload.encode("utf-8")).hexdigest(),
        )
        self._frames = parsed
        self._width = manifest.width
        self._height = manifest.height

    @property
    def producer_ref(self) -> ProducerRef:
        return self._producer_ref

    @property
    def device(self) -> str:
        return "annotation-oracle"

    def detect(self, frame: VideoFrame) -> tuple[Detection, ...]:
        frame_index = frame.position.frame_index
        if frame_index is None or frame_index not in self._frames:
            raise ValueError("frame is outside the oracle annotation scope")
        if getattr(frame.rgb, "shape", None) != (self._height, self._width, 3):
            raise ValueError("frame dimensions disagree with oracle scope")
        return tuple(
            Detection(
                label=item.label,
                confidence=1.0,
                bbox=item.bbox,
                position=frame.position,
                producer_ref=self._producer_ref,
            )
            for item in self._frames[frame_index]
        )

    def peak_vram_bytes(self) -> int:
        return 0

    def runtime_metadata(self) -> dict[str, object]:
        return {
            "cuda_version": None,
            "cudnn_version": None,
            "gpu_name": None,
            "torch_version": None,
        }
