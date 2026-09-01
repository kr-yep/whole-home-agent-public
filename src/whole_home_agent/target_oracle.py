"""No-media D1 target-label oracle and split conformance boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .evaluation import DetectionQuality, evaluate_detection_quality
from .model import ProducerRef, SourcePosition, TimestampBasis
from .perception import BoundingBox, Detection, GroundTruthObject


ORACLE_VERSION = "d1-target-label-oracle/1"
_ALLOWED_SPLITS = {"development", "validation", "test"}


class TargetOracleError(ValueError):
    """Fail-closed D1 contract error with a stable diagnostic code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class FrameEvaluationState(str, Enum):
    SCORED = "SCORED"
    UNKNOWN = "UNKNOWN"


class VisibilityState(str, Enum):
    VISIBLE = "VISIBLE"
    TRUNCATED = "TRUNCATED"
    OCCLUDED = "OCCLUDED"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class TransitionKind(str, Enum):
    LOCATION_CHANGE = "LOCATION_CHANGE"
    CONTAINMENT_CHANGE = "CONTAINMENT_CHANGE"


@dataclass(frozen=True, slots=True)
class SourceGroup:
    source_sequence: int
    source_sequence_id: str
    split: str
    participant_id: str
    house_room_id: str
    session_id: str
    camera_time_group_id: str
    synchronized_view_group_id: str

    def __post_init__(self) -> None:
        if type(self.source_sequence) is not int or self.source_sequence < 0:
            raise TargetOracleError(
                "INVALID_SOURCE_SEQUENCE", "source_sequence must be a non-negative integer"
            )
        if self.split not in _ALLOWED_SPLITS:
            raise TargetOracleError("INVALID_SPLIT", "split is outside the frozen set")
        for field_name in (
            "source_sequence_id",
            "participant_id",
            "house_room_id",
            "session_id",
            "camera_time_group_id",
            "synchronized_view_group_id",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value or value != value.strip():
                raise TargetOracleError(
                    "MISSING_PROTECTED_GROUP",
                    f"{field_name} must be a non-empty trimmed string",
                )

    def protected_values(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (field_name, getattr(self, field_name))
            for field_name in (
                "participant_id",
                "house_room_id",
                "session_id",
                "source_sequence_id",
                "camera_time_group_id",
                "synchronized_view_group_id",
            )
        )


@dataclass(frozen=True, slots=True)
class ReferenceInstance:
    instance_id: str
    label: str
    visibility: VisibilityState
    bbox: BoundingBox | None

    def __post_init__(self) -> None:
        for field_name in ("instance_id", "label"):
            value = getattr(self, field_name)
            if not value or value != value.strip():
                raise TargetOracleError(
                    "INVALID_INSTANCE", f"{field_name} must be a non-empty trimmed string"
                )
        requires_box = self.visibility in {
            VisibilityState.VISIBLE,
            VisibilityState.TRUNCATED,
        }
        if requires_box != (self.bbox is not None):
            raise TargetOracleError(
                "VISIBILITY_BOX_CONFLICT",
                "visible/truncated instances require a box and other states prohibit one",
            )


@dataclass(frozen=True, slots=True)
class OracleFrame:
    frame_index: int
    state: FrameEvaluationState
    instances: tuple[ReferenceInstance, ...]

    def __post_init__(self) -> None:
        if type(self.frame_index) is not int or self.frame_index < 0:
            raise TargetOracleError(
                "INVALID_FRAME_INDEX", "frame_index must be a non-negative integer"
            )
        identities = [item.instance_id for item in self.instances]
        if len(identities) != len(set(identities)):
            raise TargetOracleError(
                "DUPLICATE_INSTANCE_IDENTITY",
                "one frame cannot repeat a persistent instance identity",
            )
        if self.state is FrameEvaluationState.UNKNOWN and any(
            item.visibility in {VisibilityState.VISIBLE, VisibilityState.TRUNCATED}
            for item in self.instances
        ):
            raise TargetOracleError(
                "UNKNOWN_FRAME_HAS_SCORABLE_TARGET",
                "an unknown frame cannot contain a scored target",
            )
        if self.state is FrameEvaluationState.SCORED and any(
            item.visibility is VisibilityState.UNKNOWN for item in self.instances
        ):
            raise TargetOracleError(
                "SCORED_FRAME_HAS_UNKNOWN_INSTANCE",
                "a scored frame cannot turn an unknown instance into a negative",
            )


@dataclass(frozen=True, slots=True)
class OracleSequence:
    group: SourceGroup
    frames: tuple[OracleFrame, ...]


@dataclass(frozen=True, slots=True)
class ReferenceTransition:
    episode_id: str
    source_sequence: int
    instance_id: str
    start_frame_index: int
    end_frame_index: int
    kind: TransitionKind

    def __post_init__(self) -> None:
        if not self.episode_id or self.episode_id != self.episode_id.strip():
            raise TargetOracleError(
                "INVALID_TRANSITION", "episode_id must be a non-empty trimmed string"
            )
        if not self.instance_id or self.instance_id != self.instance_id.strip():
            raise TargetOracleError(
                "INVALID_TRANSITION", "instance_id must be a non-empty trimmed string"
            )
        if (
            type(self.start_frame_index) is not int
            or type(self.end_frame_index) is not int
            or self.start_frame_index < 0
            or self.end_frame_index <= self.start_frame_index
        ):
            raise TargetOracleError(
                "INVALID_TRANSITION", "transition bounds must be strictly increasing"
            )


@dataclass(frozen=True, slots=True)
class TargetOracleDataset:
    dataset_id: str
    width: int
    height: int
    sequences: tuple[OracleSequence, ...]
    transitions: tuple[ReferenceTransition, ...] = ()

    def __post_init__(self) -> None:
        if not self.dataset_id or self.dataset_id != self.dataset_id.strip():
            raise TargetOracleError(
                "INVALID_DATASET_ID", "dataset_id must be a non-empty trimmed string"
            )
        if type(self.width) is not int or type(self.height) is not int:
            raise TargetOracleError("INVALID_DIMENSIONS", "dimensions must be integers")
        if self.width <= 0 or self.height <= 0:
            raise TargetOracleError("INVALID_DIMENSIONS", "dimensions must be positive")
        if not self.sequences:
            raise TargetOracleError("EMPTY_DATASET", "at least one sequence is required")
        self._validate_sequences()
        self._validate_transitions()

    def _validate_sequences(self) -> None:
        sequence_numbers = [item.group.source_sequence for item in self.sequences]
        sequence_ids = [item.group.source_sequence_id for item in self.sequences]
        if len(sequence_numbers) != len(set(sequence_numbers)) or len(sequence_ids) != len(
            set(sequence_ids)
        ):
            raise TargetOracleError(
                "DUPLICATE_SOURCE_SEQUENCE", "source sequence identities must be unique"
            )
        seen_frames: set[tuple[int, int]] = set()
        labels: dict[tuple[int, str], str] = {}
        for sequence in self.sequences:
            indexes = sorted(frame.frame_index for frame in sequence.frames)
            if len(indexes) != len(set(indexes)):
                raise TargetOracleError(
                    "DUPLICATE_FRAME_IDENTITY", "frame identity is repeated"
                )
            if indexes != list(range(len(indexes))):
                raise TargetOracleError(
                    "INCOMPLETE_FRAME_ACCOUNTING",
                    "each sequence must contain every zero-based frame record exactly once",
                )
            for frame in sequence.frames:
                frame_key = (sequence.group.source_sequence, frame.frame_index)
                if frame_key in seen_frames:
                    raise TargetOracleError(
                        "DUPLICATE_FRAME_IDENTITY", "frame identity is repeated"
                    )
                seen_frames.add(frame_key)
                for instance in frame.instances:
                    identity = (sequence.group.source_sequence, instance.instance_id)
                    previous = labels.setdefault(identity, instance.label)
                    if previous != instance.label:
                        raise TargetOracleError(
                            "INSTANCE_LABEL_CONFLICT",
                            "one persistent instance changed class label within a sequence",
                        )
                    if instance.bbox is not None and not instance.bbox.within(
                        width=self.width, height=self.height
                    ):
                        raise TargetOracleError(
                            "BOX_OUT_OF_BOUNDS", "reference box exceeds frame dimensions"
                        )

    def _validate_transitions(self) -> None:
        episode_ids: set[str] = set()
        frames_by_sequence = {
            item.group.source_sequence: {frame.frame_index: frame for frame in item.frames}
            for item in self.sequences
        }
        for transition in self.transitions:
            if transition.episode_id in episode_ids:
                raise TargetOracleError(
                    "DUPLICATE_TRANSITION_IDENTITY", "transition episode is repeated"
                )
            episode_ids.add(transition.episode_id)
            frames = frames_by_sequence.get(transition.source_sequence)
            if (
                frames is None
                or transition.start_frame_index not in frames
                or transition.end_frame_index not in frames
            ):
                raise TargetOracleError(
                    "TRANSITION_FRAME_MISSING", "transition references an absent frame"
                )
            for frame_index in (
                transition.start_frame_index,
                transition.end_frame_index,
            ):
                if transition.instance_id not in {
                    item.instance_id for item in frames[frame_index].instances
                }:
                    raise TargetOracleError(
                        "TRANSITION_INSTANCE_MISSING",
                        "transition instance must be represented at both bounds",
                    )


@dataclass(frozen=True, slots=True)
class TargetOracleReport:
    oracle_version: str
    dataset_id: str
    quality: DetectionQuality
    evaluated_frame_count: int
    unknown_frame_count: int
    negative_frame_count: int
    false_positives50_per_evaluated_frame: float
    reference_transition_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "evaluated_frame_count": self.evaluated_frame_count,
            "false_positives50_per_evaluated_frame": (
                self.false_positives50_per_evaluated_frame
            ),
            "negative_frame_count": self.negative_frame_count,
            "oracle_version": self.oracle_version,
            "quality": self.quality.as_dict(),
            "reference_transition_count": self.reference_transition_count,
            "unknown_frame_count": self.unknown_frame_count,
        }


