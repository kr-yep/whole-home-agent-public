"""Perception-to-memory bridge connecting camera observations to SQLite replay archive.

Debounces raw detections from camera ingest, verifies idempotency against the current
replay state, and commits strictly-typed, traceable spatial claims to the SQLite archive
under D0/B0/B1 invariants (epistemic status ESTIMATED, zero raw frame storage).
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .adapters.sqlite_archive import SQLiteReplayArchive
from .errors import B0Error, ErrorCode
from .ledger import build_ledger_from_candidates
from .model import (
    ClaimCandidate,
    ClaimCommit,
    ClaimOperation,
    EpistemicStatus,
    EvidenceRef,
    Predicate,
    ProducerRef,
    ReplaySession,
    SourceDescriptor,
    SourcePosition,
    TimestampBasis,
)
from .relations import reduce_relations
from .serialization import canonical_json, semantic_document
from .sources import validate_candidate

logger = logging.getLogger(__name__)

# Standard mapping from COCO class labels to canonical entity IDs
COCO_TO_ENTITY_MAP: dict[str, str] = {
    "cell phone": "phone",
    "cup": "cup",
    "bottle": "bottle",
    "laptop": "laptop",
    "backpack": "bag",
    "handbag": "bag",
    "couch": "sofa",
    "chair": "chair",
    "dining table": "table",
    "book": "book",
    "scissors": "scissors",
    "remote": "remote",
    "mouse": "mouse",
    "keyboard": "keyboard",
    "clock": "clock",
}

# Household semantic aliasing:
# In indoor residential settings, dark rectangular handheld electronics predominantly represent phones,
# and drink tumblers/bottles represent cups/drink containers.
HOUSEHOLD_ALIASES: dict[str, str] = {
    "remote": "phone",
    "bottle": "cup",
}

DEFAULT_MIN_STABLE_FRAMES: int = 3
DEFAULT_MIN_CONFIDENCE: float = 0.25


@dataclass(frozen=True, slots=True)
class BridgeCommitResult:
    """Result receipt returned when an observation is processed."""

    status: str  # "COMMITTED", "UNCHANGED", "REFUSED"
    subject_id: str
    zone_id: str
    operation: str
    claim_id: str
    replay_run_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "subject_id": self.subject_id,
            "zone_id": self.zone_id,
            "operation": self.operation,
            "claim_id": self.claim_id,
            "replay_run_id": self.replay_run_id,
            "details": self.details,
        }


class PerceptionBridge:
    """Thread-safe debouncing bridge from camera detections to SQLite replay archive."""

    def __init__(
        self,
        archive: SQLiteReplayArchive,
        *,
        default_zone: str = "desk",
        min_stable_frames: int = DEFAULT_MIN_STABLE_FRAMES,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        enable_household_aliases: bool = True,
    ) -> None:
        self._archive = archive
        self._default_zone = default_zone
        self._min_stable_frames = max(1, min_stable_frames)
        self._min_confidence = min_confidence
        self._enable_household_aliases = enable_household_aliases
        self._last_enrollment_status: dict[str, Any] | None = None
        self._lock = threading.RLock()
        # Track consecutive detections: (subject_id, zone_id) -> count
        self._consecutive_counts: dict[tuple[str, str], int] = {}
        # Cached active zone per subject: subject_id -> zone_id
        self._active_locations: dict[str, str] = {}
        self._sync_active_locations()

    def _sync_active_locations(self) -> None:
        """Read current active relations from the archive into the local cache."""
        try:
            session = self._archive.load_latest()
            self._active_locations.clear()
            for rel in session.projection.active_relations:
                if rel.predicate == Predicate.AT_ZONE:
                    self._active_locations[rel.subject_id] = rel.object_id
        except Exception as error:
            logger.debug("Could not sync active locations on bridge init: %s", error)

    def resolve_entity_id(
        self,
        raw_label: str,
        *,
        apply_household_aliases: bool = False,
    ) -> str | None:
        """Resolve a detector label to a canonical entity ID."""
        if not isinstance(raw_label, str) or not raw_label.strip():
            return None
        cleaned = raw_label.strip().lower()

        # 1. Household alias override when requested
        if apply_household_aliases and cleaned in HOUSEHOLD_ALIASES:
            return HOUSEHOLD_ALIASES[cleaned]

        # 2. Direct COCO mapping
        if cleaned in COCO_TO_ENTITY_MAP:
            return COCO_TO_ENTITY_MAP[cleaned]

        # 2. Check custom user entity registry if available
        try:
            from .entity_registry import get_global_registry

            registry = get_global_registry()
            for entity in registry.list_entities():
                if entity.get("entity_id", "").lower() == cleaned:
                    return entity["entity_id"]
                if entity.get("display_name", "").lower() == cleaned:
                    return entity["entity_id"]
                if entity.get("visual_category", "").lower() == cleaned:
                    return entity["entity_id"]
                for alias in entity.get("aliases", []):
                    if alias.lower() == cleaned:
                        return entity["entity_id"]
        except Exception:
            pass

        # 3. Valid sanitized identifier fallback
        slug = re.sub(r"[^a-zA-Z0-9_]+", "_", cleaned).strip("_")
        if slug and len(slug) <= 64:
            return slug
        return None

    def _make_candidate(
        self,
        *,
        subject_id: str,
        predicate: Predicate,
        object_id: str,
        operation: ClaimOperation,
        sequence: int,
        descriptor: SourceDescriptor,
        confidence: float,
    ) -> ClaimCandidate:
        """Construct and validate a canonical ClaimCandidate."""
        if descriptor.timestamp_basis == TimestampBasis.MEDIA_PTS:
            pos = SourcePosition(
                source_sequence=sequence,
                source_offset=sequence,
                timestamp_basis=TimestampBasis.MEDIA_PTS,
                frame_index=sequence,
                pts=sequence * 1000,
                time_base_numerator=1,
                time_base_denominator=1000,
            )
        else:
            pos = SourcePosition(
                source_sequence=sequence,
                source_offset=sequence,
                timestamp_basis=descriptor.timestamp_basis,
            )

        producer = ProducerRef(
            component="whole_home_agent.perception_bridge",
            version="1.0.0",
            artifact_hash=hashlib.sha256(b"whole_home_agent.perception_bridge.v1").hexdigest(),
            config_hash=hashlib.sha256(b"perception_bridge_config_v1").hexdigest(),
        )

        op_str = "assert" if operation == ClaimOperation.ASSERT else "retract"
        ev = EvidenceRef(
            evidence_id=f"ev-cam-{subject_id}-{object_id}-{sequence}",
            source_id=descriptor.source_id,
            start=pos,
            end=pos,
            confidence=round(confidence, 2),
            quality="perception_report",
        )

        cand = ClaimCandidate(
            claim_id=f"cam:{subject_id}:{op_str}:{predicate.value}:{object_id}:seq{sequence}",
            source_sequence=sequence,
            source_offset=sequence,
            operation=operation,
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            epistemic_status=EpistemicStatus.ESTIMATED,
            source_position=pos,
            producer_ref=producer,
            evidence_refs=(ev,),
        )
        validate_candidate(cand, descriptor)
        return cand

    def commit_observation(
        self,
        subject_id: str,
        zone_id: str,
        confidence: float = 0.85,
    ) -> BridgeCommitResult:
        """Commit an observed subject location to the SQLite replay archive."""
        with self._lock:
            session = self._archive.load_latest()
            desc = session.source_descriptor

            # Sync active relations to determine current location
            current_zone = None
            active_for_subj: list[tuple[Predicate, str]] = []
            for rel in session.projection.active_relations:
                if rel.subject_id == subject_id:
                    active_for_subj.append((rel.predicate, rel.object_id))
                    if rel.predicate == Predicate.AT_ZONE:
                        current_zone = rel.object_id

            # Idempotency check: already at this exact zone
            if current_zone == zone_id:
                self._active_locations[subject_id] = zone_id
                return BridgeCommitResult(
                    status="UNCHANGED",
                    subject_id=subject_id,
                    zone_id=zone_id,
                    operation="ASSERT",
                    claim_id=f"cam:{subject_id}:assert:at_zone:{zone_id}",
                    replay_run_id=session.replay_run_id,
                    details={"reason": "already located at target zone"},
                )

            # Reconstruct prior candidates
            prev_candidates = [
                ClaimCandidate(
                    claim_id=c.claim_id,
                    source_sequence=c.source_sequence,
                    source_offset=c.source_offset,
                    operation=c.operation,
                    subject_id=c.subject_id,
                    predicate=c.predicate,
                    object_id=c.object_id,
                    epistemic_status=c.epistemic_status,
                    source_position=c.source_position,
                    producer_ref=c.producer_ref,
                    evidence_refs=c.evidence_refs,
                )
                for c in session.accepted_claims
            ]

            next_seq = max((c.source_sequence for c in session.accepted_claims), default=0) + 1
            new_candidates: list[ClaimCandidate] = []

            # Retract existing active relations for this subject to prevent conflicts
            for pred, obj in active_for_subj:
                retract_cand = self._make_candidate(
                    subject_id=subject_id,
                    predicate=pred,
                    object_id=obj,
                    operation=ClaimOperation.RETRACT,
                    sequence=next_seq,
                    descriptor=desc,
                    confidence=confidence,
                )
                new_candidates.append(retract_cand)
                next_seq += 1

            # Assert new at_zone relation
            assert_cand = self._make_candidate(
                subject_id=subject_id,
                predicate=Predicate.AT_ZONE,
                object_id=zone_id,
                operation=ClaimOperation.ASSERT,
                sequence=next_seq,
                descriptor=desc,
                confidence=confidence,
            )
            new_candidates.append(assert_cand)

            all_candidates = tuple(prev_candidates + new_candidates)
            new_ledger = build_ledger_from_candidates(all_candidates)
            new_proj = reduce_relations(new_ledger.accepted_claims)
            new_semantic = canonical_json(semantic_document(desc, new_ledger, new_proj))
            new_hash = hashlib.sha256(new_semantic.encode("utf-8")).hexdigest()

            base_run_id = session.replay_run_id.split("-c")[0]
            new_run_id = f"{base_run_id}-c{next_seq}"

            new_session = ReplaySession(
                fixture_id=session.fixture_id,
                fixture_revision=session.fixture_revision,
                world_scope=session.world_scope,
                replay_run_id=new_run_id,
                projection_frontier=new_proj.frontier,
                source_content_hash=session.source_content_hash,
                validator_version=session.validator_version,
                projector_version=session.projector_version,
                ledger=new_ledger,
                projection=new_proj,
                semantic_output=new_semantic,
                canonical_hash=new_hash,
                source_descriptor=desc,
            )

            receipt = self._archive.save_completed(new_session)
            self._active_locations[subject_id] = zone_id

            logger.info(
                "Committed perception observation: %s at_zone %s (run=%s, hash=%s)",
                subject_id,
                zone_id,
                new_run_id,
                receipt.canonical_hash[:8],
            )
            return BridgeCommitResult(
                status="COMMITTED",
                subject_id=subject_id,
                zone_id=zone_id,
                operation="ASSERT",
                claim_id=assert_cand.claim_id,
                replay_run_id=new_run_id,
                details={
                    "receipt_status": receipt.status,
                    "canonical_hash": receipt.canonical_hash,
                    "retracted_count": len(active_for_subj),
                },
            )

    def get_enrollment_status(self) -> dict[str, Any] | None:
        with self._lock:
            if self._last_enrollment_status is not None:
                return self._last_enrollment_status
            try:
                from .adapters.visual_matcher import get_global_matcher

                session = get_global_matcher().get_active_session()
                if session is not None:
                    return session.progress()
            except Exception:
                pass
            return None

    def start_visual_enrollment(
        self,
        entity_id: str,
        display_name: str,
        *,
        target_samples: int = 5,
    ) -> Any:
        from .adapters.visual_matcher import get_global_matcher

        return get_global_matcher().start_session(
            entity_id,
            display_name,
            target_samples=target_samples,
        )

    def process_detections(
        self,
        detections: list[dict[str, Any]],
        *,
        zone_id: str | None = None,
        frame_payload: bytes | None = None,
    ) -> list[dict[str, Any]]:
        """Process one frame of detections, applying debounce accumulation and committing when stable."""
        target_zone = (zone_id or self._default_zone).strip().lower()
        if not target_zone:
            target_zone = "desk"

        with self._lock:
            # 1. Visual enrollment & feature matching if payload provided
            decoded_img = None
            if frame_payload:
                try:
                    import io
                    from PIL import Image

                    decoded_img = Image.open(io.BytesIO(frame_payload)).convert("RGB")
                except Exception as error:
                    logger.debug("Failed to decode frame_payload: %s", error)

            try:
                from .adapters.visual_matcher import get_global_matcher

                matcher = get_global_matcher()
                active_session = matcher.get_active_session()

                if active_session is not None:
                    if decoded_img is not None and detections:
                        # Feed the largest/most prominent box to enrollment
                        best_box = max(detections, key=lambda d: float(d.get("w", 0)) * float(d.get("h", 0)))
                        bx = max(0, int(best_box.get("x", 0)))
                        by = max(0, int(best_box.get("y", 0)))
                        bw = int(best_box.get("w", 0))
                        bh = int(best_box.get("h", 0))
                        if bw >= 24 and bh >= 24 and decoded_img.width > bx and decoded_img.height > by:
                            crop = decoded_img.crop(
                                (bx, by, min(decoded_img.width, bx + bw), min(decoded_img.height, by + bh))
                            )
                            self._last_enrollment_status = matcher.feed_crop(crop)
                        else:
                            self._last_enrollment_status = active_session.progress()
                    else:
                        self._last_enrollment_status = active_session.progress()
                else:
                    self._last_enrollment_status = None
                    # Visual feature verification on boxes if enrolled objects exist
                    if decoded_img is not None:
                        for det in detections:
                            bx = max(0, int(det.get("x", 0)))
                            by = max(0, int(det.get("y", 0)))
                            bw = int(det.get("w", 0))
                            bh = int(det.get("h", 0))
                            if bw >= 24 and bh >= 24 and decoded_img.width > bx and decoded_img.height > by:
                                crop = decoded_img.crop(
                                    (bx, by, min(decoded_img.width, bx + bw), min(decoded_img.height, by + bh))
                                )
                                matched_id, score = matcher.match(crop)
                                if matched_id:
                                    det["visual_matched"] = True
                                    det["matched_entity"] = matched_id
                                    det["visual_score"] = round(score, 3)
            except Exception as error:
                logger.debug("Visual matching step failed: %s", error)

            # Aggregate highest confidence per subject_id in current frame
            frame_entities: dict[str, float] = {}
            for det in detections:
                conf = float(det.get("confidence", 0.0))
                if conf < self._min_confidence:
                    continue
                if det.get("visual_matched") and det.get("matched_entity"):
                    subject_id = det["matched_entity"]
                else:
                    raw_label = det.get("raw_label") or det.get("label", "")
                    subject_id = self.resolve_entity_id(
                        raw_label,
                        apply_household_aliases=self._enable_household_aliases,
                    )
                if not subject_id:
                    continue
                frame_entities[subject_id] = max(frame_entities.get(subject_id, 0.0), conf)

            commit_results: list[dict[str, Any]] = []

            # Increment consecutive counts for detected entities
            for subject_id, conf in frame_entities.items():
                key = (subject_id, target_zone)
                self._consecutive_counts[key] = self._consecutive_counts.get(key, 0) + 1

                if self._consecutive_counts[key] >= self._min_stable_frames:
                    # Check if already active at this zone
                    if self._active_locations.get(subject_id) != target_zone:
                        res = self.commit_observation(
                            subject_id=subject_id,
                            zone_id=target_zone,
                            confidence=conf,
                        )
                        commit_results.append(res.as_dict())

            # Decay or reset counts for entities not seen in this frame
            for key in list(self._consecutive_counts.keys()):
                subj, z = key
                if z == target_zone and subj not in frame_entities:
                    self._consecutive_counts[key] -= 1
                    if self._consecutive_counts[key] <= 0:
                        self._consecutive_counts.pop(key, None)

            return commit_results
