"""Run the frozen M28 offline primary-demo acceptance checks."""

from __future__ import annotations

import contextlib
import argparse
import io
import json
from pathlib import Path
import socket
import sys
import tomllib
from typing import Iterator


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from whole_home_agent.cli import main as cli_main
from whole_home_agent.public_demo import run_public_demo


CONTRACT = ROOT / "configs" / "evaluation" / "m28-primary-demo-acceptance-v1.toml"
STREAMLIT = ROOT / "src" / "whole_home_agent" / "streamlit_app.py"
JUDGE_CARD = ROOT / "docs" / "judge-demo-card.md"
USE_CLASS = "COMMITTED_D0_SYNTHETIC_PRIMARY_DEMO"


@contextlib.contextmanager
def _deny_network(counter: dict[str, int]) -> Iterator[None]:
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection

    def denied(*_args, **_kwargs):
        counter["attempts"] += 1
        raise RuntimeError("M28 acceptance denies network access")

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        socket.create_connection = original_create_connection


def _semantic_document(result: dict[str, object]) -> dict[str, object]:
    answer = dict(result["answer"])
    answer.pop("replay_run_id", None)
    perception = result["perception_evaluation"]
    relation = result["relation_evaluation"]
    return {
        "source": result["source"],
        "governance": result["governance"],
        "answer": answer,
        "claims": result["claims"],
        "source_diagnostics": result["source_diagnostics"],
        "warnings": result["warnings"],
        "perception_quality": perception["quality"],
        "relation_quality": relation["quality"],
    }


def _claim_signature(claim: dict[str, object]) -> tuple[object, ...]:
    evidence = claim["evidence"][0]
    return (
        claim["operation"],
        claim["predicate"],
        claim["subject_id"],
        claim["object_id"],
        claim["epistemic_status"],
        claim["source_position"]["frame_index"],
        evidence["start"]["frame_index"],
        evidence["end"]["frame_index"],
    )


def _assert_result(
    result: dict[str, object], contract: dict[str, object], failures: list[str]
) -> None:
    source = result.get("source", {})
    expected_source = (
        contract["source_id"],
        contract["source_revision"],
        contract["source_content_sha256"],
        contract["source_license"],
        contract["source_frame_count"],
    )
    actual_source = (
        source.get("source_id"),
        source.get("source_revision"),
        source.get("content_hash"),
        source.get("license"),
        source.get("frame_count"),
    )
    if actual_source != expected_source:
        failures.append("SOURCE_IDENTITY")
    governance = result.get("governance", {})
    if governance != {
        "allowed_data": "D0_SYNTHETIC",
        "mode": "OFFLINE_PRERECORDED_REPLAY",
        "operate": "DISABLED",
        "physical_truth_claimed": False,
    }:
        failures.append("GOVERNANCE_BOUNDARY")
    answer = result.get("answer", {})
    if (
        answer.get("status"),
        answer.get("location_id"),
        answer.get("epistemic_status"),
        len(answer.get("relation_path", ())),
        len(answer.get("source_claim_ids", ())),
        bool(answer.get("world_scope")),
        answer.get("as_of_source_sequence") is not None,
    ) != ("FOUND", "sofa", "estimated", 2, 2, True, True):
        failures.append("SCOPED_ANSWER")
    expected_claims = [
        (
            item["operation"],
            item["predicate"],
            item["subject_id"],
            item["object_id"],
            item["epistemic_status"],
            item["confirmation_frame"],
            item["evidence_start_frame"],
            item["evidence_end_frame"],
        )
        for item in contract["expected_claim"]
    ]
    actual_claims = [_claim_signature(item) for item in result.get("claims", ())]
    if actual_claims != expected_claims:
        failures.append("EXACT_EVIDENCE_TRACE")
    if len(result.get("warnings", ())) < contract["expected_limits"]["warning_count_minimum"]:
        failures.append("EVIDENCE_LIMITS")
    diagnostics = result.get("source_diagnostics", {})
    if diagnostics.get("abstentions") != [] or diagnostics.get("completed") is not True:
        failures.append("EASY_REPLAY_DIAGNOSTICS")
    if not result.get("run_receipt"):
        failures.append("RUN_RECEIPT")


