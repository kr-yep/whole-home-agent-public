"""Command-line adapter for the offline B0 replay/query slice."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .errors import B0Error
from .fixture import load_fixture
from .model import AnswerTrace, QueryRequest
from .orchestrator import run_fixture
from .public_demo import run_public_demo
from .relations import locate


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whole-home-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    replay = subparsers.add_parser(
        "replay", help="replay one local D0 fixture and query an entity"
    )
    replay.add_argument("fixture", type=Path)
    replay.add_argument("--entity", required=True, help="subject identifier to locate")
    replay.add_argument(
        "--as-of", required=True, type=int, dest="as_of", help="source sequence frontier"
    )
    replay.add_argument("--run-id", dest="run_id", help="explicit replay run scope")
    demo = subparsers.add_parser(
        "demo-recorded",
        help="run the fixed, allowlisted, project-generated prerecorded B1 demo",
    )
    demo.add_argument(
        "--entity",
        choices=("key", "bag", "sofa"),
        default="key",
        help="manifest entity to locate (default: key)",
    )
    demo.add_argument(
        "--run-id", dest="run_id", default="public-b1-demo-001"
    )
    demo.add_argument(
        "--compact",
        action="store_true",
        help="omit the per-frame presentation timeline from JSON output",
    )
    return parser


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
        "source_content_hash": answer.source_content_hash,
        "source_claim_ids": list(answer.source_claim_ids),
        "status": answer.status.value,
        "subject_id": answer.subject_id,
        "validator_version": answer.validator_version,
        "projector_version": answer.projector_version,
        "world_scope": answer.world_scope,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "demo-recorded":
            payload = run_public_demo(
                replay_run_id=arguments.run_id,
                subject_id=arguments.entity,
                include_frames=not arguments.compact,
            )
        elif arguments.command == "replay":
            fixture = load_fixture(arguments.fixture)
            session = run_fixture(fixture, replay_run_id=arguments.run_id)
            answer = locate(
                session,
                QueryRequest(
                    subject_id=arguments.entity,
                    world_scope=session.world_scope,
                    replay_run_id=session.replay_run_id,
                    as_of_source_sequence=arguments.as_of,
                ),
            )
            payload = {
                "answer": _answer_dict(answer),
                "canonical_hash": session.canonical_hash,
                "fixture_id": session.fixture_id,
                "fixture_revision": session.fixture_revision,
            }
        else:  # pragma: no cover - argparse is closed.
            parser.error(f"unsupported command: {arguments.command}")
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except B0Error as error:
        print(
            json.dumps(error.as_dict(), ensure_ascii=False, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
