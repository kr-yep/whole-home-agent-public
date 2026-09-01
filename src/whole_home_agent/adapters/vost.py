"""Strict VOST consecutive-frame adapter for offline motion screening."""

from __future__ import annotations

import hashlib
import json
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
from .motion import MotionScheduleConfig


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_SEQUENCE_RE = re.compile(r"^[0-9]+_[a-z0-9_]+$")
_FRAME_RE = re.compile(r"^frame(?P<index>[0-9]{5})$")
_ARCHIVE_HOST = "tri-ml-public.s3.amazonaws.com"
_DATASET_HOST = "www.vostdataset.org"
_REPOSITORY_HOST = "github.com"
_SPLITS = {"development", "validation"}


@dataclass(frozen=True, slots=True)
class MotionGateCriteria:
    minimum_validation_mask_change_coverage: float
    minimum_validation_avoided_detector_fraction: float
    maximum_detector_p95_ms: float
    maximum_peak_vram_bytes: int


@dataclass(frozen=True, slots=True)
class TargetTrackingCriteria:
    minimum_full_frame_recall50: float
    minimum_matched_observation_fraction: float
    maximum_id_switches: int
    maximum_fragmentations: int
    minimum_scheduled_target_event_coverage: float
    minimum_scheduled_target_event_retention: float


@dataclass(frozen=True, slots=True)
class VostSequenceSpec:
    sequence_id: str
    source_partition: str
    split: str
    frame_count: int
    frame_width: int
    frame_height: int
    source_frame_step: int
    subset_file_count: int
    subset_bytes: int
    sequence_files_manifest_sha256: str
    frame_files_manifest_sha256: str
    annotation_files_manifest_sha256: str
    label_review_source_offsets: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class VostUpstreamArtifactSpec:
    kind: str
    member: str
    path: Path
    bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class VostMotionScreenManifest:
    dataset_id: str
    dataset_version: str
    origin_url: str
    repository_url: str
    archive_url: str
    archive_version_id: str
    archive_etag: str
    archive_bytes: int
    central_directory_offset: int
    central_directory_bytes: int
    central_directory_sha256: str
    central_directory_entries: int
    license_id: str
    license_url: str
    license_source_member: str
    readme_source_member: str
    intended_use: str
    local_root: Path
    sample_fps_numerator: int
    sample_fps_denominator: int
    target_mask_id: int
    void_mask_id: int
    mask_change_iou_threshold: float
    coverage_window_frames: int
    development_candidate_motion_thresholds: tuple[float, ...]
    development_selection_minimum_mask_change_coverage: float
    subset_file_count: int
    subset_bytes: int
    subset_files_manifest_sha256: str
    upstream_artifacts: tuple[VostUpstreamArtifactSpec, ...]
    scheduler: MotionScheduleConfig
    gate: MotionGateCriteria
    target_label: str | None
    target_tracking_gate: TargetTrackingCriteria | None
    sequences: tuple[VostSequenceSpec, ...]
    config_hash: str

    def sequence(self, sequence_id: str) -> VostSequenceSpec:
        matches = [item for item in self.sequences if item.sequence_id == sequence_id]
        if len(matches) != 1:
            raise ValueError(f"unknown VOST sequence: {sequence_id!r}")
        return matches[0]


@dataclass(frozen=True, slots=True)
class _VostFrameRecord:
    image_path: Path
    mask_path: Path
    position: SourcePosition
    targets: tuple[GroundTruthObject, ...]


