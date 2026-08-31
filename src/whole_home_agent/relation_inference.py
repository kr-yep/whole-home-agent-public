"""Conservative temporal rules that emit estimated B1 claim candidates."""

from __future__ import annotations

import hashlib
import json
import math
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from .binding import BoundFrame, BoundObject
from .model import (
    ClaimCandidate,
    ClaimOperation,
    EpistemicStatus,
    EvidenceRef,
    Predicate,
    ProducerRef,
    SourcePosition,
)


_CONFIG_FIELDS = {
    "schema_version",
    "rule_version",
    "subject_entity_id",
    "container_entity_id",
    "zone_entity_id",
    "containment_lookback_frames",
    "contained_observations_required",
    "disappearance_confirmation_frames",
    "take_out_confirmation_frames",
    "container_motion_max_pixels",
    "zone_enter_overlap_ratio",
    "zone_exit_overlap_ratio",
    "zone_stable_confirmation_frames",
    "zone_exit_confirmation_frames",
    "maximum_observation_gap_frames",
}


@dataclass(frozen=True, slots=True)
class RelationRuleConfig:
    rule_version: str
    subject_entity_id: str
    container_entity_id: str
    zone_entity_id: str
    containment_lookback_frames: int
    contained_observations_required: int
    disappearance_confirmation_frames: int
    take_out_confirmation_frames: int
    container_motion_max_pixels: float
    zone_enter_overlap_ratio: float
    zone_exit_overlap_ratio: float
    zone_stable_confirmation_frames: int
    zone_exit_confirmation_frames: int
    maximum_observation_gap_frames: int

    def __post_init__(self) -> None:
        identifiers = (
            self.rule_version,
            self.subject_entity_id,
            self.container_entity_id,
            self.zone_entity_id,
        )
        positive_integers = (
            self.containment_lookback_frames,
            self.contained_observations_required,
            self.disappearance_confirmation_frames,
            self.take_out_confirmation_frames,
            self.zone_stable_confirmation_frames,
            self.zone_exit_confirmation_frames,
            self.maximum_observation_gap_frames,
        )
        if any(
            type(value) is not str or not value or value != value.strip()
            for value in identifiers
        ):
            raise ValueError("relation rule identifiers must be non-empty strings")
        if len(set(identifiers[1:])) != 3:
            raise ValueError("subject, container, and zone entity IDs must be distinct")
        if any(type(value) is not int or value <= 0 for value in positive_integers):
            raise ValueError("relation rule frame counts must be positive integers")
        if self.contained_observations_required > self.containment_lookback_frames:
            raise ValueError("containment evidence cannot exceed its lookback window")
        if (
            type(self.container_motion_max_pixels) is not float
            or self.container_motion_max_pixels < 0
            or type(self.zone_enter_overlap_ratio) is not float
            or type(self.zone_exit_overlap_ratio) is not float
            or not 0 <= self.zone_exit_overlap_ratio < self.zone_enter_overlap_ratio <= 1
        ):
            raise ValueError("relation motion/overlap thresholds are invalid")


@dataclass(frozen=True, slots=True)
class InferenceAbstention:
    frame_index: int
    reason: str
    entity_ids: tuple[str, ...]


def load_relation_rule_config(
    path: str | Path, *, repository_root: str | Path
) -> RelationRuleConfig:
    root = Path(repository_root).resolve(strict=True)
    allowed_directory = (root / "configs" / "perception").resolve(strict=True)
    config_path = Path(path).resolve(strict=True)
    if config_path.parent != allowed_directory or config_path.suffix != ".toml":
        raise ValueError("relation rule config is outside configs/perception")
    document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    if set(document) != _CONFIG_FIELDS or document["schema_version"] != 1:
        raise ValueError("relation rule config does not match schema version 1")
    values = dict(document)
    values.pop("schema_version")
    return RelationRuleConfig(**values)


def _center_inside(item: BoundObject, container: BoundObject) -> bool:
    x, y = item.center
    return (
        container.bbox.x_min <= x <= container.bbox.x_max
        and container.bbox.y_min <= y <= container.bbox.y_max
    )


def _center_distance(left: BoundObject, right: BoundObject) -> float:
    left_x, left_y = left.center
    right_x, right_y = right.center
    return math.hypot(left_x - right_x, left_y - right_y)


def _subject_overlap(subject: BoundObject, zone: BoundObject) -> float:
    left = max(subject.bbox.x_min, zone.bbox.x_min)
    top = max(subject.bbox.y_min, zone.bbox.y_min)
    right = min(subject.bbox.x_max, zone.bbox.x_max)
    bottom = min(subject.bbox.y_max, zone.bbox.y_max)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    return intersection / subject.bbox.area


