"""Strict VISOR sparse-frame adapter for offline, non-commercial D0 screening."""

from __future__ import annotations

import hashlib
import json
import math
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

from ..model import (
    SourceDescriptor,
    SourceKind,
    SourcePosition,
    TimestampBasis,
    UseClass,
)
from ..perception import BoundingBox, GroundTruthObject, VideoFrame


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_FRAME_RE = re.compile(r"^(?P<sequence>P\d{2}_\d+)_frame_(?P<index>\d{10})\.jpg$")
_SPLITS = {"development", "validation", "test"}
_UPSTREAM_HOST = "data.bris.ac.uk"
_BOUNDARY_TOLERANCE_PIXELS = 8.0


@dataclass(frozen=True, slots=True)
class VisorSequenceSpec:
    sequence_id: str
    split: str
    frame_count: int
    annotation_path: Path
    annotation_url: str
    annotation_bytes: int
    annotation_sha256: str
    archive_path: Path
    archive_url: str
    archive_bytes: int
    archive_sha256: str
    frames_path: Path


@dataclass(frozen=True, slots=True)
class VisorScreenManifest:
    dataset_id: str
    dataset_version: str
    origin_url: str
    repository_url: str
    license_id: str
    license_url: str
    intended_use: str
    local_root: Path
    frame_width: int
    frame_height: int
    class_mapping: tuple[tuple[str, str], ...]
    sequences: tuple[VisorSequenceSpec, ...]
    config_hash: str

    def sequence(self, sequence_id: str) -> VisorSequenceSpec:
        matches = [item for item in self.sequences if item.sequence_id == sequence_id]
        if len(matches) != 1:
            raise ValueError(f"unknown VISOR sequence: {sequence_id!r}")
        return matches[0]


@dataclass(frozen=True, slots=True)
class _FrameRecord:
    image_path: Path
    position: SourcePosition
    targets: tuple[GroundTruthObject, ...]


@dataclass(frozen=True, slots=True)
class VisorFrameSet:
    descriptor: SourceDescriptor
    split: str
    annotation_hash: str
    width: int
    height: int
    records: tuple[_FrameRecord, ...]
    boundary_clipped_objects: int
    boundary_clipped_points: int

    @property
    def frame_count(self) -> int:
        return len(self.records)

    @property
    def ground_truth(self) -> dict[int, tuple[GroundTruthObject, ...]]:
        return {
            record.position.frame_index: record.targets
            for record in self.records
            if record.position.frame_index is not None
        }

    @property
    def source_diagnostics(self) -> dict[str, object]:
        return {
            "annotation_scope": "VISOR active objects, not exhaustive scene objects",
            "boundary_clip_tolerance_pixels": _BOUNDARY_TOLERANCE_PIXELS,
            "boundary_clipped_objects": self.boundary_clipped_objects,
            "boundary_clipped_points": self.boundary_clipped_points,
            "false_positive_limit": (
                "generic-detector extra boxes can match unannotated scene objects"
            ),
            "mask_to_box": "polygon_extent_xyxy_clipped_within_declared_tolerance",
        }

    def iter_frames(self) -> Iterator[VideoFrame]:
        try:
            import numpy as np
            from PIL import Image
        except ImportError as error:  # pragma: no cover - supplied by the video extra.
            raise RuntimeError("VISOR replay requires the video extra") from error
        for record in self.records:
            with Image.open(record.image_path) as image:
                rgb_image = image.convert("RGB")
                if rgb_image.size != (self.width, self.height):
                    raise ValueError("VISOR image dimensions disagree with the manifest")
                rgb = np.asarray(rgb_image).copy()
            yield VideoFrame(position=record.position, rgb=rgb)


def _safe_relative_path(value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field} must be a non-empty POSIX relative path")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{field} must stay within the declared data root")
    return path