@dataclass(frozen=True, slots=True)
class VostMotionSequence:
    descriptor: SourceDescriptor
    split: str
    annotation_hash: str
    width: int
    height: int
    fps_numerator: int
    fps_denominator: int
    records: tuple[_VostFrameRecord, ...]
    mask_change_frames: frozenset[int]
    mask_change_ious: tuple[float, ...]
    mask_change_iou_threshold: float
    coverage_window_frames: int
    target_label: str | None

    @property
    def ground_truth(self) -> dict[int, tuple[GroundTruthObject, ...]]:
        return {
            record.position.frame_index: record.targets
            for record in self.records
            if record.position.frame_index is not None
        }

    @property
    def frame_count(self) -> int:
        return len(self.records)

    @property
    def source_diagnostics(self) -> dict[str, object]:
        return {
            "annotation_scope": (
                "single VOST transformed-object mask mapped to the explicit target label; "
                "255 is void"
                if self.target_label is not None
                else "single VOST transformed-object mask; 255 is void"
            ),
            "camera_motion_limit": (
                "egocentric camera-motion stress case, not fixed-camera transfer evidence"
            ),
            "coverage_semantics": "selected at mask-change frame or a following frame",
            "coverage_window_frames": self.coverage_window_frames,
            "mask_change_event_count": len(self.mask_change_frames),
            "mask_change_iou_threshold": self.mask_change_iou_threshold,
            "source_timing": "ordinal replay at documented 5 fps; no capture timestamp",
            "target_label": self.target_label,
        }

    def iter_frames(self) -> Iterator[VideoFrame]:
        try:
            import numpy as np
            from PIL import Image
        except ImportError as error:  # pragma: no cover - supplied by video extra.
            raise RuntimeError("VOST replay requires the video extra") from error
        for record in self.records:
            with Image.open(record.image_path) as image:
                rgb_image = image.convert("RGB")
                if rgb_image.size != (self.width, self.height):
                    raise ValueError("VOST image dimensions disagree with the manifest")
                rgb = np.asarray(rgb_image).copy()
            yield VideoFrame(position=record.position, rgb=rgb)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(rows: list[dict[str, object]]) -> str:
    payload = json.dumps(rows, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _safe_relative_path(value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field} must be a non-empty POSIX relative path")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{field} must stay within the repository")
    return path


