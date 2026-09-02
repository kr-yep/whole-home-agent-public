"""Application use cases for persisting and querying completed D0 replays."""

from __future__ import annotations

from collections.abc import Mapping

from .llm_context import build_llm_text_context
from .memory import ReplayArchive
from .model import AnswerTrace, QueryRequest
from .natural_query import QUESTION_PARSER_ID, parse_location_question
from .presentation import (
    DeterministicLocationPresenter,
    LocationPresenter,
    present_location_context,
)


MEMORY_ANSWER_SCHEMA = "whole-home-agent.memory-answer.v1"


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


def _known_entities(answer_source: object) -> tuple[str, ...]:
    accepted_claims = getattr(answer_source, "accepted_claims")
    return tuple(
        sorted(
            {
                identifier
                for claim in accepted_claims
                for identifier in (claim.subject_id, claim.object_id)
            }
        )
    )


def answer_latest_memory(
    archive: ReplayArchive,
    question: str,
    *,
    presenter: LocationPresenter | None = None,
) -> dict[str, object]:
    """Restore the newest verified replay and answer one bounded location question."""

    session = archive.load_latest()
    subject_id = parse_location_question(
        question,
        allowed_entity_ids=_known_entities(session),
    )
    answer = session.locate(
        QueryRequest(
            subject_id=subject_id,
            world_scope=session.world_scope,
            replay_run_id=session.replay_run_id,
            as_of_source_sequence=session.projection_frontier,
        )
    )
    answer_payload = _answer_dict(answer)
    context: Mapping[str, object] = build_llm_text_context(answer_payload)
    presentation = present_location_context(
        context,
        presenter if presenter is not None else DeterministicLocationPresenter(),
    )
    return {
        "schema": MEMORY_ANSWER_SCHEMA,
        "query": {
            "parser_id": QUESTION_PARSER_ID,
            "subject_id": subject_id,
            "stored": False,
        },
        "answer": answer_payload,
        "presentation": presentation.as_dict(),
        "governance": {
            "data_scope": "D0_SYNTHETIC_OR_PUBLIC",
            "operate": "DISABLED",
            "physical_truth_claimed": False,
        },
    }