def _official_url(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an HTTPS URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != _UPSTREAM_HOST:
        raise ValueError(f"{field} must use the official Bristol data host")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_artifact(path: Path, *, expected_bytes: int, expected_hash: str) -> None:
    if not path.is_file():
        raise ValueError(f"required VISOR artifact is missing: {path.name}")
    if path.stat().st_size != expected_bytes or _sha256(path) != expected_hash:
        raise ValueError(f"VISOR artifact failed size/hash verification: {path.name}")


def load_visor_screen_manifest(
    path: str | Path,
    *,
    repository_root: str | Path,
) -> VisorScreenManifest:
    root = Path(repository_root).resolve()
    config_path = Path(path).resolve()
    try:
        config_path.relative_to(root)
    except ValueError as error:
        raise ValueError("VISOR config must be inside the repository") from error
    raw_bytes = config_path.read_bytes()
    document = tomllib.loads(raw_bytes.decode("utf-8"))
    required = {
        "schema_version",
        "dataset_id",
        "dataset_version",
        "origin_url",
        "repository_url",
        "license_id",
        "license_url",
        "intended_use",
        "redistribution_allowed",
        "local_root",
        "frame_width",
        "frame_height",
        "class_mapping",
        "sequence",
    }
    if set(document) != required or document.get("schema_version") != 1:
        raise ValueError("VISOR manifest top-level schema is invalid")
    if (
        document.get("license_id") != "CC-BY-NC-4.0"
        or document.get("intended_use")
        != "D0_PUBLIC_NONCOMMERCIAL_METHOD_SCREENING"
        or document.get("redistribution_allowed") is not False
    ):
        raise ValueError("VISOR license/use envelope must remain non-commercial and local")
    local_root_relative = _safe_relative_path(document["local_root"], field="local_root")
    local_root = (root / local_root_relative).resolve()
    try:
        local_root.relative_to(root)
    except ValueError as error:
        raise ValueError("VISOR local root escaped the repository") from error
    width = document["frame_width"]
    height = document["frame_height"]
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError("VISOR frame dimensions must be positive integers")
    mapping = document["class_mapping"]
    if (
        not isinstance(mapping, dict)
        or not mapping
        or any(
            not isinstance(source, str)
            or not source
            or source != source.strip()
            or not isinstance(target, str)
            or not target
            or target != target.strip()
            for source, target in mapping.items()
        )
    ):
        raise ValueError("VISOR class mapping is invalid")
    sequence_documents = document["sequence"]
    if not isinstance(sequence_documents, list) or not sequence_documents:
        raise ValueError("VISOR manifest requires sequences")
    sequences: list[VisorSequenceSpec] = []
    sequence_ids: set[str] = set()
    splits: set[str] = set()
    sequence_keys = {
        "sequence_id",
        "split",
        "frame_count",
        "annotation_path",
        "annotation_url",
        "annotation_bytes",
        "annotation_sha256",
        "archive_path",
        "archive_url",
        "archive_bytes",
        "archive_sha256",
        "frames_path",
    }
    for item in sequence_documents:
        if not isinstance(item, dict) or set(item) != sequence_keys:
            raise ValueError("VISOR sequence schema is invalid")
        sequence_id = item["sequence_id"]
        split = item["split"]
        frame_count = item["frame_count"]
        if (
            not isinstance(sequence_id, str)
            or not re.fullmatch(r"P\d{2}_\d+", sequence_id)
            or sequence_id in sequence_ids
            or split not in _SPLITS
            or split in splits
            or type(frame_count) is not int
            or frame_count <= 0
        ):
            raise ValueError("VISOR sequence identity, split, or count is invalid")
        sequence_ids.add(sequence_id)
        splits.add(split)
        hashes = (item["annotation_sha256"], item["archive_sha256"])
        sizes = (item["annotation_bytes"], item["archive_bytes"])
        if any(not isinstance(value, str) or not _HASH_RE.fullmatch(value) for value in hashes):
            raise ValueError("VISOR artifact SHA-256 is invalid")
        if any(type(value) is not int or value <= 0 for value in sizes):
            raise ValueError("VISOR artifact size is invalid")
        annotation_relative = _safe_relative_path(
            item["annotation_path"], field="annotation_path"
        )
        archive_relative = _safe_relative_path(item["archive_path"], field="archive_path")
        frames_relative = _safe_relative_path(item["frames_path"], field="frames_path")
        sequences.append(
            VisorSequenceSpec(
                sequence_id=sequence_id,
                split=split,
                frame_count=frame_count,
                annotation_path=local_root / annotation_relative,
                annotation_url=_official_url(item["annotation_url"], field="annotation_url"),
                annotation_bytes=item["annotation_bytes"],
                annotation_sha256=item["annotation_sha256"],
                archive_path=local_root / archive_relative,
                archive_url=_official_url(item["archive_url"], field="archive_url"),
                archive_bytes=item["archive_bytes"],
                archive_sha256=item["archive_sha256"],
                frames_path=local_root / frames_relative,
            )
        )
    if splits != _SPLITS:
        raise ValueError("VISOR screen must freeze one development, validation, and test source")
    return VisorScreenManifest(
        dataset_id=document["dataset_id"],
        dataset_version=document["dataset_version"],
        origin_url=document["origin_url"],
        repository_url=document["repository_url"],
        license_id=document["license_id"],
        license_url=document["license_url"],
        intended_use=document["intended_use"],
        local_root=local_root,
        frame_width=width,
        frame_height=height,
        class_mapping=tuple(sorted(mapping.items())),
        sequences=tuple(sequences),
        config_hash=hashlib.sha256(raw_bytes).hexdigest(),
    )


def _polygon_box(
    segments: object,
    *,
    width: int,
    height: int,
) -> tuple[BoundingBox, int]:
    if not isinstance(segments, list) or not segments:
        raise ValueError("VISOR object segments must be a non-empty list")
    points: list[tuple[float, float]] = []
    for polygon in segments:
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise ValueError("VISOR polygon must contain at least three points")
        for point in polygon:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(type(value) not in {int, float} for value in point)
            ):
                raise ValueError("VISOR polygon point is invalid")
            x, y = (float(value) for value in point)
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("VISOR polygon coordinate is invalid")
            if (
                x < -_BOUNDARY_TOLERANCE_PIXELS
                or y < -_BOUNDARY_TOLERANCE_PIXELS
                or x > width + _BOUNDARY_TOLERANCE_PIXELS
                or y > height + _BOUNDARY_TOLERANCE_PIXELS
            ):
                raise ValueError("VISOR polygon coordinate exceeds boundary tolerance")
            points.append((x, y))
    clipped_points = sum(
        point[0] < 0 or point[1] < 0 or point[0] > width or point[1] > height
        for point in points
    )
    x_min = max(0.0, min(point[0] for point in points))
    y_min = max(0.0, min(point[1] for point in points))
    x_max = min(float(width), max(point[0] for point in points))
    y_max = min(float(height), max(point[1] for point in points))
    box = BoundingBox(x_min, y_min, x_max, y_max)
    if not box.within(width=width, height=height):
        raise ValueError("VISOR polygon box exceeds declared dimensions")
    return box, clipped_points


