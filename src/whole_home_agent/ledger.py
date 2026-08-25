"""Deterministic claim admission and session-ledger construction."""

from __future__ import annotations

from collections import defaultdict

from .errors import ClaimConflictError, CycleError, ErrorCode, FixtureError
from .model import (
    ClaimCandidate,
    ClaimCommit,
    ClaimOperation,
    Predicate,
    ReplayFixture,
    SessionLedger,
)


class ClaimCommitter:
    """Stateful, single-session admission boundary.

    The class is deliberately internal to orchestration in B0.  Its output is the
    immutable public ``ClaimCommit`` sequence rather than a second persistence API.
    """

    def __init__(self) -> None:
        self._accepted: list[ClaimCommit] = []
        self._by_identity: dict[str, ClaimCommit] = {}
        self._active_inside: set[tuple[str, str]] = set()
        self._last_new_source_sequence = -1

    def submit(self, candidate: ClaimCandidate) -> ClaimCommit:
        existing = self._by_identity.get(candidate.claim_id)
        if existing is not None:
            if existing.identity_payload() == candidate.identity_payload():
                return existing
            raise ClaimConflictError(
                f"claim_id {candidate.claim_id!r} was reused with a different payload",
                details={
                    "claim_id": candidate.claim_id,
                    "existing_source_sequence": existing.source_sequence,
                    "conflicting_source_sequence": candidate.source_sequence,
                    "source_offset": candidate.source_offset,
                },
            )

        if candidate.source_sequence < self._last_new_source_sequence:
            raise FixtureError(
                "new claim source_sequence moved behind the committed frontier",
                error_code=ErrorCode.SOURCE_ORDER,
                details={
                    "claim_id": candidate.claim_id,
                    "source_sequence": candidate.source_sequence,
                    "committed_frontier": self._last_new_source_sequence,
                    "source_offset": candidate.source_offset,
                },
            )

        if (
            candidate.operation is ClaimOperation.ASSERT
            and candidate.predicate is Predicate.INSIDE
            and self._would_create_cycle(candidate.subject_id, candidate.object_id)
        ):
            raise CycleError(
                "inside relation would create a containment cycle",
                details={
                    "claim_id": candidate.claim_id,
                    "subject_id": candidate.subject_id,
                    "object_id": candidate.object_id,
                    "source_sequence": candidate.source_sequence,
                },
            )

        commit = ClaimCommit(
            commit_index=len(self._accepted),
            claim_id=candidate.claim_id,
            source_sequence=candidate.source_sequence,
            source_offset=candidate.source_offset,
            operation=candidate.operation,
            subject_id=candidate.subject_id,
            predicate=candidate.predicate,
            object_id=candidate.object_id,
            epistemic_status=candidate.epistemic_status,
        )
        self._accepted.append(commit)
        self._by_identity[commit.claim_id] = commit
        self._last_new_source_sequence = candidate.source_sequence
        self._apply_containment(commit)
        return commit

    def snapshot(self) -> SessionLedger:
        return SessionLedger(accepted_claims=tuple(self._accepted), rejections=())

    def _apply_containment(self, commit: ClaimCommit) -> None:
        if commit.predicate is not Predicate.INSIDE:
            return
        edge = (commit.subject_id, commit.object_id)
        if commit.operation is ClaimOperation.ASSERT:
            self._active_inside.add(edge)
        else:
            self._active_inside.discard(edge)

    def _would_create_cycle(self, subject_id: str, object_id: str) -> bool:
        if subject_id == object_id:
            return True
        adjacency: dict[str, set[str]] = defaultdict(set)
        for child, container in self._active_inside:
            adjacency[child].add(container)

        pending = [object_id]
        visited: set[str] = set()
        while pending:
            node = pending.pop()
            if node == subject_id:
                return True
            if node in visited:
                continue
            visited.add(node)
            pending.extend(sorted(adjacency.get(node, ()), reverse=True))
        return False


def build_ledger(fixture: ReplayFixture) -> SessionLedger:
    committer = ClaimCommitter()
    for candidate in fixture.claims:
        committer.submit(candidate)
    return committer.snapshot()
