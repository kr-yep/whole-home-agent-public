"""Frozen event and answer evaluation for the bounded B1 relation replay."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import QueryRequest, QueryStatus, ReplayRunResult, RunStatus
from .relation_inference import InferenceAbstention
from .video_manifest import VideoSourceManifest


_FIELDS = {
    "schema_version",
    "evaluator_version",
    "maximum_confirmation_lag_frames",
    "query_subject_id",
    "expected_location_id",
}


@dataclass(frozen=True, slots=True)
class RelationEvaluationConfig:
    evaluator_version: str
    maximum_confirmation_lag_frames: int
    query_subject_id: str
    expected_location_id: str

    def __post_init__(self) -> None:
        if (
            type(self.evaluator_version) is not str
            or not self.evaluator_version
            or type(self.maximum_confirmation_lag_frames) is not int
            or self.maximum_confirmation_lag_frames < 0
            or type(self.query_subject_id) is not str
            or not self.query_subject_id
            or type(self.expected_location_id) is not str
            or not self.expected_location_id
        ):
            raise ValueError("relation evaluation config is invalid")


@dataclass(frozen=True, slots=True)
class RelationQuality:
    expected_events: int
    predicted_events: int
    matched_events: int
    precision: float
    recall: float
    f1: float
    confirmation_lags_frames: tuple[int, ...]
    answer_correct: bool
    answer_status: str
    answer_location_id: str | None
    abstention_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "abstention_count": self.abstention_count,
            "answer_correct": self.answer_correct,
            "answer_location_id": self.answer_location_id,
            "answer_status": self.answer_status,
            "confirmation_lags_frames": list(self.confirmation_lags_frames),
            "expected_events": self.expected_events,
            "f1": self.f1,
            "matched_events": self.matched_events,
            "precision": self.precision,
            "predicted_events": self.predicted_events,
            "recall": self.recall,
        }


@dataclass(frozen=True, slots=True)
class RelationEvaluationReport:
    source_id: str
    source_revision: str
    source_content_hash: str
    evaluator_version: str
    quality: RelationQuality
    evidence_limit: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "evaluator_version": self.evaluator_version,
            "evidence_limit": self.evidence_limit,
            "quality": self.quality.as_dict(),
            "source_content_hash": self.source_content_hash,
            "source_id": self.source_id,
            "source_revision": self.source_revision,
        }


def load_relation_evaluation_config(
    path: str | Path, *, repository_root: str | Path
) -> RelationEvaluationConfig:
    root = Path(repository_root).resolve(strict=True)
    allowed_directory = (root / "configs" / "perception").resolve(strict=True)
    config_path = Path(path).resolve(strict=True)
    if config_path.parent != allowed_directory or config_path.suffix != ".toml":
        raise ValueError("relation evaluation config is outside configs/perception")
    document = tomllib.loads(config_path.read_text(encoding="utf-8"))
    if set(document) != _FIELDS or document["schema_version"] != 1:
        raise ValueError("relation evaluation config does not match schema version 1")
    values = dict(document)
    values.pop("schema_version")
    return RelationEvaluationConfig(**values)


def evaluate_relations(
    manifest: VideoSourceManifest,
    result: ReplayRunResult,
    abstentions: tuple[InferenceAbstention, ...],
    source_completed: bool,
    config: RelationEvaluationConfig,
) -> RelationEvaluationReport:
    if result.status is not RunStatus.COMPLETE or result.session is None:
        raise ValueError("relation evaluation requires one complete replay session")
    if not source_completed:
        raise ValueError("relation evaluation refuses incomplete source diagnostics")
    session = result.session
    expected: list[tuple[str, str, str, str, int]] = []
    for record in manifest.events:
        required = {
            "event_id",
            "frame_index",
            "object_id",
            "operation",
            "predicate",
            "subject_id",
        }
        if set(record) != required or type(record["frame_index"]) is not int:
            raise ValueError("manifest event does not match the frozen evaluation schema")
        expected.append(
            (
                record["operation"],
                record["subject_id"],
                record["predicate"],
                record["object_id"],
                record["frame_index"],
            )
        )
    predicted = [
        (
            claim.operation.value,
            claim.subject_id,
            claim.predicate.value,
            claim.object_id,
            claim.source_position.frame_index,
        )
        for claim in session.accepted_claims
        if claim.source_position is not None
        and claim.source_position.frame_index is not None
    ]
    used_predictions: set[int] = set()
    lags: list[int] = []
    for operation, subject, predicate, object_id, expected_frame in expected:
        matches = sorted(
            (
                predicted_frame - expected_frame,
                index,
            )
            for index, (
                predicted_operation,
                predicted_subject,
                predicted_predicate,
                predicted_object,
                predicted_frame,
            ) in enumerate(predicted)
            if index not in used_predictions
            and predicted_operation == operation
            and predicted_subject == subject
            and predicted_predicate == predicate
            and predicted_object == object_id
            and 0 <= predicted_frame - expected_frame
            <= config.maximum_confirmation_lag_frames
        )
        if matches:
            lag, prediction_index = matches[0]
            used_predictions.add(prediction_index)
            lags.append(lag)
    matched = len(lags)
    precision = matched / len(predicted) if predicted else (1.0 if not expected else 0.0)
    recall = matched / len(expected) if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    answer = session.locate(
        QueryRequest(
            subject_id=config.query_subject_id,
            world_scope=session.world_scope,
            replay_run_id=session.replay_run_id,
            as_of_source_sequence=session.projection_frontier,
        )
    )
    answer_correct = (
        answer.status is QueryStatus.FOUND
        and answer.location_id == config.expected_location_id
    )
    return RelationEvaluationReport(
        source_id=manifest.descriptor.source_id,
        source_revision=manifest.descriptor.source_revision,
        source_content_hash=manifest.descriptor.content_hash,
        evaluator_version=config.evaluator_version,
        quality=RelationQuality(
            expected_events=len(expected),
            predicted_events=len(predicted),
            matched_events=matched,
            precision=precision,
            recall=recall,
            f1=f1,
            confirmation_lags_frames=tuple(lags),
            answer_correct=answer_correct,
            answer_status=answer.status.value,
            answer_location_id=answer.location_id,
            abstention_count=len(abstentions),
        ),
        evidence_limit=(
            "This report scores one hash-pinned generated replay with a predeclared "
            "confirmation lag and final query; it does not establish indoor transfer, "
            "physical truth, live sensing, or general relation understanding."
        ),
    )
