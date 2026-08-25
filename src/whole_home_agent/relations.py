"""Pure relation projection and evidence-traceable location queries."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .model import (
    AnswerTrace,
    ClaimCommit,
    ClaimOperation,
    Predicate,
    ProjectionRelation,
    ProjectionState,
    QueryRequest,
    QueryStatus,
    RelationStep,
)

if TYPE_CHECKING:
    from .model import ReplaySession


def reduce_relations(
    claims: tuple[ClaimCommit, ...], *, as_of_source_sequence: int | None = None
) -> ProjectionState:
    """Fold accepted commits into a deterministic set-valued relation projection."""

    maximum_frontier = max((claim.source_sequence for claim in claims), default=0)
    frontier = maximum_frontier if as_of_source_sequence is None else as_of_source_sequence
    active: dict[tuple[str, Predicate, str], ProjectionRelation] = {}
    for claim in claims:
        if claim.source_sequence > frontier:
            continue
        key = (claim.subject_id, claim.predicate, claim.object_id)
        if claim.operation is ClaimOperation.ASSERT:
            active[key] = ProjectionRelation(
                subject_id=claim.subject_id,
                predicate=claim.predicate,
                object_id=claim.object_id,
                source_claim_id=claim.claim_id,
                source_sequence=claim.source_sequence,
                source_offset=claim.source_offset,
            )
        else:
            active.pop(key, None)

    relations = tuple(
        sorted(
            active.values(),
            key=lambda relation: (
                relation.subject_id,
                relation.predicate.value,
                relation.object_id,
                relation.source_sequence,
                relation.source_offset,
                relation.source_claim_id,
            ),
        )
    )
    return ProjectionState(frontier=frontier, active_relations=relations)


@dataclass(frozen=True, slots=True)
class _Resolution:
    candidates: tuple[tuple[str, tuple[RelationStep, ...]], ...]
    conflict: bool
    reason: str


def _resolve_location(projection: ProjectionState, subject_id: str) -> _Resolution:
    inside: dict[str, list[ProjectionRelation]] = defaultdict(list)
    at_zone: dict[str, list[ProjectionRelation]] = defaultdict(list)
    for relation in projection.active_relations:
        target = inside if relation.predicate is Predicate.INSIDE else at_zone
        target[relation.subject_id].append(relation)

    def to_step(relation: ProjectionRelation) -> RelationStep:
        return RelationStep(
            subject_id=relation.subject_id,
            predicate=relation.predicate,
            object_id=relation.object_id,
            source_claim_id=relation.source_claim_id,
            source_sequence=relation.source_sequence,
            source_offset=relation.source_offset,
        )

    def walk(
        node: str,
        path: tuple[RelationStep, ...],
        ancestors: frozenset[str],
    ) -> _Resolution:
        if node in ancestors:
            return _Resolution((), True, "containment cycle encountered in projection")

        zone_edges = sorted(
            at_zone.get(node, ()),
            key=lambda edge: (edge.object_id, edge.source_sequence, edge.source_claim_id),
        )
        inside_edges = sorted(
            inside.get(node, ()),
            key=lambda edge: (edge.object_id, edge.source_sequence, edge.source_claim_id),
        )
        local_conflict = len({edge.object_id for edge in zone_edges}) > 1 or len(
            {edge.object_id for edge in inside_edges}
        ) > 1
        candidates: list[tuple[str, tuple[RelationStep, ...]]] = [
            (edge.object_id, path + (to_step(edge),)) for edge in zone_edges
        ]
        reasons: list[str] = []
        if local_conflict:
            reasons.append(f"multiple active locations or containers for {node!r}")

        next_ancestors = ancestors | {node}
        for edge in inside_edges:
            nested = walk(
                edge.object_id,
                path + (to_step(edge),),
                next_ancestors,
            )
            candidates.extend(nested.candidates)
            local_conflict = local_conflict or nested.conflict
            if nested.reason:
                reasons.append(nested.reason)

        candidates.sort(
            key=lambda item: (
                item[0],
                len(item[1]),
                tuple(step.source_claim_id for step in item[1]),
            )
        )
        return _Resolution(tuple(candidates), local_conflict, "; ".join(dict.fromkeys(reasons)))

    return walk(subject_id, (), frozenset())


def _trace(
    session: ReplaySession,
    request: QueryRequest,
    *,
    status: QueryStatus,
    projection_frontier: int,
    location_id: str | None = None,
    path: tuple[RelationStep, ...] = (),
    candidates: tuple[str, ...] = (),
    epistemic_status: str | None = None,
    reason: str,
) -> AnswerTrace:
    return AnswerTrace(
        status=status,
        location_id=location_id,
        relation_path=path,
        source_claim_ids=tuple(step.source_claim_id for step in path),
        world_scope=session.world_scope,
        replay_run_id=session.replay_run_id,
        as_of_source_sequence=request.as_of_source_sequence,
        projection_frontier=projection_frontier,
        source_content_hash=session.source_content_hash,
        validator_version=session.validator_version,
        projector_version=session.projector_version,
        epistemic_status=(
            epistemic_status
            if epistemic_status is not None
            else status.value.lower()
        ),
        candidate_location_ids=candidates,
        reason=reason,
    )


def locate(session: ReplaySession, request: QueryRequest) -> AnswerTrace:
    """Resolve a location only inside an explicit fixture/run/frontier scope."""

    if (
        not request.world_scope
        or not request.replay_run_id
        or request.as_of_source_sequence is None
    ):
        return _trace(
            session,
            request,
            status=QueryStatus.SCOPE_REQUIRED,
            projection_frontier=session.projection_frontier,
            reason="world_scope, replay_run_id, and as_of_source_sequence are required",
        )

    if (
        request.world_scope != session.world_scope
        or request.replay_run_id != session.replay_run_id
    ):
        return _trace(
            session,
            request,
            status=QueryStatus.OUT_OF_SCOPE,
            projection_frontier=session.projection_frontier,
            reason="query scope does not match this replay session",
        )

    as_of = request.as_of_source_sequence
    if type(as_of) is not int or as_of < 0 or as_of > session.projection_frontier:
        return _trace(
            session,
            request,
            status=QueryStatus.FRONTIER_MISMATCH,
            projection_frontier=session.projection_frontier,
            reason="as_of_source_sequence is outside the committed replay frontier",
        )

    projection = reduce_relations(
        session.accepted_claims, as_of_source_sequence=as_of
    )
    resolution = _resolve_location(projection, request.subject_id)
    distinct_locations = tuple(sorted({item[0] for item in resolution.candidates}))
    if resolution.conflict or len(distinct_locations) > 1:
        return _trace(
            session,
            request,
            status=QueryStatus.CONFLICT,
            projection_frontier=projection.frontier,
            candidates=distinct_locations,
            reason=resolution.reason or "active evidence supports conflicting locations",
        )
    if not resolution.candidates:
        return _trace(
            session,
            request,
            status=QueryStatus.UNKNOWN,
            projection_frontier=projection.frontier,
            reason="no active evidence resolves the subject to a zone",
        )

    location_id = distinct_locations[0]
    matching_paths = [
        path for candidate, path in resolution.candidates if candidate == location_id
    ]
    path = min(
        matching_paths,
        key=lambda value: (
            len(value),
            tuple(step.source_claim_id for step in value),
        ),
    )
    return _trace(
        session,
        request,
        status=QueryStatus.FOUND,
        projection_frontier=projection.frontier,
        location_id=location_id,
        path=path,
        candidates=(location_id,),
        epistemic_status=(
            "estimated"
            if any(step.predicate is Predicate.INSIDE for step in path)
            else "reported"
        ),
        reason="location resolved from active reported relations",
    )
