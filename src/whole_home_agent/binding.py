"""Deterministic one-instance entity binding for the bounded B1 replay."""

from __future__ import annotations

from dataclasses import dataclass

from .model import SourcePosition
from .perception import BoundingBox, TrackObservation
from .video_manifest import VideoSourceManifest


@dataclass(frozen=True, slots=True)
class BoundObject:
    entity_id: str
    label: str
    bbox: BoundingBox
    confidence: float
    track_id: str
    position: SourcePosition

    @property
    def center(self) -> tuple[float, float]:
        return (
            (self.bbox.x_min + self.bbox.x_max) / 2.0,
            (self.bbox.y_min + self.bbox.y_max) / 2.0,
        )


@dataclass(frozen=True, slots=True)
class BindingAbstention:
    frame_index: int
    reason: str
    label: str
    candidate_count: int


@dataclass(frozen=True, slots=True)
class BoundFrame:
    position: SourcePosition
    objects: tuple[BoundObject, ...]
    absent_entity_ids: tuple[str, ...]
    abstentions: tuple[BindingAbstention, ...]

    def by_entity(self) -> dict[str, BoundObject]:
        return {item.entity_id: item for item in self.objects}


class ManifestEntityBinder:
    """Bind labels only when a manifest declares exactly one instance."""

    def __init__(self, manifest: VideoSourceManifest) -> None:
        by_label: dict[str, str] = {}
        entity_ids: set[str] = set()
        for record in manifest.entities:
            if (
                set(record) != {"entity_id", "instance_count", "label"}
                or type(record.get("entity_id")) is not str
                or type(record.get("label")) is not str
                or record.get("instance_count") != 1
            ):
                raise ValueError(
                    "bounded entity binding requires one instance per declared entity"
                )
            entity_id = record["entity_id"]
            label = record["label"]
            if (
                not entity_id
                or not label
                or entity_id in entity_ids
                or label in by_label
            ):
                raise ValueError("manifest entity identities and labels must be unique")
            entity_ids.add(entity_id)
            by_label[label] = entity_id
        if not by_label:
            raise ValueError("entity binder requires at least one manifest entity")
        self._by_label = by_label
        self._entity_ids = tuple(sorted(entity_ids))

    @property
    def entity_map(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._by_label.items()))

    def bind(
        self,
        position: SourcePosition,
        observations: tuple[TrackObservation, ...],
    ) -> BoundFrame:
        frame_index = position.frame_index
        if frame_index is None:
            raise ValueError("recorded entity binding requires a frame index")
        grouped: dict[str, list[TrackObservation]] = {}
        abstentions: list[BindingAbstention] = []
        for observation in observations:
            if observation.detection.position != position:
                raise ValueError("track observation position disagrees with bound frame")
            label = observation.detection.label
            if label not in self._by_label:
                abstentions.append(
                    BindingAbstention(
                        frame_index=frame_index,
                        reason="unknown_label",
                        label=label,
                        candidate_count=1,
                    )
                )
                continue
            grouped.setdefault(label, []).append(observation)

        objects: list[BoundObject] = []
        bound_entities: set[str] = set()
        for label, entity_id in sorted(self._by_label.items()):
            candidates = grouped.get(label, [])
            if len(candidates) > 1:
                abstentions.append(
                    BindingAbstention(
                        frame_index=frame_index,
                        reason="ambiguous_instance",
                        label=label,
                        candidate_count=len(candidates),
                    )
                )
                continue
            if not candidates:
                continue
            observation = candidates[0]
            objects.append(
                BoundObject(
                    entity_id=entity_id,
                    label=label,
                    bbox=observation.detection.bbox,
                    confidence=observation.detection.confidence,
                    track_id=observation.track_id,
                    position=position,
                )
            )
            bound_entities.add(entity_id)
        return BoundFrame(
            position=position,
            objects=tuple(sorted(objects, key=lambda item: item.entity_id)),
            absent_entity_ids=tuple(
                entity_id
                for entity_id in self._entity_ids
                if entity_id not in bound_entities
            ),
            abstentions=tuple(
                sorted(
                    abstentions,
                    key=lambda item: (item.label, item.reason, item.candidate_count),
                )
            ),
        )
