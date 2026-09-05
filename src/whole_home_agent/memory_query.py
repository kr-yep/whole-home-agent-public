"""Application use cases for persisting and querying completed D0 replays."""

from __future__ import annotations

from collections.abc import Mapping

from .llm_context import build_llm_text_context
from .errors import ErrorCode, QuestionError
from .memory import ReplayArchive
from .model import AnswerTrace, QueryRequest
from .natural_query import (
    CONTENTS_PARSER_ID,
    QUESTION_PARSER_ID,
    TIMELINE_PARSER_ID,
    VERIFICATION_PARSER_ID,
    parse_container_question,
    parse_location_question,
    parse_location_verification,
    parse_timeline_question,
)
from .verification import verify
from .presentation import (
    DeterministicLocationPresenter,
    LocationPresenter,
    _display_name,
    present_location_context,
)


MEMORY_ANSWER_SCHEMA = "whole-home-agent.memory-answer.v1"
MEMORY_VERIFICATION_SCHEMA = "whole-home-agent.memory-verification.v1"
MEMORY_CONTENTS_SCHEMA = "whole-home-agent.memory-contents.v1"
MEMORY_TIMELINE_SCHEMA = "whole-home-agent.memory-timeline.v1"


class _DisplayMap(dict):
    def get(self, key, default=None):
        return _display_name(str(key))

    def __getitem__(self, key):
        return _display_name(str(key))


# Two branches solved the same problem differently: one enumerated the new
# inventory objects here, the other made every lookup go through _display_name.
# The dynamic one subsumes the list, so the names live in one place --
# _DISPLAY_NAMES in presentation.py -- and adding an object needs one edit.
_CONTAINER_DISPLAY = _DisplayMap({"bag": "包包", "key": "鑰匙", "sofa": "沙發"})


def _provenance(session) -> dict[str, object]:
    """What was restored, and the tree it was restored into.

    Returned with every answer so a caller can show the basis rather than ask the
    reader to trust the sentence.
    """

    descriptor = session.source_descriptor
    return {
        "memory": {
            "source_id": session.source_id,
            "source_revision": getattr(descriptor, "source_revision", None),
            "use_class": getattr(getattr(descriptor, "use_class", None), "value", None),
            "world_scope": session.world_scope,
            "replay_run_id": session.replay_run_id,
            "content_hash": session.source_content_hash,
            "semantic_output_hash": session.semantic_output_hash,
            "restored_claim_count": len(session.accepted_claims),
            "projection_frontier": session.projection_frontier,
        },
        "projection": {
            "edge_count": len(session.projection.active_relations),
            "edges": [
                {
                    "subject_id": relation.subject_id,
                    "predicate": relation.predicate.value,
                    "object_id": relation.object_id,
                    "source_claim_id": relation.source_claim_id,
                    "source_sequence": relation.source_sequence,
                }
                for relation in session.projection.active_relations
            ],
        },
    }


def _speakable(result: Mapping[str, object]) -> dict[str, object]:
    """The compact fact set a verbalizer is allowed to see. No hashes, no ids."""

    contents = result.get("contents")
    if contents is not None:
        return {
            "status": "CONTENTS",
            "container": _CONTAINER_DISPLAY.get(
                contents["container_id"], contents["container_id"]
            ),
            "items": [
                _CONTAINER_DISPLAY.get(item, item)
                for item in contents["contained_entity_ids"]
            ],
        }
    event = result.get("event")
    if event is not None:
        return {"status": "TIMELINE", "text": event["text"]}
    answer = result.get("answer") or {}
    facts: dict[str, object] = {
        "status": answer.get("status"),
        "subject": _CONTAINER_DISPLAY.get(
            answer.get("subject_id"), answer.get("subject_id")
        ),
        "confidence": answer.get("epistemic_status"),
    }
    verification = result.get("verification")
    if verification is not None:
        facts["question_kind"] = "yes_no"
        facts["verdict"] = verification["verdict"]
        facts["proposed_place"] = _CONTAINER_DISPLAY.get(
            verification["target_id"], verification["target_id"]
        )
    if answer.get("location_id"):
        facts["location"] = _CONTAINER_DISPLAY.get(
            answer["location_id"], answer["location_id"]
        )
    if answer.get("candidate_location_ids"):
        facts["candidates"] = [
            _CONTAINER_DISPLAY.get(item, item)
            for item in answer["candidate_location_ids"]
        ]
    chain = []
    for step in answer.get("relation_path") or []:
        subject = _CONTAINER_DISPLAY.get(step["subject_id"], step["subject_id"])
        place = _CONTAINER_DISPLAY.get(step["object_id"], step["object_id"])
        relation = f"在{place}裡面" if step["predicate"] == "inside" else f"位於{place}"
        chain.append({subject: relation})
    if chain:
        facts["chain"] = chain
    return facts


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
    entities = {
        identifier
        for claim in accepted_claims
        for identifier in (claim.subject_id, claim.object_id)
    }
    try:
        from .entity_registry import get_global_registry

        for custom in get_global_registry().list_entities():
            entities.add(custom["entity_id"])
    except Exception:
        pass
    return tuple(sorted(entities))