def _assert_presentation(failures: list[str]) -> None:
    source = STREAMLIT.read_text(encoding="utf-8")
    required = (
        "OPERATE DISABLED",
        "1 · Fixed public replay",
        "2 · Ask: Where is the key?",
        "3 · What the system connected",
        "5 · Abstention behavior",
        "Traceable answer JSON",
        "Run receipt",
        "Evidence limits",
    )
    if any(text not in source for text in required):
        failures.append("PRESENTATION_REQUIRED_SECTIONS")
    forbidden_widgets = ("file_uploader(", "camera_input(", "chat_input(", "text_input(")
    if any(text in source for text in forbidden_widgets):
        failures.append("PRESENTATION_OPEN_INPUT")
    if 'st.subheader("4 · Fixed-fixture evaluation' in source:
        failures.append("PERFECT_METRICS_PRIMARY_VISIBLE")
    if "Optional synthetic fixture metrics — not indoor evidence" not in source:
        failures.append("METRICS_NOT_COLLAPSED_OR_LABELED")
    if "Ambiguous, unsupported, " not in source or "interrupted cases" not in source:
        failures.append("FAIL_CLOSED_TEXT")


def _assert_judge_card(failures: list[str]) -> None:
    if not JUDGE_CARD.is_file():
        failures.append("JUDGE_CARD_MISSING")
        return
    source = JUDGE_CARD.read_text(encoding="utf-8")
    required = (
        "0–10 seconds",
        "10–30 seconds",
        "30–55 seconds",
        "55–75 seconds",
        "75–90 seconds",
        "Windows PowerShell",
        "macOS / Linux",
        "demo-recorded --compact",
        "Recovery",
        "Do not claim",
    )
    if any(text not in source for text in required):
        failures.append("JUDGE_CARD_INCOMPLETE")


def check() -> dict[str, object]:
    contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    if contract.get("status") != "FROZEN_BEFORE_COMMITTED_DEMO_EXECUTION":
        raise RuntimeError("M28 contract identity changed")
    counter = {"attempts": 0}
    with _deny_network(counter):
        direct = run_public_demo(
            replay_run_id=contract["run_ids"][0], include_frames=False
        )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "demo-recorded",
                    "--compact",
                    "--run-id",
                    contract["run_ids"][1],
                ]
            )
        cli_result = json.loads(stdout.getvalue()) if exit_code == 0 else {}
    failures: list[str] = []
    if exit_code != 0:
        failures.append("COMPACT_CLI_EXIT")
    _assert_result(direct, contract, failures)
    _assert_result(cli_result, contract, failures)
    direct_semantic = _semantic_document(direct)
    cli_semantic = _semantic_document(cli_result)
    if direct_semantic != cli_semantic:
        failures.append("SEMANTIC_NONDETERMINISM")
    _assert_presentation(failures)
    _assert_judge_card(failures)
    failures = sorted(set(failures))
    semantic_bytes = (
        json.dumps(direct_semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    import hashlib

    return {
        "schema_version": 1,
        "gate_id": contract["gate_id"],
        "decision": contract["decision"]["pass"] if not failures else contract["decision"]["normal_stop"],
        "acceptance_run_count": 2,
        "interfaces": [contract["execution"]["first_run_interface"], contract["execution"]["second_run_interface"]],
        "network_attempt_count": counter["attempts"],
        "semantic_outputs_equal": direct_semantic == cli_semantic,
        "semantic_sha256": hashlib.sha256(semantic_bytes).hexdigest(),
        "failure_codes": failures,
        "source": direct.get("source"),
        "answer": direct.get("answer"),
        "claims": direct.get("claims"),
        "warnings": direct.get("warnings"),
        "operate_enabled": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acknowledge-use-class", choices=(USE_CLASS,), required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    _parser().parse_args(argv)
    receipt = check()
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if not receipt["failure_codes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
