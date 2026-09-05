"""Repeatable local component ablation; no provider, camera or real device calls."""
from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

from whole_home_agent.actuation.models import ActionRequest, ActionType
from whole_home_agent.actuation.policy import ActionPolicy
from whole_home_agent.adapters.mock_actuator import MockActuator
from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
from whole_home_agent.fixture import load_fixture
from whole_home_agent.orchestrator import run_fixture
from whole_home_agent.memory_query import answer_question
from whole_home_agent.errors import B0Error
from whole_home_agent.presentation import DeterministicLocationPresenter
from whole_home_agent.rem_persona import RemLocationPresenter

ROOT = Path(__file__).resolve().parents[1]


def run_benchmark(repeats: int = 3) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    # Explicit expected outcomes: scored independently of response wording.
    questions = (
        ("鑰匙在哪裡", "FOUND", "sofa"),
        ("包包在哪裡", "FOUND", "sofa"),
        ("沙發在哪裡", "UNKNOWN", None),
        ("雨傘在哪裡", "REJECTED", None),
        ("錢包在哪裡", "REJECTED", None),
    )
    report = {"scope": "fixed synthetic semantic fixture and mock devices only",
              "repeats": repeats, "model_calls": 0, "physical_device_calls": 0,
              "limitations": "No real LLM comparison, household accuracy, user preference or safety certification.",
              "treatments": []}
    with tempfile.TemporaryDirectory() as directory:
        archive = SQLiteReplayArchive(Path(directory) / "memory.sqlite3")
        session = run_fixture(load_fixture(ROOT / "examples/fixtures/b0_key_bag_sofa_v1.json"),
                              replay_run_id="component-benchmark")
        archive.save_completed(session)
        report["semantic_hash"] = session.canonical_hash
        for name, presenter in (("template", DeterministicLocationPresenter()), ("persona", RemLocationPresenter())):
            rows = []
            for repeat in range(repeats):
                for question, expected, location in questions:
                    started = time.perf_counter()
                    try:
                        result = answer_question(archive, question, presenter=presenter)
                        answer = result["answer"]
                        actual, actual_location = answer["status"], answer["location_id"]
                        trace = answer["relation_path"]
                    except B0Error:
                        actual, actual_location, trace = "REJECTED", None, []
                    elapsed = (time.perf_counter() - started) * 1000
                    trace_ok = expected != "FOUND" or (
                        bool(trace) and trace[0]["subject_id"] in ("key", "bag")
                        and trace[-1]["object_id"] == location
                        and all(step["source_claim_id"] for step in trace))
                    rows.append({"question": question, "repeat": repeat, "expected": expected,
                                 "actual": actual, "location": actual_location,
                                 "passed": actual == expected and actual_location == location and trace_ok,
                                 "latency_ms": elapsed})
            report["treatments"].append({"name": name, "passed": sum(r["passed"] for r in rows),
                                         "total": len(rows), "median_latency_ms": statistics.median(r["latency_ms"] for r in rows),
                                         "cases": rows})
    requests = ((26, True), (18, True), (30, True), (16, False), (35, False))
    for enabled in (False, True):
        rows = []
        for temperature, allowed in requests:
            actuator = MockActuator()
            request = ActionRequest("living_room_ac", ActionType.SET_TEMPERATURE, {"temperature": temperature})
            denial = ActionPolicy().evaluate(request) if enabled else None
            if denial is None:
                actuator.execute(request)
            rows.append({"temperature": temperature, "expected_allowed": allowed,
                         "actual_allowed": denial is None, "passed": (denial is None) == allowed})
        report["treatments"].append({"name": "policy-on" if enabled else "policy-off-mock-only",
                                     "passed": sum(r["passed"] for r in rows), "total": len(rows), "cases": rows})
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    result = run_benchmark(args.repeats)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.write_text(text, encoding="utf-8")
    else:
        print(text)
    return int(any(t["passed"] != t["total"] for t in result["treatments"] if t["name"] != "policy-off-mock-only"))


if __name__ == "__main__":
    raise SystemExit(main())