@dataclass(frozen=True, slots=True)
class LoadedTargetOracleFixture:
    fixture_id: str
    use_class: str
    dataset: TargetOracleDataset
    split_groups: tuple[SourceGroup, ...]
    prediction_cases: tuple[tuple[str, tuple[Detection, ...]], ...]

    def predictions_for(self, case_id: str) -> tuple[Detection, ...]:
        matches = [items for name, items in self.prediction_cases if name == case_id]
        if len(matches) != 1:
            raise TargetOracleError(
                "UNKNOWN_PREDICTION_CASE", "prediction case must exist exactly once"
            )
        return matches[0]


def validate_source_group_splits(groups: tuple[SourceGroup, ...]) -> None:
    """Reject reuse of any protected source-group value across splits."""

    if not groups:
        raise TargetOracleError("EMPTY_SPLIT_MANIFEST", "at least one group is required")
    seen_sequence_numbers: set[int] = set()
    seen_sequence_ids: set[str] = set()
    split_by_protected_value: dict[tuple[str, str], str] = {}
    for group in groups:
        if group.source_sequence in seen_sequence_numbers:
            raise TargetOracleError(
                "DUPLICATE_SOURCE_SEQUENCE", "split manifest repeats a source sequence"
            )
        seen_sequence_numbers.add(group.source_sequence)
        for field_name, value in group.protected_values():
            identity = (field_name, value)
            previous = split_by_protected_value.setdefault(identity, group.split)
            if previous != group.split:
                raise TargetOracleError(
                    "PROTECTED_GROUP_SPLIT_LEAKAGE",
                    f"{field_name} value appears in both {previous} and {group.split}",
                )
        if group.source_sequence_id in seen_sequence_ids:
            raise TargetOracleError(
                "DUPLICATE_SOURCE_SEQUENCE", "split manifest repeats a source sequence"
            )
        seen_sequence_ids.add(group.source_sequence_id)


