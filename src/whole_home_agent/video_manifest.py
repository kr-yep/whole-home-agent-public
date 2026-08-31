"""Closed manifest boundary for allowlisted, project-generated D0 video."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ErrorCode, SourceError
from .model import SourceDescriptor, SourceKind, TimestampBasis, UseClass


_FIELDS = frozenset(
    {
        "schema_version",
        "source_id",
        "source_revision",
        "source_kind",
        "timestamp_basis",
        "use_class",
        "path",
        "sha256",
        "license",
        "provenance",
        "frame_count",
        "width",
        "height",
        "fps",
        "annotations",
        "entities",
        "events",
        "split",
    }
)
_PROVENANCE_FIELDS = frozenset({"kind", "generator", "generator_sha256"})
_FPS_FIELDS = frozenset({"numerator", "denominator"})
_ANNOTATION_FIELDS = frozenset({"path", "sha256"})


@dataclass(frozen=True, slots=True)
class VideoSourceManifest:
    descriptor: SourceDescriptor
    manifest_path: Path
    media_path: Path
    annotation_path: Path
    annotation_hash: str
    license_id: str
    frame_count: int
    width: int
    height: int
    fps_numerator: int
    fps_denominator: int
    entities: tuple[dict[str, Any], ...]
    events: tuple[dict[str, Any], ...]
    split: str


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SourceError(
                f"duplicate manifest key: {key!r}",
                error_code=ErrorCode.INVALID_SOURCE,
            )
        result[key] = value
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object)
    except SourceError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceError(
            "video manifest is not readable strict UTF-8 JSON",
            error_code=ErrorCode.INVALID_SOURCE,
        ) from error
    if type(document) is not dict:
        raise SourceError(
            "video manifest must be a JSON object",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    return document


def _exact_fields(value: dict[str, Any], expected: frozenset[str], context: str) -> None:
    if set(value) != expected:
        raise SourceError(
            f"{context} does not match the closed schema",
            error_code=ErrorCode.INVALID_SOURCE,
            details={
                "extra": sorted(set(value) - expected),
                "missing": sorted(expected - set(value)),
            },
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_file(parent: Path, value: Any, field: str) -> Path:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or "://" in value
        or "\\" in value
        or "/" in value
        or value in {".", ".."}
    ):
        raise SourceError(
            f"{field} must name a file beside the manifest",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    resolved = (parent / value).resolve(strict=True)
    if resolved.parent != parent or not resolved.is_file():
        raise SourceError(
            f"{field} escapes the allowlisted manifest directory",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    return resolved


def _repository_file(root: Path, value: Any, field: str) -> Path:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or "://" in value
        or "\\" in value
        or value.startswith("/")
        or ".." in value.split("/")
        or (len(value) >= 2 and value[1] == ":")
    ):
        raise SourceError(
            f"{field} must be a repository-relative file",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    resolved = root.joinpath(*value.split("/")).resolve(strict=True)
    if root not in resolved.parents or not resolved.is_file():
        raise SourceError(
            f"{field} escapes the repository",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    return resolved


def _positive_int(value: Any, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise SourceError(
            f"{field} must be a positive integer",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    return value


def load_video_manifest(
    path: str | Path, *, repository_root: str | Path
) -> VideoSourceManifest:
    """Load only a manifest below ``examples/media/generated``."""

    try:
        root = Path(repository_root).resolve(strict=True)
        allowlist = (root / "examples" / "media" / "generated").resolve(strict=True)
        manifest_path = Path(path).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise SourceError(
            "video manifest or repository root does not exist",
            error_code=ErrorCode.INVALID_SOURCE,
        ) from error
    if manifest_path.parent != allowlist or not manifest_path.name.endswith(
        ".manifest.json"
    ):
        raise SourceError(
            "video manifest is outside the generated D0 allowlist",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    document = _read_json(manifest_path)
    _exact_fields(document, _FIELDS, "video manifest")
    if document["schema_version"] != 1:
        raise SourceError(
            "video manifest schema_version must be integer 1",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    if (
        document["source_kind"] != SourceKind.RECORDED_VIDEO.value
        or document["timestamp_basis"] != TimestampBasis.MEDIA_PTS.value
        or document["use_class"] != UseClass.D0_SYNTHETIC.value
        or document["split"] not in {"train", "validation", "test", "demo"}
    ):
        raise SourceError(
            "video manifest requests an unsupported source/use/time envelope",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    provenance = document["provenance"]
    fps = document["fps"]
    annotations = document["annotations"]
    if type(provenance) is not dict or type(fps) is not dict or type(annotations) is not dict:
        raise SourceError(
            "video manifest nested records have invalid types",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    _exact_fields(provenance, _PROVENANCE_FIELDS, "provenance")
    _exact_fields(fps, _FPS_FIELDS, "fps")
    _exact_fields(annotations, _ANNOTATION_FIELDS, "annotations")
    if provenance["kind"] != "project_generated_synthetic":
        raise SourceError(
            "only project-generated synthetic media is allowed",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    media_path = _relative_file(manifest_path.parent, document["path"], "path")
    annotation_path = _relative_file(
        manifest_path.parent, annotations["path"], "annotations.path"
    )
    generator_path = _repository_file(
        root, provenance["generator"], "provenance.generator"
    )
    expected_hashes = (
        (media_path, document["sha256"], "sha256"),
        (annotation_path, annotations["sha256"], "annotations.sha256"),
        (generator_path, provenance["generator_sha256"], "provenance.generator_sha256"),
    )
    for artifact, expected, field in expected_hashes:
        if type(expected) is not str or _sha256(artifact) != expected:
            raise SourceError(
                f"{field} does not match the referenced artifact",
                error_code=ErrorCode.INVALID_SOURCE,
            )
    license_id = document["license"]
    if type(license_id) is not str or license_id.casefold() in {
        "",
        "unknown",
        "unreviewed",
        "tbd",
    }:
        raise SourceError(
            "video media license is missing or unresolved",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    source_id = document["source_id"]
    revision = document["source_revision"]
    if any(
        type(value) is not str or not value or value != value.strip()
        for value in (source_id, revision)
    ):
        raise SourceError(
            "video source identity is invalid",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    entities = document["entities"]
    events = document["events"]
    if type(entities) is not list or type(events) is not list:
        raise SourceError(
            "entities and events must be arrays",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    if any(type(item) is not dict for item in entities + events):
        raise SourceError(
            "entity and event records must be JSON objects",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    descriptor = SourceDescriptor(
        source_id=source_id,
        source_revision=revision,
        source_kind=SourceKind.RECORDED_VIDEO,
        use_class=UseClass.D0_SYNTHETIC,
        timestamp_basis=TimestampBasis.MEDIA_PTS,
        content_hash=document["sha256"],
        license_manifest_id=manifest_path.relative_to(root).as_posix(),
        world_scope=f"source:{source_id}@{revision}",
    )
    return VideoSourceManifest(
        descriptor=descriptor,
        manifest_path=manifest_path,
        media_path=media_path,
        annotation_path=annotation_path,
        annotation_hash=annotations["sha256"],
        license_id=license_id,
        frame_count=_positive_int(document["frame_count"], "frame_count"),
        width=_positive_int(document["width"], "width"),
        height=_positive_int(document["height"], "height"),
        fps_numerator=_positive_int(fps["numerator"], "fps.numerator"),
        fps_denominator=_positive_int(fps["denominator"], "fps.denominator"),
        entities=tuple(dict(item) for item in entities),
        events=tuple(dict(item) for item in events),
        split=document["split"],
    )
