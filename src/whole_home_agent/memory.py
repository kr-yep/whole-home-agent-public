"""Narrow application contracts for durable, replay-scoped D0 memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .model import ReplaySession


ARCHIVE_SCHEMA = "whole-home-agent.replay-archive.v1"


@dataclass(frozen=True, slots=True)
class ArchiveWriteReceipt:
    """Result of one idempotent completed-session archive write."""

    status: str
    world_scope: str
    replay_run_id: str
    canonical_hash: str

    def as_dict(self) -> dict[str, str]:
        return {
            "schema": ARCHIVE_SCHEMA,
            "status": self.status,
            "world_scope": self.world_scope,
            "replay_run_id": self.replay_run_id,
            "canonical_hash": self.canonical_hash,
        }


class ReplayArchive(Protocol):
    """Completed-session store; it has no media, action, policy, or credential handle."""

    def save_completed(self, session: ReplaySession) -> ArchiveWriteReceipt:
        """Atomically save one complete D0 replay session."""

    def load_latest(self) -> ReplaySession:
        """Restore and verify the latest completed replay session."""