def _https_url(value: object, *, field: str, host: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an HTTPS URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != host:
        raise ValueError(f"{field} must use {host}")
    return value


def _positive_int(value: object, *, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _unit_float(value: object, *, field: str) -> float:
    if type(value) not in {int, float} or not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{field} must be between zero and one")
    return float(value)


def load_vost_motion_screen_manifest(
    path: str | Path,
    *,
    repository_root: str | Path,
) -> VostMotionScreenManifest:
    root = Path(repository_root).resolve()
    config_path = Path(path).resolve()
    try:
        config_path.relative_to(root)
    except ValueError as error:
        raise ValueError("VOST config must be inside the repository") from error
    raw_bytes = config_path.read_bytes()
    document = tomllib.loads(raw_bytes.decode("utf-8"))
    required = {
        "schema_version",
        "dataset_id",
        "dataset_version",
        "origin_url",
        "repository_url",
        "archive_url",
        "archive_version_id",
        "archive_etag",
        "archive_bytes",
        "central_directory_offset",
        "central_directory_bytes",
        "central_directory_sha256",
        "central_directory_entries",
        "license_id",
        "license_url",
        "license_source_member",
        "readme_source_member",
        "intended_use",
        "redistribution_allowed",
        "local_root",
        "sample_fps_numerator",
        "sample_fps_denominator",
        "target_mask_id",
        "void_mask_id",
        "mask_change_iou_threshold",
        "coverage_window_frames",
        "development_candidate_motion_thresholds",
        "development_selection_minimum_mask_change_coverage",
        "subset_file_count",
        "subset_bytes",
        "subset_files_manifest_sha256",
        "upstream_artifact",
        "scheduler",
        "gate",
        "sequence",
    }
    optional = {"target_label", "target_tracking_gate"}
    if (
        not required <= set(document)
        or not set(document) <= required | optional
        or document.get("schema_version") != 1
    ):
        raise ValueError("VOST manifest top-level schema is invalid")
    has_target_label = "target_label" in document
    has_target_gate = "target_tracking_gate" in document
    if has_target_label != has_target_gate:
        raise ValueError("VOST target label and tracking gate must be declared together")
    target_label = document.get("target_label")
    if target_label is not None and (
        not isinstance(target_label, str)
        or not target_label
        or target_label != target_label.strip()
    ):
        raise ValueError("VOST target label must be a non-empty trimmed string")
    if (
        document.get("license_id") != "CC-BY-NC-SA-4.0"
        or document.get("intended_use")
        != "D0_PUBLIC_NONCOMMERCIAL_MOTION_SCREENING"
        or document.get("redistribution_allowed") is not False
    ):
        raise ValueError("VOST use envelope must remain non-commercial and local")
    archive_url = _https_url(
        document["archive_url"], field="archive_url", host=_ARCHIVE_HOST
    )
    version_id = document["archive_version_id"]
    parsed_archive = urlparse(archive_url)
    if (
        not isinstance(version_id, str)
        or not version_id
        or parsed_archive.path != "/datasets/VOST.zip"
        or parsed_archive.query
    ):
        raise ValueError("VOST archive URL/version declaration is invalid")
    origin_url = _https_url(
        document["origin_url"], field="origin_url", host=_DATASET_HOST
    )
    repository_url = _https_url(
        document["repository_url"], field="repository_url", host=_REPOSITORY_HOST
    )
    license_url = _https_url(
        document["license_url"],
        field="license_url",
        host="creativecommons.org",
    )
    local_relative = _safe_relative_path(document["local_root"], field="local_root")
    local_root = (root / local_relative).resolve()
    try:
        local_root.relative_to(root)
    except ValueError as error:
        raise ValueError("VOST local root escaped the repository") from error
    hash_fields = (
        document["central_directory_sha256"],
        document["subset_files_manifest_sha256"],
    )
    if any(not isinstance(value, str) or not _HASH_RE.fullmatch(value) for value in hash_fields):
        raise ValueError("VOST manifest SHA-256 is invalid")
    fps_numerator = _positive_int(
        document["sample_fps_numerator"], field="sample_fps_numerator"
    )
    fps_denominator = _positive_int(
        document["sample_fps_denominator"], field="sample_fps_denominator"
    )
    target_mask_id = document["target_mask_id"]
    void_mask_id = document["void_mask_id"]
    if (
        type(target_mask_id) is not int
        or type(void_mask_id) is not int
        or not 1 <= target_mask_id <= 254
        or not 1 <= void_mask_id <= 255
        or target_mask_id == void_mask_id
    ):
        raise ValueError("VOST target/void mask IDs are invalid")
    coverage_window = document["coverage_window_frames"]
    if type(coverage_window) is not int or not 0 <= coverage_window <= 10:
        raise ValueError("VOST coverage window is invalid")
    candidate_thresholds = document["development_candidate_motion_thresholds"]
    if (
        not isinstance(candidate_thresholds, list)
        or not candidate_thresholds
        or any(type(value) is not float or not 0.0 <= value <= 1.0 for value in candidate_thresholds)
        or candidate_thresholds != sorted(set(candidate_thresholds))
    ):
        raise ValueError("VOST development candidate thresholds are invalid")
    selection_minimum = _unit_float(
        document["development_selection_minimum_mask_change_coverage"],
        field="development_selection_minimum_mask_change_coverage",
    )

    artifact_documents = document["upstream_artifact"]
    expected_kinds = {"license", "readme", "train_split", "validation_split"}
    if not isinstance(artifact_documents, list) or len(artifact_documents) != 4:
        raise ValueError("VOST upstream artifact set is invalid")
    upstream_artifacts: list[VostUpstreamArtifactSpec] = []
    seen_kinds: set[str] = set()
    for item in artifact_documents:
        if not isinstance(item, dict) or set(item) != {
            "kind",
            "member",
            "path",
            "bytes",
            "sha256",
        }:
            raise ValueError("VOST upstream artifact schema is invalid")
        kind = item["kind"]
        member = item["member"]
        if (
            kind not in expected_kinds
            or kind in seen_kinds
            or not isinstance(member, str)
            or not member.startswith("VOST/")
            or ".." in member.split("/")
            or not isinstance(item["sha256"], str)
            or not _HASH_RE.fullmatch(item["sha256"])
        ):
            raise ValueError("VOST upstream artifact identity is invalid")
        seen_kinds.add(kind)
        relative_path = _safe_relative_path(item["path"], field="upstream artifact path")
        upstream_artifacts.append(
            VostUpstreamArtifactSpec(
                kind=kind,
                member=member,
                path=local_root / relative_path,
                bytes=_positive_int(item["bytes"], field="upstream artifact bytes"),
                sha256=item["sha256"],
            )
        )
    if seen_kinds != expected_kinds:
        raise ValueError("VOST upstream artifact kinds are incomplete")

    scheduler_document = document["scheduler"]
    if not isinstance(scheduler_document, dict) or set(scheduler_document) != {
        "motion_threshold",
        "min_gap_frames",
        "anchor_interval_frames",
        "sample_stride",
    }:
        raise ValueError("VOST scheduler schema is invalid")
    scheduler = MotionScheduleConfig(**scheduler_document)
    gate_document = document["gate"]
    if not isinstance(gate_document, dict) or set(gate_document) != {
        "minimum_validation_mask_change_coverage",
        "minimum_validation_avoided_detector_fraction",
        "maximum_detector_p95_ms",
        "maximum_peak_vram_bytes",
    }:
        raise ValueError("VOST gate schema is invalid")
    maximum_p95 = gate_document["maximum_detector_p95_ms"]
    if type(maximum_p95) not in {int, float} or float(maximum_p95) <= 0:
        raise ValueError("VOST detector p95 gate is invalid")
    gate = MotionGateCriteria(
        minimum_validation_mask_change_coverage=_unit_float(
            gate_document["minimum_validation_mask_change_coverage"],
            field="minimum_validation_mask_change_coverage",
        ),
        minimum_validation_avoided_detector_fraction=_unit_float(
            gate_document["minimum_validation_avoided_detector_fraction"],
            field="minimum_validation_avoided_detector_fraction",
        ),
        maximum_detector_p95_ms=float(maximum_p95),
        maximum_peak_vram_bytes=_positive_int(
            gate_document["maximum_peak_vram_bytes"],
            field="maximum_peak_vram_bytes",
        ),
    )

    target_tracking_gate = None
    if has_target_gate:
        target_gate_document = document["target_tracking_gate"]
        target_gate_keys = {
            "minimum_full_frame_recall50",
            "minimum_matched_observation_fraction",
            "maximum_id_switches",
            "maximum_fragmentations",
            "minimum_scheduled_target_event_coverage",
            "minimum_scheduled_target_event_retention",
        }
        if not isinstance(target_gate_document, dict) or set(target_gate_document) != target_gate_keys:
            raise ValueError("VOST target-tracking gate schema is invalid")
        maximum_id_switches = target_gate_document["maximum_id_switches"]
        maximum_fragmentations = target_gate_document["maximum_fragmentations"]
        if (
            type(maximum_id_switches) is not int
            or maximum_id_switches < 0
            or type(maximum_fragmentations) is not int
            or maximum_fragmentations < 0
        ):
            raise ValueError("VOST target-tracking count gates are invalid")
        target_tracking_gate = TargetTrackingCriteria(
            minimum_full_frame_recall50=_unit_float(
                target_gate_document["minimum_full_frame_recall50"],
                field="minimum_full_frame_recall50",
            ),
            minimum_matched_observation_fraction=_unit_float(
                target_gate_document["minimum_matched_observation_fraction"],
                field="minimum_matched_observation_fraction",
            ),
            maximum_id_switches=maximum_id_switches,
            maximum_fragmentations=maximum_fragmentations,
            minimum_scheduled_target_event_coverage=_unit_float(
                target_gate_document["minimum_scheduled_target_event_coverage"],
                field="minimum_scheduled_target_event_coverage",
            ),
            minimum_scheduled_target_event_retention=_unit_float(
                target_gate_document["minimum_scheduled_target_event_retention"],
                field="minimum_scheduled_target_event_retention",
            ),
        )

    sequence_documents = document["sequence"]
    if not isinstance(sequence_documents, list) or len(sequence_documents) != 2:
        raise ValueError("VOST screen requires development and validation sequences")
    sequence_keys = {
        "sequence_id",
        "source_partition",
        "split",
        "frame_count",
        "frame_width",
        "frame_height",
        "source_frame_step",
        "subset_file_count",
        "subset_bytes",
        "sequence_files_manifest_sha256",
        "frame_files_manifest_sha256",
        "annotation_files_manifest_sha256",
    }
    sequences: list[VostSequenceSpec] = []
    seen_ids: set[str] = set()
    seen_splits: set[str] = set()
    for item in sequence_documents:
        expected_sequence_keys = (
            sequence_keys | {"label_review_source_offsets"}
            if target_label is not None
            else sequence_keys
        )
        if not isinstance(item, dict) or set(item) != expected_sequence_keys:
            raise ValueError("VOST sequence schema is invalid")
        sequence_id = item["sequence_id"]
        split = item["split"]
        source_partition = item["source_partition"]
        if (
            not isinstance(sequence_id, str)
            or not _SEQUENCE_RE.fullmatch(sequence_id)
            or sequence_id in seen_ids
            or split not in _SPLITS
            or split in seen_splits
            or (split == "development" and source_partition != "train")
            or (split == "validation" and source_partition != "val")
        ):
            raise ValueError("VOST sequence identity or split is invalid")
        seen_ids.add(sequence_id)
        seen_splits.add(split)
        hashes = (
            item["sequence_files_manifest_sha256"],
            item["frame_files_manifest_sha256"],
            item["annotation_files_manifest_sha256"],
        )
        if any(not isinstance(value, str) or not _HASH_RE.fullmatch(value) for value in hashes):
            raise ValueError("VOST sequence SHA-256 is invalid")
        frame_count = _positive_int(item["frame_count"], field="frame_count")
        source_frame_step = _positive_int(
            item["source_frame_step"], field="source_frame_step"
        )
        review_offsets = item.get("label_review_source_offsets", [])
        if target_label is not None and (
            not isinstance(review_offsets, list)
            or not 2 <= len(review_offsets) <= 3
            or any(type(value) is not int for value in review_offsets)
            or review_offsets != sorted(set(review_offsets))
            or any(
                value < 0
                or value > (frame_count - 1) * source_frame_step
                or value % source_frame_step != 0
                for value in review_offsets
            )
        ):
            raise ValueError("VOST label-review offsets are invalid")
        sequences.append(
            VostSequenceSpec(
                sequence_id=sequence_id,
                source_partition=source_partition,
                split=split,
                frame_count=frame_count,
                frame_width=_positive_int(item["frame_width"], field="frame_width"),
                frame_height=_positive_int(item["frame_height"], field="frame_height"),
                source_frame_step=source_frame_step,
                subset_file_count=_positive_int(
                    item["subset_file_count"], field="subset_file_count"
                ),
                subset_bytes=_positive_int(item["subset_bytes"], field="subset_bytes"),
                sequence_files_manifest_sha256=item[
                    "sequence_files_manifest_sha256"
                ],
                frame_files_manifest_sha256=item["frame_files_manifest_sha256"],
                annotation_files_manifest_sha256=item[
                    "annotation_files_manifest_sha256"
                ],
                label_review_source_offsets=tuple(review_offsets),
            )
        )
    if seen_splits != _SPLITS:
        raise ValueError("VOST screen must freeze development and validation splits")
    return VostMotionScreenManifest(
        dataset_id=document["dataset_id"],
        dataset_version=document["dataset_version"],
        origin_url=origin_url,
        repository_url=repository_url,
        archive_url=archive_url,
        archive_version_id=version_id,
        archive_etag=document["archive_etag"],
        archive_bytes=_positive_int(document["archive_bytes"], field="archive_bytes"),
        central_directory_offset=_positive_int(
            document["central_directory_offset"], field="central_directory_offset"
        ),
        central_directory_bytes=_positive_int(
            document["central_directory_bytes"], field="central_directory_bytes"
        ),
        central_directory_sha256=document["central_directory_sha256"],
        central_directory_entries=_positive_int(
            document["central_directory_entries"], field="central_directory_entries"
        ),
        license_id=document["license_id"],
        license_url=license_url,
        license_source_member=document["license_source_member"],
        readme_source_member=document["readme_source_member"],
        intended_use=document["intended_use"],
        local_root=local_root,
        sample_fps_numerator=fps_numerator,
        sample_fps_denominator=fps_denominator,
        target_mask_id=target_mask_id,
        void_mask_id=void_mask_id,
        mask_change_iou_threshold=_unit_float(
            document["mask_change_iou_threshold"], field="mask_change_iou_threshold"
        ),
        coverage_window_frames=coverage_window,
        development_candidate_motion_thresholds=tuple(candidate_thresholds),
        development_selection_minimum_mask_change_coverage=selection_minimum,
        subset_file_count=_positive_int(
            document["subset_file_count"], field="subset_file_count"
        ),
        subset_bytes=_positive_int(document["subset_bytes"], field="subset_bytes"),
        subset_files_manifest_sha256=document["subset_files_manifest_sha256"],
        upstream_artifacts=tuple(upstream_artifacts),
        scheduler=scheduler,
        gate=gate,
        target_label=target_label,
        target_tracking_gate=target_tracking_gate,
        sequences=tuple(sequences),
        config_hash=hashlib.sha256(raw_bytes).hexdigest(),
    )


def _read_subset_rows(manifest: VostMotionScreenManifest) -> list[dict[str, object]]:
    path = manifest.local_root / "subset-manifest.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("VOST subset manifest is missing or unreadable") from error
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "dataset",
        "license",
        "source_url",
        "sequences",
        "file_count",
        "files",
        "files_manifest_sha256",
    }:
        raise ValueError("VOST subset manifest schema is invalid")
    rows = document["files"]
    expected_sequences = {
        item.split: item.sequence_id for item in manifest.sequences
    }
    if (
        document["schema_version"] != 1
        or document["dataset"] != "VOST"
        or document["license"] != "CC BY-NC-SA 4.0"
        or document["source_url"] != manifest.archive_url
        or document["sequences"] != expected_sequences
        or document["file_count"] != manifest.subset_file_count
        or not isinstance(rows, list)
        or len(rows) != manifest.subset_file_count
    ):
        raise ValueError("VOST subset manifest identity or count is invalid")
    if any(
        not isinstance(row, dict)
        or set(row) != {"member", "bytes", "crc32", "sha256", "split", "sequence"}
        or not isinstance(row["member"], str)
        or type(row["bytes"]) is not int
        or row["bytes"] <= 0
        or not isinstance(row["crc32"], str)
        or not re.fullmatch(r"[0-9a-f]{8}", row["crc32"])
        or not isinstance(row["sha256"], str)
        or not _HASH_RE.fullmatch(row["sha256"])
        or row["split"] not in _SPLITS
        or not isinstance(row["sequence"], str)
        for row in rows
    ):
        raise ValueError("VOST subset file receipt schema is invalid")
    canonical = _canonical_hash(rows)
    if (
        canonical != manifest.subset_files_manifest_sha256
        or document["files_manifest_sha256"] != canonical
        or sum(row["bytes"] for row in rows) != manifest.subset_bytes
    ):
        raise ValueError("VOST subset manifest failed aggregate verification")
    return rows


def _verify_upstream_artifacts(manifest: VostMotionScreenManifest) -> dict[str, bytes]:
    verified: dict[str, bytes] = {}
    for artifact in manifest.upstream_artifacts:
        try:
            artifact.path.relative_to(manifest.local_root)
        except ValueError as error:
            raise ValueError("VOST upstream artifact escaped the local data root") from error
        if (
            not artifact.path.is_file()
            or artifact.path.stat().st_size != artifact.bytes
            or _sha256(artifact.path) != artifact.sha256
        ):
            raise ValueError(f"VOST upstream artifact failed verification: {artifact.kind}")
        verified[artifact.kind] = artifact.path.read_bytes()
    by_kind = {item.kind: item for item in manifest.upstream_artifacts}
    if (
        by_kind["license"].member != manifest.license_source_member
        or by_kind["readme"].member != manifest.readme_source_member
        or b"CC BY-NC-SA 4.0" not in verified["readme"]
        or b"Attribution-NonCommercial-ShareAlike 4.0" not in verified["license"]
    ):
        raise ValueError("VOST upstream license evidence disagrees with the config")
    return verified


def load_vost_motion_sequence(
    manifest: VostMotionScreenManifest,
    sequence_id: str,
) -> VostMotionSequence:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as error:  # pragma: no cover - supplied by video extra.
        raise RuntimeError("VOST replay requires the video extra") from error
    spec = manifest.sequence(sequence_id)
    upstream = _verify_upstream_artifacts(manifest)
    split_kind = "train_split" if spec.source_partition == "train" else "validation_split"
    split_ids = {
        line.strip()
        for line in upstream[split_kind].decode("utf-8").splitlines()
        if line.strip()
    }
    if sequence_id not in split_ids:
        raise ValueError("VOST sequence is absent from the declared upstream split")
    all_rows = _read_subset_rows(manifest)
    rows = [row for row in all_rows if row["sequence"] == sequence_id]
    frame_rows = [row for row in rows if f"VOST/JPEGImages/{sequence_id}/" in row["member"]]
    mask_rows = [row for row in rows if f"VOST/Annotations/{sequence_id}/" in row["member"]]
    if (
        len(rows) != spec.subset_file_count
        or sum(row["bytes"] for row in rows) != spec.subset_bytes
        or _canonical_hash(rows) != spec.sequence_files_manifest_sha256
        or _canonical_hash(frame_rows) != spec.frame_files_manifest_sha256
        or _canonical_hash(mask_rows) != spec.annotation_files_manifest_sha256
        or len(frame_rows) != spec.frame_count
        or len(mask_rows) != spec.frame_count
    ):
        raise ValueError("VOST sequence receipts disagree with the frozen config")
    row_by_member = {str(row["member"]): row for row in rows}
    if len(row_by_member) != len(rows):
        raise ValueError("VOST sequence contains duplicate member receipts")

    records: list[_VostFrameRecord] = []
    previous_target = None
    change_ious: list[float] = []
    change_frames: set[int] = set()
    for local_index in range(spec.frame_count):
        source_offset = local_index * spec.source_frame_step
        stem = f"frame{source_offset:05d}"
        image_member = f"VOST/JPEGImages/{sequence_id}/{stem}.jpg"
        mask_member = f"VOST/Annotations/{sequence_id}/{stem}.png"
        image_row = row_by_member.get(image_member)
        mask_row = row_by_member.get(mask_member)
        if image_row is None or mask_row is None or _FRAME_RE.fullmatch(stem) is None:
            raise ValueError("VOST frame/mask names are not consecutive or aligned")
        image_path = (manifest.local_root / Path(*image_member.split("/"))).resolve()
        mask_path = (manifest.local_root / Path(*mask_member.split("/"))).resolve()
        for artifact_path, row in ((image_path, image_row), (mask_path, mask_row)):
            try:
                artifact_path.relative_to(manifest.local_root)
            except ValueError as error:
                raise ValueError("VOST artifact escaped the local data root") from error
            if (
                not artifact_path.is_file()
                or artifact_path.stat().st_size != row["bytes"]
                or _sha256(artifact_path) != row["sha256"]
            ):
                raise ValueError(f"VOST artifact failed size/hash verification: {artifact_path.name}")
        with Image.open(image_path) as image:
            if image.size != (spec.frame_width, spec.frame_height):
                raise ValueError("VOST image dimensions disagree with the frozen config")
        with Image.open(mask_path) as image:
            if image.size != (spec.frame_width, spec.frame_height):
                raise ValueError("VOST mask dimensions disagree with the frozen config")
            mask = np.asarray(image)
        values = {int(value) for value in np.unique(mask)}
        if not values <= {0, manifest.target_mask_id, manifest.void_mask_id}:
            raise ValueError("VOST mask contains an undeclared object ID")
        target = mask == manifest.target_mask_id
        if target.any() and manifest.target_label is not None:
            y_coordinates, x_coordinates = np.nonzero(target)
            targets = (
                GroundTruthObject(
                    entity_id=f"{sequence_id}:target-mask-{manifest.target_mask_id}",
                    label=manifest.target_label,
                    bbox=BoundingBox(
                        x_min=float(x_coordinates.min()),
                        y_min=float(y_coordinates.min()),
                        x_max=float(x_coordinates.max() + 1),
                        y_max=float(y_coordinates.max() + 1),
                    ),
                ),
            )
        else:
            targets = ()
        if previous_target is not None:
            intersection = int(np.logical_and(previous_target, target).sum())
            union = int(np.logical_or(previous_target, target).sum())
            iou = float(intersection / union) if union else 1.0
            change_ious.append(iou)
            if iou < manifest.mask_change_iou_threshold:
                change_frames.add(local_index)
        previous_target = target
        records.append(
            _VostFrameRecord(
                image_path=image_path,
                mask_path=mask_path,
                position=SourcePosition(
                    source_sequence=local_index,
                    source_offset=source_offset,
                    timestamp_basis=TimestampBasis.SOURCE_FRAME_INDEX,
                    frame_index=local_index,
                    pts=local_index,
                    time_base_numerator=manifest.sample_fps_denominator,
                    time_base_denominator=manifest.sample_fps_numerator,
                ),
                targets=targets,
            )
        )
    if set(row_by_member) != {
        f"VOST/JPEGImages/{sequence_id}/frame{index * spec.source_frame_step:05d}.jpg"
        for index in range(spec.frame_count)
    } | {
        f"VOST/Annotations/{sequence_id}/frame{index * spec.source_frame_step:05d}.png"
        for index in range(spec.frame_count)
    }:
        raise ValueError("VOST sequence contains undeclared files")
    descriptor = SourceDescriptor(
        source_id=f"vost:{sequence_id}",
        source_revision=manifest.dataset_version,
        source_kind=SourceKind.RECORDED_FRAME_SET,
        use_class=UseClass.D0_PUBLIC,
        timestamp_basis=TimestampBasis.SOURCE_FRAME_INDEX,
        content_hash=spec.sequence_files_manifest_sha256,
        license_manifest_id=f"vost-{manifest.license_id.lower()}@{manifest.dataset_version}",
        world_scope=f"public-dataset:{manifest.dataset_id}/{sequence_id}",
    )
    return VostMotionSequence(
        descriptor=descriptor,
        split=spec.split,
        annotation_hash=spec.annotation_files_manifest_sha256,
        width=spec.frame_width,
        height=spec.frame_height,
        fps_numerator=manifest.sample_fps_numerator,
        fps_denominator=manifest.sample_fps_denominator,
        records=tuple(records),
        mask_change_frames=frozenset(change_frames),
        mask_change_ious=tuple(change_ious),
        mask_change_iou_threshold=manifest.mask_change_iou_threshold,
        coverage_window_frames=manifest.coverage_window_frames,
        target_label=manifest.target_label,
    )