def evaluate_target_oracle(
    dataset: TargetOracleDataset,
    predictions: tuple[Detection, ...],
) -> TargetOracleReport:
    """Validate D1 scoring scope, then reuse the canonical pure quality calculator."""

    frame_by_key: dict[tuple[int, int], OracleFrame] = {}
    for sequence in dataset.sequences:
        for frame in sequence.frames:
            frame_by_key[(sequence.group.source_sequence, frame.frame_index)] = frame

    scored_keys = sorted(
        key for key, frame in frame_by_key.items() if frame.state is FrameEvaluationState.SCORED
    )
    if not scored_keys:
        raise TargetOracleError("NO_SCORED_FRAMES", "evaluation needs a scored frame")
    flat_index = {key: index for index, key in enumerate(scored_keys)}
    ground_truth: dict[int, tuple[GroundTruthObject, ...]] = {}
    negative_frames = 0
    for key in scored_keys:
        targets = tuple(
            GroundTruthObject(
                entity_id=item.instance_id,
                label=item.label,
                bbox=item.bbox,
            )
            for item in frame_by_key[key].instances
            if item.visibility in {VisibilityState.VISIBLE, VisibilityState.TRUNCATED}
            and item.bbox is not None
        )
        if not targets:
            negative_frames += 1
        ground_truth[flat_index[key]] = targets
    if not any(ground_truth.values()):
        raise TargetOracleError("NO_SCORABLE_TARGETS", "evaluation needs a scored target")

    grouped_predictions: dict[int, list[Detection]] = {
        index: [] for index in range(len(scored_keys))
    }
    for detection in predictions:
        position = detection.position
        if (
            position.timestamp_basis is not TimestampBasis.SOURCE_FRAME_INDEX
            or position.frame_index is None
            or position.source_offset != position.frame_index
        ):
            raise TargetOracleError(
                "INVALID_PREDICTION_POSITION",
                "predictions require source-frame-index positions with matching offset",
            )
        key = (position.source_sequence, position.frame_index)
        frame = frame_by_key.get(key)
        if frame is None:
            raise TargetOracleError(
                "PREDICTION_FRAME_MISSING", "prediction references an absent frame"
            )
        if frame.state is not FrameEvaluationState.SCORED:
            raise TargetOracleError(
                "PREDICTION_ON_UNSCORED_FRAME",
                "predictions on unknown frames cannot be silently ignored or scored",
            )
        if not detection.bbox.within(width=dataset.width, height=dataset.height):
            raise TargetOracleError(
                "BOX_OUT_OF_BOUNDS", "prediction box exceeds frame dimensions"
            )
        grouped_predictions[flat_index[key]].append(detection)

    canonical_predictions = {
        index: tuple(
            sorted(
                items,
                key=lambda item: (
                    -item.confidence,
                    item.label,
                    item.bbox.as_xyxy(),
                    item.producer_ref.identity_payload(),
                ),
            )
        )
        for index, items in grouped_predictions.items()
    }
    quality = evaluate_detection_quality(
        ground_truth,
        canonical_predictions,
        frame_width=dataset.width,
        frame_height=dataset.height,
    )
    return TargetOracleReport(
        oracle_version=ORACLE_VERSION,
        dataset_id=dataset.dataset_id,
        quality=quality,
        evaluated_frame_count=len(scored_keys),
        unknown_frame_count=len(frame_by_key) - len(scored_keys),
        negative_frame_count=negative_frames,
        false_positives50_per_evaluated_frame=(
            quality.false_positives50 / len(scored_keys)
        ),
        reference_transition_count=len(dataset.transitions),
    )


