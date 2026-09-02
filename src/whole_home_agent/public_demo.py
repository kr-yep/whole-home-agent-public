"""Closed composition and presentation boundary for the public B1 demo."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .adapters.recorded_perception_source import RecordedPerceptionCandidateSource
from .adapters.synthetic_color import (
    SyntheticColorDetector,
    load_synthetic_color_config,
)
from .adapters.tracking import IoUTracker
from .errors import ErrorCode, SourceError
from .evaluation import evaluate_perception
from .llm_context import build_llm_text_context
from .model import AnswerTrace, QueryRequest, RunStatus
from .orchestrator import run_source
from .presentation import (
    DeterministicLocationPresenter,
    present_location_context,
)
from .relation_evaluation import (
    evaluate_relations,
    load_relation_evaluation_config,
)
from .relation_inference import load_relation_rule_config
from .video_manifest import load_video_manifest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_MANIFEST = (
    REPOSITORY_ROOT
    / "examples"
    / "media"
    / "generated"
    / "key_bag_sofa_v2.manifest.json"
)
COLOR_CONFIG = (
    REPOSITORY_ROOT / "configs" / "perception" / "synthetic-color-v1.toml"
)
RELATION_CONFIG = (
    REPOSITORY_ROOT / "configs" / "perception" / "relation-rules-v1.toml"
)
RELATION_EVAL_CONFIG = (
    REPOSITORY_ROOT / "configs" / "perception" / "relation-eval-v1.toml"
)


def _resolve_demo_root() -> Path:
    """Resolve the clone root or the wheel's read-only shared-data root."""

    if PUBLIC_MANIFEST.is_file():
        return REPOSITORY_ROOT
    installed_root = Path(sys.prefix) / "wha"
    installed_manifest = installed_root / PUBLIC_MANIFEST.relative_to(
        REPOSITORY_ROOT
    )
    if installed_manifest.is_file():
        return installed_root
    raise SourceError(
        "the fixed public demo bundle is not installed",
        error_code=ErrorCode.INVALID_SOURCE,
    )


def _at_demo_root(path: Path, demo_root: Path) -> Path:
    return demo_root / path.relative_to(REPOSITORY_ROOT)


def _position_dict(position) -> dict[str, object]:
    return {
        "frame_index": position.frame_index,
        "pts": position.pts,
        "source_offset": position.source_offset,
        "source_sequence": position.source_sequence,
        "time_base_denominator": position.time_base_denominator,
        "time_base_numerator": position.time_base_numerator,
        "timestamp_basis": position.timestamp_basis.value,
    }


def _answer_dict(answer: AnswerTrace) -> dict[str, object]:
    return {
        "as_of_source_sequence": answer.as_of_source_sequence,
        "candidate_location_ids": list(answer.candidate_location_ids),
        "epistemic_status": answer.epistemic_status,
        "location_id": answer.location_id,
        "projection_frontier": answer.projection_frontier,
        "reason": answer.reason,
        "relation_path": [
            {
                "epistemic_status": step.epistemic_status.value,
                "object_id": step.object_id,
                "predicate": step.predicate.value,
                "source_claim_id": step.source_claim_id,
                "source_offset": step.source_offset,
                "source_sequence": step.source_sequence,
                "subject_id": step.subject_id,
            }
            for step in answer.relation_path
        ],
        "replay_run_id": answer.replay_run_id,
        "source_claim_ids": list(answer.source_claim_ids),
        "status": answer.status.value,
        "subject_id": answer.subject_id,
        "world_scope": answer.world_scope,
    }


def _claim_dict(claim) -> dict[str, object]:
    return {
        "claim_id": claim.claim_id,
        "epistemic_status": claim.epistemic_status.value,
        "evidence": [
            {
                "confidence": item.confidence,
                "end": _position_dict(item.end),
                "evidence_id": item.evidence_id,
                "quality": item.quality,
                "start": _position_dict(item.start),
            }
            for item in claim.evidence_refs
        ],
        "object_id": claim.object_id,
        "operation": claim.operation.value,
        "predicate": claim.predicate.value,
        "producer_ref": (
            {
                "artifact_hash": claim.producer_ref.artifact_hash,
                "component": claim.producer_ref.component,
                "config_hash": claim.producer_ref.config_hash,
                "version": claim.producer_ref.version,
            }
            if claim.producer_ref is not None
            else None
        ),
        "source_position": (
            _position_dict(claim.source_position)
            if claim.source_position is not None
            else None
        ),
        "subject_id": claim.subject_id,
    }