class TemporalRelationEngine:
    """Infer only the bounded key/container/zone relations from ordered frames."""

    def __init__(
        self,
        config: RelationRuleConfig,
        *,
        source_id: str,
        detector_producer: ProducerRef,
        entity_map: tuple[tuple[str, str], ...],
    ) -> None:
        entity_ids = {entity_id for _, entity_id in entity_map}
        required = {
            config.subject_entity_id,
            config.container_entity_id,
            config.zone_entity_id,
        }
        if not source_id or required - entity_ids:
            raise ValueError("relation rules refer to entities outside the source manifest")
        artifact_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        config_payload = {
            "detector_producer": detector_producer.identity_payload(),
            "entity_map": entity_map,
            "rules": asdict(config),
        }
        config_hash = hashlib.sha256(
            json.dumps(config_payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        self._producer_ref = ProducerRef(
            component="b1-temporal-relation-engine",
            version=config.rule_version,
            artifact_hash=artifact_hash,
            config_hash=config_hash,
        )
        self._config = config
        self._source_id = source_id
        self._label_to_entity = dict(entity_map)
        self._emitted: list[ClaimCandidate] = []
        self._abstentions: list[InferenceAbstention] = []
        self._last_frame_index: int | None = None
        self._contained_history: list[tuple[BoundObject, BoundObject]] = []
        self._absence_count = 0
        self._absence_start: SourcePosition | None = None
        self._absence_confidences: list[float] = []
        self._no_context_recorded = False
        self._outside_count = 0
        self._outside_start: SourcePosition | None = None
        self._outside_confidences: list[float] = []
        self._inside_active = False
        self._last_container: BoundObject | None = None
        self._zone_stable_count = 0
        self._zone_stable_start: SourcePosition | None = None
        self._zone_stable_confidences: list[float] = []
        self._zone_exit_count = 0
        self._zone_exit_start: SourcePosition | None = None
        self._zone_exit_confidences: list[float] = []
        self._zone_active = False
        self._last_zone_subject: BoundObject | None = None

    @property
    def producer_ref(self) -> ProducerRef:
        return self._producer_ref

    @property
    def emitted_candidates(self) -> tuple[ClaimCandidate, ...]:
        return tuple(self._emitted)

    @property
    def abstentions(self) -> tuple[InferenceAbstention, ...]:
        return tuple(self._abstentions)

    def _reset_transient(self) -> None:
        self._contained_history.clear()
        self._absence_count = 0
        self._absence_start = None
        self._absence_confidences.clear()
        self._no_context_recorded = False
        self._outside_count = 0
        self._outside_start = None
        self._outside_confidences.clear()
        self._zone_stable_count = 0
        self._zone_stable_start = None
        self._zone_stable_confidences.clear()
        self._zone_exit_count = 0
        self._zone_exit_start = None
        self._zone_exit_confidences.clear()
        self._last_container = None
        self._last_zone_subject = None

    def _abstain(self, frame_index: int, reason: str, *entity_ids: str) -> None:
        record = InferenceAbstention(
            frame_index=frame_index,
            reason=reason,
            entity_ids=tuple(sorted(set(entity_ids))),
        )
        if not self._abstentions or self._abstentions[-1] != record:
            self._abstentions.append(record)

    def _position(self, observed: SourcePosition, ordinal: int) -> SourcePosition:
        return SourcePosition(
            source_sequence=observed.source_sequence,
            source_offset=observed.source_offset * 100 + ordinal,
            timestamp_basis=observed.timestamp_basis,
            frame_index=observed.frame_index,
            pts=observed.pts,
            time_base_numerator=observed.time_base_numerator,
            time_base_denominator=observed.time_base_denominator,
        )

    def _candidate(
        self,
        *,
        frame: BoundFrame,
        ordinal: int,
        operation: ClaimOperation,
        subject_id: str,
        predicate: Predicate,
        object_id: str,
        evidence_start: SourcePosition,
        confidences: list[float],
    ) -> ClaimCandidate:
        position = self._position(frame.position, ordinal)
        frame_index = frame.position.frame_index
        assert frame_index is not None
        confidence = float(min(confidences)) if confidences else None
        operation_name = operation.value
        predicate_name = predicate.value
        claim_id = (
            f"b1:{self._config.rule_version}:{operation_name}:{predicate_name}:"
            f"{subject_id}:{object_id}:f{frame_index}"
        )
        return ClaimCandidate(
            claim_id=claim_id,
            source_sequence=position.source_sequence,
            source_offset=position.source_offset,
            operation=operation,
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            epistemic_status=EpistemicStatus.ESTIMATED,
            source_position=position,
            producer_ref=self._producer_ref,
            evidence_refs=(
                EvidenceRef(
                    evidence_id=(
                        f"frames:{evidence_start.frame_index}-{frame_index}:"
                        f"{predicate_name}:{subject_id}:{object_id}:{operation_name}"
                    ),
                    source_id=self._source_id,
                    start=evidence_start,
                    end=frame.position,
                    confidence=confidence,
                    quality="perception_report",
                ),
            ),
        )

    def observe(self, frame: BoundFrame) -> tuple[ClaimCandidate, ...]:
        frame_index = frame.position.frame_index
        if frame_index is None:
            raise ValueError("temporal relation inference requires frame indexes")
        if self._last_frame_index is not None:
            gap = frame_index - self._last_frame_index
            if gap <= 0:
                raise ValueError("bound frames must be strictly ordered")
            if gap > self._config.maximum_observation_gap_frames:
                self._reset_transient()
                self._abstain(
                    frame_index,
                    "observation_gap_exceeded",
                    self._config.subject_entity_id,
                    self._config.container_entity_id,
                    self._config.zone_entity_id,
                )
        self._last_frame_index = frame_index
        by_entity = frame.by_entity()
        ambiguous_entities = {
            self._label_to_entity[item.label]
            for item in frame.abstentions
            if item.reason == "ambiguous_instance"
            and item.label in self._label_to_entity
        }
        for item in frame.abstentions:
            entity_id = self._label_to_entity.get(item.label)
            self._abstain(
                frame_index,
                f"binding_{item.reason}",
                *(tuple([entity_id]) if entity_id is not None else ()),
            )

        emitted: list[ClaimCandidate] = []
        if ambiguous_entities & {
            self._config.subject_entity_id,
            self._config.container_entity_id,
        }:
            self._contained_history.clear()
            self._absence_count = 0
            self._outside_count = 0
        else:
            candidate = self._observe_containment(frame, by_entity, len(emitted))
            if candidate is not None:
                emitted.append(candidate)
        if ambiguous_entities & {
            self._config.container_entity_id,
            self._config.zone_entity_id,
        }:
            self._zone_stable_count = 0
            self._zone_exit_count = 0
        else:
            candidate = self._observe_zone(frame, by_entity, len(emitted))
            if candidate is not None:
                emitted.append(candidate)
        self._emitted.extend(emitted)
        return tuple(emitted)

    def _observe_containment(
        self,
        frame: BoundFrame,
        by_entity: dict[str, BoundObject],
        ordinal: int,
    ) -> ClaimCandidate | None:
        frame_index = frame.position.frame_index
        assert frame_index is not None
        subject = by_entity.get(self._config.subject_entity_id)
        container = by_entity.get(self._config.container_entity_id)
        self._contained_history = [
            item
            for item in self._contained_history
            if frame_index - item[0].position.frame_index
            <= self._config.containment_lookback_frames
        ]
        container_stable = (
            container is not None
            and self._last_container is not None
            and _center_distance(container, self._last_container)
            <= self._config.container_motion_max_pixels
        )

        if subject is not None:
            self._absence_count = 0
            self._absence_start = None
            self._absence_confidences.clear()
            self._no_context_recorded = False
            if container is None:
                if self._inside_active:
                    self._abstain(
                        frame_index,
                        "active_container_unobserved",
                        self._config.subject_entity_id,
                        self._config.container_entity_id,
                    )
                self._outside_count = 0
            elif _center_inside(subject, container):
                self._contained_history.append((subject, container))
                self._outside_count = 0
                self._outside_start = None
                self._outside_confidences.clear()
            elif self._inside_active:
                if self._outside_count == 0:
                    self._outside_start = frame.position
                    self._outside_confidences = []
                self._outside_count += 1
                self._outside_confidences.extend(
                    [subject.confidence, container.confidence]
                )
                if self._outside_count >= self._config.take_out_confirmation_frames:
                    assert self._outside_start is not None
                    candidate = self._candidate(
                        frame=frame,
                        ordinal=ordinal,
                        operation=ClaimOperation.RETRACT,
                        subject_id=self._config.subject_entity_id,
                        predicate=Predicate.INSIDE,
                        object_id=self._config.container_entity_id,
                        evidence_start=self._outside_start,
                        confidences=self._outside_confidences,
                    )
                    self._inside_active = False
                    self._outside_count = 0
                    self._outside_start = None
                    self._outside_confidences = []
                    self._last_container = container
                    return candidate
            else:
                self._outside_count = 0
        elif self._inside_active:
            if container is None:
                self._abstain(
                    frame_index,
                    "active_container_unobserved",
                    self._config.subject_entity_id,
                    self._config.container_entity_id,
                )
        elif container is not None:
            recent = self._contained_history[
                -self._config.contained_observations_required :
            ]
            has_context = (
                len(recent) >= self._config.contained_observations_required
            )
            if has_context and container_stable:
                if self._absence_count == 0:
                    self._absence_start = recent[0][0].position
                    self._absence_confidences = [
                        value
                        for item, observed_container in recent
                        for value in (item.confidence, observed_container.confidence)
                    ]
                self._absence_count += 1
                self._absence_confidences.append(container.confidence)
                if (
                    self._absence_count
                    >= self._config.disappearance_confirmation_frames
                ):
                    assert self._absence_start is not None
                    candidate = self._candidate(
                        frame=frame,
                        ordinal=ordinal,
                        operation=ClaimOperation.ASSERT,
                        subject_id=self._config.subject_entity_id,
                        predicate=Predicate.INSIDE,
                        object_id=self._config.container_entity_id,
                        evidence_start=self._absence_start,
                        confidences=self._absence_confidences,
                    )
                    self._inside_active = True
                    self._absence_count = 0
                    self._absence_start = None
                    self._absence_confidences = []
                    self._last_container = container
                    return candidate
            else:
                self._absence_count += 1
                if (
                    self._absence_count
                    >= self._config.disappearance_confirmation_frames
                    and not self._no_context_recorded
                ):
                    self._abstain(
                        frame_index,
                        "disappearance_without_containment_context",
                        self._config.subject_entity_id,
                        self._config.container_entity_id,
                    )
                    self._no_context_recorded = True
        else:
            self._absence_count = 0
            self._abstain(
                frame_index,
                "subject_and_container_unobserved",
                self._config.subject_entity_id,
                self._config.container_entity_id,
            )
        if container is not None:
            self._last_container = container
        return None

    def _observe_zone(
        self,
        frame: BoundFrame,
        by_entity: dict[str, BoundObject],
        ordinal: int,
    ) -> ClaimCandidate | None:
        frame_index = frame.position.frame_index
        assert frame_index is not None
        subject = by_entity.get(self._config.container_entity_id)
        zone = by_entity.get(self._config.zone_entity_id)
        if subject is None or zone is None:
            self._zone_stable_count = 0
            self._zone_exit_count = 0
            if subject is not None:
                self._last_zone_subject = subject
            return None
        overlap = _subject_overlap(subject, zone)
        stable = (
            self._last_zone_subject is not None
            and _center_distance(subject, self._last_zone_subject)
            <= self._config.container_motion_max_pixels
        )
        self._last_zone_subject = subject
        if self._zone_active:
            if overlap <= self._config.zone_exit_overlap_ratio:
                if self._zone_exit_count == 0:
                    self._zone_exit_start = frame.position
                    self._zone_exit_confidences = []
                self._zone_exit_count += 1
                self._zone_exit_confidences.extend(
                    [subject.confidence, zone.confidence]
                )
                if self._zone_exit_count >= self._config.zone_exit_confirmation_frames:
                    assert self._zone_exit_start is not None
                    candidate = self._candidate(
                        frame=frame,
                        ordinal=ordinal,
                        operation=ClaimOperation.RETRACT,
                        subject_id=self._config.container_entity_id,
                        predicate=Predicate.AT_ZONE,
                        object_id=self._config.zone_entity_id,
                        evidence_start=self._zone_exit_start,
                        confidences=self._zone_exit_confidences,
                    )
                    self._zone_active = False
                    self._zone_exit_count = 0
                    self._zone_exit_start = None
                    self._zone_exit_confidences = []
                    return candidate
            else:
                self._zone_exit_count = 0
                self._zone_exit_start = None
                self._zone_exit_confidences.clear()
            return None
        if overlap >= self._config.zone_enter_overlap_ratio and stable:
            if self._zone_stable_count == 0:
                self._zone_stable_start = frame.position
                self._zone_stable_confidences = []
            self._zone_stable_count += 1
            self._zone_stable_confidences.extend(
                [subject.confidence, zone.confidence]
            )
            if (
                self._zone_stable_count
                >= self._config.zone_stable_confirmation_frames
            ):
                assert self._zone_stable_start is not None
                candidate = self._candidate(
                    frame=frame,
                    ordinal=ordinal,
                    operation=ClaimOperation.ASSERT,
                    subject_id=self._config.container_entity_id,
                    predicate=Predicate.AT_ZONE,
                    object_id=self._config.zone_entity_id,
                    evidence_start=self._zone_stable_start,
                    confidences=self._zone_stable_confidences,
                )
                self._zone_active = True
                self._zone_stable_count = 0
                self._zone_stable_start = None
                self._zone_stable_confidences = []
                return candidate
        else:
            self._zone_stable_count = 0
            self._zone_stable_start = None
            self._zone_stable_confidences.clear()
        return None
