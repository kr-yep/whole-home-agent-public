"""Check one clean-clone, offline, project-generated teammate demo drill."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
from importlib import metadata
import io
import json
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import tomllib
from typing import Iterator, Mapping


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m33-teammate-clean-install-demo-drill-v1.toml"

from whole_home_agent.cli import main as cli_main


@contextlib.contextmanager
def _deny_network(counter: dict[str, int]) -> Iterator[None]:
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection

    def denied(*_args, **_kwargs):
        counter["attempts"] += 1
        raise RuntimeError("teammate demo drill denies network access")

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        socket.create_connection = original_create_connection


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        shell=False,
    )
    return result.stdout.strip()


def _git_bytes(*arguments: str, cwd: Path = ROOT) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        shell=False,
    )
    return result.stdout


def _versioned_text_hashes(
    path: Path, *, repository_root: Path = ROOT, revision: str = "HEAD"
) -> tuple[str, str, bool]:
    relative_path = path.relative_to(repository_root).as_posix()
    git_blob = _git_bytes("show", f"{revision}:{relative_path}", cwd=repository_root)
    git_blob_sha256 = hashlib.sha256(git_blob).hexdigest()
    worktree_sha256 = _sha256(path)
    return git_blob_sha256, worktree_sha256, git_blob_sha256 == worktree_sha256


def _validate_artifact_identity(
    *, lock_git_blob_sha256: str, manifest_sha256: str, contract: Mapping[str, object]
) -> list[str]:
    if (
        lock_git_blob_sha256 != contract["frozen_text_input"][1]["sha256"]
        or manifest_sha256 != contract["expected_source"]["manifest_sha256"]
    ):
        return ["LOCK_OR_MANIFEST"]
    return []


def _semantic_document(payload: Mapping[str, object]) -> dict[str, object]:
    answer = dict(payload.get("answer", {}))
    answer.pop("replay_run_id", None)
    return {
        "answer": answer,
        "claims": payload.get("claims"),
        "governance": payload.get("governance"),
        "relation_quality": dict(payload.get("relation_evaluation", {})).get("quality"),
        "source": payload.get("source"),
        "source_diagnostics": payload.get("source_diagnostics"),
        "warnings": payload.get("warnings"),
    }


def _relation_signatures(answer: Mapping[str, object]) -> list[str]:
    return [
        "|".join((str(step.get("subject_id")), str(step.get("predicate")), str(step.get("object_id"))))
        for step in answer.get("relation_path", ())
    ]


def validate_payload(
    payload: Mapping[str, object], contract: Mapping[str, object]
) -> list[str]:
    failures: list[str] = []
    expected_source = contract["expected_source"]
    source = payload.get("source", {})
    if (
        source.get("source_id"),
        source.get("source_revision"),
        source.get("content_hash"),
        source.get("license"),
        source.get("frame_count"),
    ) != (
        expected_source["source_id"],
        expected_source["source_revision"],
        expected_source["source_content_sha256"],
        expected_source["source_license"],
        expected_source["source_frame_count"],
    ):
        failures.append("SOURCE")

    expected_output = contract["expected_output"]
    governance = payload.get("governance", {})
    if (
        governance.get("mode") != expected_output["governance_mode"]
        or governance.get("operate") != expected_output["governance_operate"]
        or governance.get("physical_truth_claimed")
        is not expected_output["physical_truth_claimed"]
    ):
        failures.append("GOVERNANCE")

    expected_answer = contract["expected_answer"]
    answer = payload.get("answer", {})
    if (
        answer.get("status"),
        answer.get("subject_id"),
        answer.get("location_id"),
        answer.get("epistemic_status"),
        answer.get("world_scope"),
        answer.get("as_of_source_sequence"),
        len(answer.get("source_claim_ids", ())),
    ) != (
        expected_answer["status"],
        expected_answer["subject_id"],
        expected_answer["location_id"],
        expected_answer["epistemic_status"],
        expected_answer["world_scope"],
        expected_answer["as_of_source_sequence"],
        expected_answer["source_claim_count"],
    ):
        failures.append("SCOPED_ANSWER")
    if _relation_signatures(answer) != expected_answer["relation_path"]:
        failures.append("RELATION_TRACE")

    claims = payload.get("claims", ())
    if len(claims) != expected_output["claim_count"] or not all(
        claim.get("evidence") for claim in claims
    ):
        failures.append("CLAIMS")
    if payload.get("run_receipt", {}).get("status") != expected_output["run_receipt_status"]:
        failures.append("RUN_RECEIPT")
    if len(payload.get("frames", ())) != expected_output["frames_in_compact_output"]:
        failures.append("RUN_RECEIPT")
    return failures


def _resolved_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution in ("whole-home-agent", "av", "numpy", "Pillow", "streamlit"):
        try:
            versions[distribution] = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            versions[distribution] = "NOT_INSTALLED"
    return versions


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--clone-elapsed-ms", required=True, type=float)
    parser.add_argument("--install-elapsed-ms", required=True, type=float)
    parser.add_argument("--run-id", default="m33-teammate-drill")
    return parser


def check(arguments: argparse.Namespace) -> dict[str, object]:
    contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    failures: list[str] = []
    actual_revision = _git("rev-parse", "HEAD")
    worktree_clean = _git("status", "--porcelain") == ""
    if actual_revision != arguments.expected_revision or not worktree_clean:
        failures.append("REVISION")

    manifest_path = ROOT / contract["expected_source"]["manifest_path"]
    lock_git_blob_hash, lock_worktree_hash, lock_representation_matches = (
        _versioned_text_hashes(ROOT / "uv.lock")
    )
    manifest_hash = _sha256(manifest_path)
    failures.extend(
        _validate_artifact_identity(
            lock_git_blob_sha256=lock_git_blob_hash,
            manifest_sha256=manifest_hash,
            contract=contract,
        )
    )

    counter = {"attempts": 0}
    stdout = io.StringIO()
    stderr = io.StringIO()
    demo_start = time.perf_counter()
    payload: dict[str, object] = {}
    exit_code = -1
    try:
        with _deny_network(counter), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = cli_main(["demo-recorded", "--compact", "--run-id", arguments.run_id])
        payload = json.loads(stdout.getvalue())
    except json.JSONDecodeError:
        failures.append("OUTPUT_PARSE")
    except Exception:
        failures.append("UNEXPECTED")
    demo_elapsed_ms = (time.perf_counter() - demo_start) * 1000.0

    if exit_code != 0:
        failures.append("CLI")
    if counter["attempts"] != contract["expected_output"]["network_attempt_count"]:
        failures.append("NETWORK")
    if payload:
        failures.extend(validate_payload(payload, contract))

    budgets = contract["time_budget_ms"]
    total_elapsed_ms = arguments.clone_elapsed_ms + arguments.install_elapsed_ms + demo_elapsed_ms
    if (
        arguments.clone_elapsed_ms > budgets["clone_maximum"]
        or arguments.install_elapsed_ms > budgets["install_maximum"]
        or demo_elapsed_ms > budgets["demo_maximum"]
        or total_elapsed_ms > budgets["total_maximum"]
    ):
        failures.append("TIME_BUDGET")

    failures = sorted(set(failures))
    semantic_document = _semantic_document(payload) if payload else {}
    semantic_bytes = json.dumps(
        semantic_document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": 1,
        "status": "PASS" if not failures else "STOP",
        "failure_classes": failures,
        "revision": actual_revision,
        "worktree_clean": worktree_clean,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "resolved_versions": _resolved_versions(),
        "uv_lock_git_blob_sha256": lock_git_blob_hash,
        "uv_lock_worktree_sha256": lock_worktree_hash,
        "uv_lock_worktree_representation_matches_git_blob": lock_representation_matches,
        "manifest_sha256": manifest_hash,
        "source_content_sha256": contract["expected_source"]["source_content_sha256"],
        "network_attempt_count": counter["attempts"],
        "clone_elapsed_ms": round(arguments.clone_elapsed_ms, 3),
        "install_elapsed_ms": round(arguments.install_elapsed_ms, 3),
        "demo_elapsed_ms": round(demo_elapsed_ms, 3),
        "total_elapsed_ms": round(total_elapsed_ms, 3),
        "semantic_sha256": hashlib.sha256(semantic_bytes).hexdigest(),
        "output_summary": {
            "answer": payload.get("answer") if payload else None,
            "claim_count": len(payload.get("claims", ())) if payload else 0,
            "governance": payload.get("governance") if payload else None,
            "run_receipt_status": payload.get("run_receipt", {}).get("status") if payload else None,
        },
        "cleanup_required": True,
        "evidence_limit": "one clean-clone synthetic offline drill; no real-home, CV-gain, live, or operation claim",
    }


def main(argv: list[str] | None = None) -> int:
    receipt = check(_parser().parse_args(argv))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