def load_target_oracle_fixture(path: str | Path) -> LoadedTargetOracleFixture:
    """Load the bounded synthetic JSON fixture without media or hidden I/O."""

    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "schema_version must be one")
    fixture_id = _strict_string(document, "fixture_id")
    use_class = _strict_string(document, "use_class")
    if use_class != "D0_SYNTHETIC":
        raise TargetOracleError(
            "INVALID_FIXTURE_USE_CLASS", "D1 oracle fixtures must be synthetic"
        )
    dataset_document = document.get("dataset")
    if not isinstance(dataset_document, dict):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "dataset must be an object")
    width = _strict_int(dataset_document, "width")
    height = _strict_int(dataset_document, "height")
    sequences_document = dataset_document.get("sequences")
    if not isinstance(sequences_document, list):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "sequences must be a list")
    sequences = tuple(_parse_sequence(item) for item in sequences_document)
    transitions_document = dataset_document.get("transitions", [])
    if not isinstance(transitions_document, list):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "transitions must be a list")
    transitions = tuple(_parse_transition(item) for item in transitions_document)
    dataset = TargetOracleDataset(
        dataset_id=_strict_string(dataset_document, "dataset_id"),
        width=width,
        height=height,
        sequences=sequences,
        transitions=transitions,
    )

    split_document = document.get("split_groups")
    if not isinstance(split_document, list):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "split_groups must be a list")
    split_groups = tuple(_parse_source_group(item) for item in split_document)

    cases_document = document.get("prediction_cases")
    if not isinstance(cases_document, dict) or not cases_document:
        raise TargetOracleError(
            "INVALID_FIXTURE_SCHEMA", "prediction_cases must be a non-empty object"
        )
    producer = ProducerRef(
        component="d1-synthetic-fake-prediction",
        version="1",
        artifact_hash="0" * 64,
        config_hash="1" * 64,
    )
    prediction_cases: list[tuple[str, tuple[Detection, ...]]] = []
    for case_id, records in sorted(cases_document.items()):
        if not isinstance(case_id, str) or not isinstance(records, list):
            raise TargetOracleError(
                "INVALID_FIXTURE_SCHEMA", "prediction case has invalid structure"
            )
        prediction_cases.append(
            (
                case_id,
                tuple(_parse_detection(item, producer) for item in records),
            )
        )
    return LoadedTargetOracleFixture(
        fixture_id=fixture_id,
        use_class=use_class,
        dataset=dataset,
        split_groups=split_groups,
        prediction_cases=tuple(prediction_cases),
    )