def load_visor_frame_set(
    manifest: VisorScreenManifest,
    sequence_id: str,
) -> VisorFrameSet:
    spec = manifest.sequence(sequence_id)
    _verify_artifact(
        spec.annotation_path,
        expected_bytes=spec.annotation_bytes,
        expected_hash=spec.annotation_sha256,
    )
    _verify_artifact(
        spec.archive_path,
        expected_bytes=spec.archive_bytes,
        expected_hash=spec.archive_sha256,
    )
    if not spec.frames_path.is_dir():
        raise ValueError(f"extracted VISOR frames are missing: {sequence_id}")
    mapping = dict(manifest.class_mapping)
    document = json.loads(spec.annotation_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {"info", "video_annotations"}:
        raise ValueError("VISOR annotation document schema is invalid")
    records = document["video_annotations"]
    if not isinstance(records, list) or len(records) != spec.frame_count:
        raise ValueError("VISOR annotation frame count disagrees with the manifest")
    parsed_records: list[_FrameRecord] = []
    boundary_clipped_objects = 0
    boundary_clipped_points = 0
    expected_names: set[str] = set()
    last_source_index = -1
    for local_index, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != {"image", "annotations"}:
            raise ValueError("VISOR frame annotation schema is invalid")
        image = record["image"]
        annotations = record["annotations"]
        if not isinstance(image, dict) or not isinstance(annotations, list):
            raise ValueError("VISOR image or object annotations are invalid")
        name = image.get("name")
        match = _FRAME_RE.fullmatch(name) if isinstance(name, str) else None
        if match is None or match.group("sequence") != sequence_id:
            raise ValueError("VISOR frame name disagrees with the sequence")
        source_index = int(match.group("index"))
        if source_index <= last_source_index:
            raise ValueError("VISOR source frame indexes must be strictly increasing")
        last_source_index = source_index
        expected_names.add(name)
        image_path = spec.frames_path / name
        if not image_path.is_file():
            raise ValueError(f"VISOR frame is missing: {name}")
        targets: list[GroundTruthObject] = []
        entity_ids: set[str] = set()
        for annotation in annotations:
            if not isinstance(annotation, dict):
                raise ValueError("VISOR object annotation must be an object")
            source_label = annotation.get("name")
            canonical_label = mapping.get(source_label)
            if canonical_label is None:
                continue
            entity_id = annotation.get("id")
            if (
                not isinstance(entity_id, str)
                or not entity_id
                or entity_id in entity_ids
            ):
                raise ValueError("VISOR mapped object identity is invalid")
            entity_ids.add(entity_id)
            box, clipped_points = _polygon_box(
                annotation.get("segments"),
                width=manifest.frame_width,
                height=manifest.frame_height,
            )
            boundary_clipped_points += clipped_points
            boundary_clipped_objects += int(clipped_points > 0)
            targets.append(
                GroundTruthObject(
                    entity_id=f"{sequence_id}:{entity_id}",
                    label=canonical_label,
                    bbox=box,
                )
            )
        parsed_records.append(
            _FrameRecord(
                image_path=image_path,
                position=SourcePosition(
                    source_sequence=local_index,
                    source_offset=source_index,
                    timestamp_basis=TimestampBasis.SOURCE_FRAME_INDEX,
                    frame_index=local_index,
                ),
                targets=tuple(
                    sorted(targets, key=lambda target: (target.label, target.entity_id))
                ),
            )
        )
    actual_names = {
        path.name for path in spec.frames_path.rglob("*.jpg") if path.is_file()
    }
    if actual_names != expected_names:
        raise ValueError("extracted VISOR frame set disagrees with the annotations")
    descriptor = SourceDescriptor(
        source_id=f"visor:{sequence_id}",
        source_revision=manifest.dataset_version,
        source_kind=SourceKind.RECORDED_FRAME_SET,
        use_class=UseClass.D0_PUBLIC,
        timestamp_basis=TimestampBasis.SOURCE_FRAME_INDEX,
        content_hash=spec.archive_sha256,
        license_manifest_id=f"visor-{manifest.license_id.lower()}@{manifest.dataset_version}",
        world_scope=f"public-dataset:{manifest.dataset_id}/{sequence_id}",
    )
    return VisorFrameSet(
        descriptor=descriptor,
        split=spec.split,
        annotation_hash=spec.annotation_sha256,
        width=manifest.frame_width,
        height=manifest.frame_height,
        records=tuple(parsed_records),
        boundary_clipped_objects=boundary_clipped_objects,
        boundary_clipped_points=boundary_clipped_points,
    )