def list_known_entities(archive: ReplayArchive) -> tuple[str, ...]:
    """Return the entity IDs the newest stored replay can be asked about.

    A caller needs this to show the closed vocabulary instead of letting a person
    guess an entity and receive an unsupported-question rejection that looks the
    same as having no evidence.
    """

    return _known_entities(archive.load_latest())


def answer_latest_memory(
    archive: ReplayArchive,
    question: str,
    *,
    presenter: LocationPresenter | None = None,
) -> dict[str, object]:
    """Restore the newest verified replay and answer one bounded location question."""

    session = archive.load_latest()
    aliases = None
    try:
        from .entity_registry import get_global_registry

        aliases = get_global_registry().get_aliases_map()
    except Exception:
        pass
    kwargs = {"aliases": aliases} if aliases is not None else {}
    subject_id = parse_location_question(
        question,
        allowed_entity_ids=_known_entities(session),
        **kwargs,
    )
    return _location_result(session, subject_id, presenter)


def _location_result(session, subject_id, presenter) -> dict[str, object]:
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
        **_provenance(session),
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


def verify_latest_memory(archive: ReplayArchive, question: str) -> dict[str, object]:
    """Answer one bounded yes/no location question against the newest replay."""

    session = archive.load_latest()
    parsed = parse_location_verification(
        question, allowed_entity_ids=_known_entities(session)
    )
    return _verification_result(session, parsed.subject_id, parsed.target_id)


def _verification_result(session, subject_id, target_id) -> dict[str, object]:
    answer = session.locate(
        QueryRequest(
            subject_id=subject_id,
            world_scope=session.world_scope,
            replay_run_id=session.replay_run_id,
            as_of_source_sequence=session.projection_frontier,
        )
    )
    answer_payload = _answer_dict(answer)
    result = verify(answer_payload, target_id)
    return {
        **_provenance(session),
        "schema": MEMORY_VERIFICATION_SCHEMA,
        "query": {
            "parser_id": VERIFICATION_PARSER_ID,
            "subject_id": subject_id,
            "target_id": target_id,
            "stored": False,
        },
        "answer": answer_payload,
        "verification": result.as_dict(),
        "governance": {
            "data_scope": "D0_SYNTHETIC_OR_PUBLIC",
            "operate": "DISABLED",
            "physical_truth_claimed": False,
        },
    }