def _parse_source_group(document: object) -> SourceGroup:
    if not isinstance(document, dict):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "source group must be an object")
    return SourceGroup(
        source_sequence=_strict_int(document, "source_sequence"),
        source_sequence_id=_strict_string(document, "source_sequence_id"),
        split=_strict_string(document, "split"),
        participant_id=_strict_string(document, "participant_id"),
        house_room_id=_strict_string(document, "house_room_id"),
        session_id=_strict_string(document, "session_id"),
        camera_time_group_id=_strict_string(document, "camera_time_group_id"),
        synchronized_view_group_id=_strict_string(
            document, "synchronized_view_group_id"
        ),
    )


def _parse_sequence(document: object) -> OracleSequence:
    if not isinstance(document, dict):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "sequence must be an object")
    frames_document = document.get("frames")
    if not isinstance(frames_document, list):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "frames must be a list")
    return OracleSequence(
        group=_parse_source_group(document.get("group")),
        frames=tuple(_parse_frame(item) for item in frames_document),
    )


def _parse_frame(document: object) -> OracleFrame:
    if not isinstance(document, dict):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "frame must be an object")
    instances_document = document.get("instances")
    if not isinstance(instances_document, list):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "instances must be a list")
    try:
        state = FrameEvaluationState(_strict_string(document, "state"))
    except ValueError as error:
        raise TargetOracleError("INVALID_FRAME_STATE", "unknown frame state") from error
    return OracleFrame(
        frame_index=_strict_int(document, "frame_index"),
        state=state,
        instances=tuple(_parse_instance(item) for item in instances_document),
    )


def _parse_instance(document: object) -> ReferenceInstance:
    if not isinstance(document, dict):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "instance must be an object")
    try:
        visibility = VisibilityState(_strict_string(document, "visibility"))
    except ValueError as error:
        raise TargetOracleError("INVALID_VISIBILITY", "unknown visibility state") from error
    coordinates = document.get("bbox")
    bbox = None if coordinates is None else _parse_box(coordinates)
    return ReferenceInstance(
        instance_id=_strict_string(document, "instance_id"),
        label=_strict_string(document, "label"),
        visibility=visibility,
        bbox=bbox,
    )


def _parse_transition(document: object) -> ReferenceTransition:
    if not isinstance(document, dict):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "transition must be an object")
    try:
        kind = TransitionKind(_strict_string(document, "kind"))
    except ValueError as error:
        raise TargetOracleError("INVALID_TRANSITION", "unknown transition kind") from error
    return ReferenceTransition(
        episode_id=_strict_string(document, "episode_id"),
        source_sequence=_strict_int(document, "source_sequence"),
        instance_id=_strict_string(document, "instance_id"),
        start_frame_index=_strict_int(document, "start_frame_index"),
        end_frame_index=_strict_int(document, "end_frame_index"),
        kind=kind,
    )


def _parse_detection(document: object, producer: ProducerRef) -> Detection:
    if not isinstance(document, dict):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "prediction must be an object")
    source_sequence = _strict_int(document, "source_sequence")
    frame_index = _strict_int(document, "frame_index")
    confidence = document.get("confidence")
    if type(confidence) not in {int, float}:
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", "confidence must be numeric")
    position = SourcePosition(
        source_sequence=source_sequence,
        source_offset=frame_index,
        timestamp_basis=TimestampBasis.SOURCE_FRAME_INDEX,
        frame_index=frame_index,
    )
    return Detection(
        label=_strict_string(document, "label"),
        confidence=float(confidence),
        bbox=_parse_box(document.get("bbox")),
        position=position,
        producer_ref=producer,
    )


def _parse_box(coordinates: object) -> BoundingBox:
    if (
        not isinstance(coordinates, list)
        or len(coordinates) != 4
        or any(type(value) not in {int, float} for value in coordinates)
    ):
        raise TargetOracleError(
            "INVALID_FIXTURE_SCHEMA", "bbox must contain four numeric coordinates"
        )
    return BoundingBox(*(float(value) for value in coordinates))


def _strict_string(document: dict[str, Any], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str):
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", f"{field} must be a string")
    return value


def _strict_int(document: dict[str, Any], field: str) -> int:
    value = document.get(field)
    if type(value) is not int:
        raise TargetOracleError("INVALID_FIXTURE_SCHEMA", f"{field} must be an integer")
    return value