def load_public_demo_media() -> bytes:
    """Return only the hash-validated project-generated public demo media."""

    demo_root = _resolve_demo_root()
    manifest = load_video_manifest(
        _at_demo_root(PUBLIC_MANIFEST, demo_root), repository_root=demo_root
    )
    return manifest.media_path.read_bytes()


def run_public_demo(
    *,
    replay_run_id: str = "public-b1-demo-001",
    subject_id: str = "key",
    include_frames: bool = True,
) -> dict[str, Any]:
    """Run the one allowlisted offline demo and return presentation-safe values."""

    demo_root = _resolve_demo_root()
    manifest = load_video_manifest(
        _at_demo_root(PUBLIC_MANIFEST, demo_root), repository_root=demo_root
    )
    allowed_entities = {record["entity_id"] for record in manifest.entities}
    if subject_id not in allowed_entities:
        raise SourceError(
            "public demo query subject is outside the manifest allowlist",
            error_code=ErrorCode.INVALID_SOURCE,
        )
    width, height, targets = load_synthetic_color_config(
        _at_demo_root(COLOR_CONFIG, demo_root), repository_root=demo_root
    )
    detector = SyntheticColorDetector(width=width, height=height, targets=targets)
    perception_report = evaluate_perception(
        manifest,
        detector,
        tracker=IoUTracker(),
        repository_root=demo_root,
    )
    source = RecordedPerceptionCandidateSource(
        manifest,
        detector,
        IoUTracker(),
        load_relation_rule_config(
            _at_demo_root(RELATION_CONFIG, demo_root), repository_root=demo_root
        ),
    )
    result = run_source(source, replay_run_id=replay_run_id)
    if result.status is not RunStatus.COMPLETE or result.session is None:
        raise SourceError(
            "public prerecorded demo did not produce a complete session",
            error_code=ErrorCode.SOURCE_FAILURE,
            details={"run_status": result.status.value},
        )
    session = result.session
    answer = session.locate(
        QueryRequest(
            subject_id=subject_id,
            world_scope=session.world_scope,
            replay_run_id=session.replay_run_id,
            as_of_source_sequence=session.projection_frontier,
        )
    )
    relation_report = evaluate_relations(
        manifest,
        result,
        source.diagnostics.abstentions,
        source.diagnostics.completed,
        load_relation_evaluation_config(
            _at_demo_root(RELATION_EVAL_CONFIG, demo_root),
            repository_root=demo_root,
        ),
    )
    answer_payload = _answer_dict(answer)
    language_context = build_llm_text_context(answer_payload)
    presentation = present_location_context(
        language_context,
        DeterministicLocationPresenter(),
    )
    frames = [
        {
            "bound_entity_ids": sorted(trace.binding.by_entity()),
            "detections": [
                {
                    "bbox_xyxy": list(item.bbox.as_xyxy()),
                    "confidence": item.confidence,
                    "label": item.label,
                }
                for item in trace.detections
            ],
            "emitted_claim_ids": list(trace.emitted_claim_ids),
            "frame_index": trace.frame_index,
            "pts": trace.pts,
        }
        for trace in source.trace
    ]
    return {
        "answer": answer_payload,
        "answer_summary": presentation.text,
        "claims": [_claim_dict(item) for item in session.accepted_claims],
        "frames": frames if include_frames else [],
        "governance": {
            "allowed_data": "D0_SYNTHETIC",
            "mode": "OFFLINE_PRERECORDED_REPLAY",
            "operate": "DISABLED",
            "physical_truth_claimed": False,
        },
        "language_context": language_context,
        "perception_evaluation": perception_report.as_dict(),
        "presentation": presentation.as_dict(),
        "relation_evaluation": relation_report.as_dict(),
        "run_receipt": result.receipt.as_dict(),
        "source": {
            "content_hash": manifest.descriptor.content_hash,
            "frame_count": manifest.frame_count,
            "license": manifest.license_id,
            "source_id": manifest.descriptor.source_id,
            "source_revision": manifest.descriptor.source_revision,
        },
        "source_diagnostics": {
            "abstentions": [
                {
                    "entity_ids": list(item.entity_ids),
                    "frame_index": item.frame_index,
                    "reason": item.reason,
                }
                for item in source.diagnostics.abstentions
            ],
            "completed": source.diagnostics.completed,
            "decoded_frames": source.diagnostics.decoded_frames,
            "emitted_candidate_count": source.diagnostics.emitted_candidate_count,
            "selected_frames": source.diagnostics.selected_frames,
        },
        "warnings": [
            "This result applies only to one generated replay and is not a present-world fact.",
            "The RGB color detector is deliberately synthetic-specific and is not a household model.",
            "No live camera, upload, cloud service, device, account, or action capability is connected.",
        ],
    }