def answer_question(
    archive: ReplayArchive,
    question: str,
    *,
    presenter: LocationPresenter | None = None,
    verbalizer: object | None = None,
    translator: object | None = None,
) -> dict[str, object]:
    """Route one question to verification or location, without guessing between.

    A yes/no question is tried first because its intent words are the narrower
    set; anything that is not one falls through to the original where-is path,
    and a question that is neither raises from that path as it always did.
    """

    result: dict[str, object] | None = None
    for attempt in (list_container_contents, verify_latest_memory, answer_latest_timeline):
        try:
            result = attempt(archive, question)
            break
        except QuestionError:
            continue
    if result is None:
        try:
            result = answer_latest_memory(archive, question, presenter=presenter)
        except QuestionError:
            # Hand-written intent words always trail real phrasing. Ask the model
            # only for what they could not read, so the common cases stay offline.
            if translator is None:
                raise
            result = answer_by_translation(
                archive, question, translator, presenter=presenter
            )

    spoken = (
        result.get("contents")
        or result.get("verification")
        or result.get("event")
        or result["presentation"]
    )
    result["spoken"] = {
        "text": spoken["text"],
        "speaker": "deterministic",
        "fallback_used": False,
    }
    if verbalizer is not None:
        # The model rewords a settled result. If it fails, times out, or returns
        # nothing usable, the deterministic sentence is already in place.
        try:
            text = verbalizer.speak(question, _speakable(result))
            if isinstance(text, str) and text.strip():
                result["spoken"] = {
                    "text": text.strip(),
                    "speaker": getattr(verbalizer, "presenter_id", "model"),
                    "fallback_used": False,
                }
        except Exception:
            result["spoken"]["fallback_used"] = True
    return result


def list_container_contents(archive: ReplayArchive, question: str) -> dict[str, object]:
    """Answer "what is inside X" by reading the containment edges backwards.

    The projection already stores each edge as subject-predicate-object, so this
    reads the same active relations the location path reads, filtered the other
    way. No new claim, source, or authority is involved.
    """

    session = archive.load_latest()
    container_id = parse_container_question(
        question, allowed_entity_ids=_known_entities(session)
    )
    return _contents_result(session, container_id)


def answer_latest_timeline(archive: ReplayArchive, question: str) -> dict[str, object]:
    """Answer when the latest accepted relation for one object was recorded.

    This is a replay-relative history view.  A PTS converts to seconds only when
    its time base is retained with the claim; no wall-clock capture time is made up.
    """

    session = archive.load_latest()
    subject_id = parse_timeline_question(
        question, allowed_entity_ids=_known_entities(session)
    )
    candidates = [
        claim
        for claim in session.accepted_claims
        if claim.subject_id == subject_id and claim.operation.value == "assert"
    ]
    if not candidates:
        raise QuestionError(
            "this replay has no accepted relation for that object",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )
    claim = max(candidates, key=lambda item: (item.source_sequence, item.source_offset))
    position = claim.source_position
    event: dict[str, object] = {
        "claim_id": claim.claim_id,
        "object_id": claim.object_id,
        "predicate": claim.predicate.value,
        "source_offset": claim.source_offset,
        "source_sequence": claim.source_sequence,
        "subject_id": subject_id,
        "timestamp_basis": None if position is None else position.timestamp_basis.value,
    }
    subject = _CONTAINER_DISPLAY.get(subject_id, subject_id)
    target = _CONTAINER_DISPLAY.get(claim.object_id, claim.object_id)
    relation = "進入" if claim.predicate.value == "inside" else "移到"
    if (
        position is not None
        and position.pts is not None
        and position.time_base_numerator is not None
        and position.time_base_denominator not in (None, 0)
    ):
        seconds = position.pts * position.time_base_numerator / position.time_base_denominator
        event.update({"frame_index": position.frame_index, "pts": position.pts, "replay_seconds": seconds})
        text = f"這段固定錄畫的約 {seconds:.1f} 秒，記錄到{subject}{relation}{target}。"
    else:
        text = f"這段固定重播的第 {claim.source_sequence} 筆記錄，顯示{subject}{relation}{target}；沒有可換算的影片秒數。"
    event["text"] = text
    return {
        **_provenance(session),
        "schema": MEMORY_TIMELINE_SCHEMA,
        "query": {"parser_id": TIMELINE_PARSER_ID, "subject_id": subject_id, "stored": False},
        "event": event,
        "governance": {
            "data_scope": "D0_SYNTHETIC_OR_PUBLIC",
            "operate": "DISABLED",
            "physical_truth_claimed": False,
        },
    }


def _contents_result(session, container_id: str) -> dict[str, object]:
    # A thing can hold something two ways: inside it, or standing at it. The sofa
    # is a zone, so asking what is on it reads at_zone edges, not containment.
    held = sorted(
        (relation.predicate.value, relation.subject_id)
        for relation in session.projection.active_relations
        if relation.object_id == container_id
        and relation.predicate.value in ("inside", "at_zone")
    )
    contained = [subject_id for _, subject_id in held]
    container = _CONTAINER_DISPLAY.get(container_id, container_id)
    preposition = "上" if any(p == "at_zone" for p, _ in held) else "裡"
    if contained:
        names = "、".join(_CONTAINER_DISPLAY.get(item, item) for item in contained)
        text = f"在這段固定重播中，{container}{preposition}有{names}。"
    else:
        text = (
            f"在這段固定重播中，沒有有效證據顯示{container}裡面或上面有東西；"
            f"這不代表它是空的，只代表這段重播沒有記錄到。"
        )
    return {
        **_provenance(session),
        "schema": MEMORY_CONTENTS_SCHEMA,
        "query": {
            "parser_id": CONTENTS_PARSER_ID,
            "container_id": container_id,
            "stored": False,
        },
        "contents": {
            "container_id": container_id,
            "contained_entity_ids": contained,
            "text": text,
        },
        "governance": {
            "data_scope": "D0_SYNTHETIC_OR_PUBLIC",
            "operate": "DISABLED",
            "physical_truth_claimed": False,
        },
    }


_TRANSLATED_OPERATIONS = {
    "locate": lambda session, q, presenter: _location_result(
        session, q["subject"], presenter
    ),
    "verify": lambda session, q, presenter: _verification_result(
        session, q["subject"], q.get("target")
    ),
    "contents": lambda session, q, presenter: _contents_result(
        session, q["container"]
    ),
}


def _entities_not_named(question: str, query: Mapping[str, object]) -> tuple[str, ...]:
    """Entities the model resolved that the sentence never actually mentions.

    The translator is there to read unfamiliar sentence shapes, not to introduce
    objects. Asked where an umbrella was, it once answered locate/bag: the bag is
    a known entity, so every id check passed, and the projection returned FOUND
    with a real chain behind it. An answer about the wrong object carrying a
    genuine receipt is the one failure the chain exists to make impossible, so
    the name has to be in the sentence before the reading is accepted.
    """

    haystack = question.casefold()
    missing = []
    for field in ("subject", "target", "container"):
        entity_id = query.get(field)
        if not isinstance(entity_id, str):
            continue
        display = _CONTAINER_DISPLAY.get(entity_id, entity_id)
        if display.casefold() not in haystack and entity_id.casefold() not in haystack:
            missing.append(display)
    return tuple(missing)


def answer_by_translation(
    archive: ReplayArchive,
    question: str,
    translator: object,
    *,
    presenter: LocationPresenter | None = None,
) -> dict[str, object]:
    """Let a model choose the query when no deterministic parser recognized one.

    The model picks an operation and an entity from the replay's own list; the
    projection then answers exactly as it would have for a hand-parsed question.
    Its reading is recorded on the result so a wrong entity choice is visible
    next to the answer instead of hidden inside it.
    """

    session = archive.load_latest()
    query = translator.translate(question, _known_entities(session))
    if query is None or query["op"] == "reject":
        raise QuestionError(
            "這句我聽不出是在問哪個東西的位置",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )
    unnamed = _entities_not_named(question, query)
    if unnamed:
        raise QuestionError(
            "我把這句讀成在問" + "、".join(unnamed) + "，但您的句子裡沒有提到，所以不敢直接回答",
            error_code=ErrorCode.UNSUPPORTED_QUESTION,
        )
    result = _TRANSLATED_OPERATIONS[query["op"]](session, query, presenter)
    result["interpretation"] = {
        "translator_id": getattr(translator, "presenter_id", "model"),
        "operation": query["op"],
        "matched_text": query.get("matched_text"),
        "target_text": query.get("target_text"),
        "resolved": {
            key: value
            for key, value in query.items()
            if key in ("subject", "target", "container")
        },
    }
    return result
