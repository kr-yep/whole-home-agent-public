"""Validate one offline wheel/sdist install and the installed M40 demo boundary."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
from importlib import metadata
import io
import json
from pathlib import Path, PurePosixPath
import platform
import socket
import subprocess
import sys
import tarfile
import time
import tomllib
from typing import Iterator, Mapping, Sequence
from unittest import mock
import zipfile

import whole_home_agent
from whole_home_agent import public_demo
from whole_home_agent.cli import main as cli_main


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m41-release-candidate-packaging-v1.toml"


@contextlib.contextmanager
def deny_network(counter: dict[str, int]) -> Iterator[None]:
    """Deny the Python socket entry points used by the closed demo process."""

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection

    def denied(*_args, **_kwargs):
        counter["attempts"] += 1
        raise RuntimeError("M41 installed demo denies network access")

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        socket.create_connection = original_create_connection


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_git(arguments: Sequence[str], *, binary: bool = False):
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=not binary,
        shell=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("git could not verify the M41 source revision")
    return completed.stdout


def _source_identity(contract: Mapping[str, object]) -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    revision = str(_run_git(["rev-parse", "HEAD"])).strip()
    tracked_clean = (
        subprocess.run(["git", "diff", "--quiet"], cwd=ROOT, check=False).returncode == 0
        and subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=ROOT, check=False
        ).returncode
        == 0
    )
    untracked = tuple(
        line
        for line in str(
            _run_git(["ls-files", "--others", "--exclude-standard"])
        ).splitlines()
        if line
    )
    lock_bytes = _run_git(["show", "HEAD:uv.lock"], binary=True)
    identities = {
        "revision": revision,
        "tracked_clean": tracked_clean,
        "untracked_count": len(untracked),
        "m40_result_sha256": sha256(ROOT / str(contract["m40_result"])),
        "pyproject_sha256": sha256(ROOT / "pyproject.toml"),
        "uv_lock_git_blob_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "presentation_module_sha256": sha256(
            ROOT / "src" / "whole_home_agent" / "presentation.py"
        ),
    }
    if not tracked_clean or untracked:
        failures.append("SOURCE_CLEANLINESS")
    for key in (
        "m40_result_sha256",
        "pyproject_sha256",
        "uv_lock_git_blob_sha256",
        "presentation_module_sha256",
    ):
        if identities[key] != contract[key]:
            failures.append("SOURCE_IDENTITY")
    return failures, identities


def _safe_member_name(name: str) -> bool:
    if not name or "\\" in name or name.startswith("/"):
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _content_contract_failures(
    names: Sequence[str], *, required_suffixes: Sequence[str], forbidden_fragments: Sequence[str],
    forbidden_suffixes: Sequence[str]
) -> list[str]:
    failures: list[str] = []
    if any(not _safe_member_name(name.rstrip("/")) for name in names if name.rstrip("/")):
        failures.append("UNSAFE_ARCHIVE_PATH")
    if any(not any(name.endswith(suffix) for name in names) for suffix in required_suffixes):
        failures.append("MISSING_REQUIRED_MEMBER")
    lowered = [name.lower() for name in names]
    if any(fragment.lower() in name for name in lowered for fragment in forbidden_fragments):
        failures.append("FORBIDDEN_ARCHIVE_MEMBER")
    if any(name.endswith(tuple(suffix.lower() for suffix in forbidden_suffixes)) for name in lowered):
        failures.append("FORBIDDEN_ARCHIVE_MEMBER")
    return failures


def inspect_artifacts(
    wheel: Path, sdist: Path, contract: Mapping[str, object]
) -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    maximum_bytes = int(contract["build"]["maximum_artifact_bytes_each"])
    if not wheel.is_file() or not sdist.is_file():
        return ["ARTIFACT_MISSING"], {}
    if wheel.stat().st_size > maximum_bytes or sdist.stat().st_size > maximum_bytes:
        failures.append("ARTIFACT_SIZE")

    wheel_names: list[str] = []
    wheel_uncompressed = 0
    installed_presentation_hash = ""
    try:
        with zipfile.ZipFile(wheel) as archive:
            infos = archive.infolist()
            wheel_names = [item.filename for item in infos]
            wheel_uncompressed = sum(item.file_size for item in infos)
            if any(item.flag_bits & 0x1 for item in infos):
                failures.append("ENCRYPTED_ARCHIVE_MEMBER")
            presentation_members = [
                item for item in infos if item.filename.endswith("whole_home_agent/presentation.py")
            ]
            if len(presentation_members) == 1:
                installed_presentation_hash = hashlib.sha256(
                    archive.read(presentation_members[0])
                ).hexdigest()
            else:
                failures.append("PRESENTATION_MEMBER_IDENTITY")
    except (OSError, zipfile.BadZipFile):
        failures.append("WHEEL_PARSE")

    wheel_contract = contract["wheel_contract"]
    failures.extend(
        _content_contract_failures(
            wheel_names,
            required_suffixes=wheel_contract["required_suffixes"],
            forbidden_fragments=wheel_contract["forbidden_prefix_fragments"],
            forbidden_suffixes=wheel_contract["forbidden_suffixes"],
        )
    )

    sdist_names: list[str] = []
    sdist_uncompressed = 0
    try:
        with tarfile.open(sdist, mode="r:gz") as archive:
            members = archive.getmembers()
            sdist_names = [item.name for item in members]
            sdist_uncompressed = sum(item.size for item in members if item.isfile())
            if any(not (item.isfile() or item.isdir()) for item in members):
                failures.append("UNSAFE_ARCHIVE_MEMBER_TYPE")
    except (OSError, tarfile.TarError):
        failures.append("SDIST_PARSE")

    sdist_contract = contract["sdist_contract"]
    failures.extend(
        _content_contract_failures(
            sdist_names,
            required_suffixes=sdist_contract["required_suffixes"],
            forbidden_fragments=sdist_contract["forbidden_path_fragments"],
            forbidden_suffixes=sdist_contract["forbidden_suffixes"],
        )
    )

    maximum_members = int(contract["build"]["maximum_archive_members_each"])
    maximum_uncompressed = int(contract["build"]["maximum_uncompressed_bytes_each"])
    if (
        len(wheel_names) > maximum_members
        or len(sdist_names) > maximum_members
        or wheel_uncompressed > maximum_uncompressed
        or sdist_uncompressed > maximum_uncompressed
    ):
        failures.append("ARCHIVE_BUDGET")
    if installed_presentation_hash != contract["presentation_module_sha256"]:
        failures.append("PRESENTATION_MEMBER_IDENTITY")

    return sorted(set(failures)), {
        "wheel_path_name": wheel.name,
        "wheel_bytes": wheel.stat().st_size,
        "wheel_sha256": sha256(wheel),
        "wheel_member_count": len(wheel_names),
        "wheel_uncompressed_bytes": wheel_uncompressed,
        "sdist_path_name": sdist.name,
        "sdist_bytes": sdist.stat().st_size,
        "sdist_sha256": sha256(sdist),
        "sdist_member_count": len(sdist_names),
        "sdist_uncompressed_bytes": sdist_uncompressed,
        "wheel_presentation_sha256": installed_presentation_hash,
    }


def _relation_signatures(answer: Mapping[str, object]) -> list[str]:
    return [
        "|".join(
            (
                str(step.get("subject_id")),
                str(step.get("predicate")),
                str(step.get("object_id")),
            )
        )
        for step in answer.get("relation_path", ())
    ]


def validate_demo(payload: Mapping[str, object], contract: Mapping[str, object]) -> list[str]:
    failures: list[str] = []
    answer = payload.get("answer", {})
    expected_answer = contract["expected_answer"]
    if (
        answer.get("status"),
        answer.get("subject_id"),
        answer.get("location_id"),
        answer.get("epistemic_status"),
        _relation_signatures(answer),
    ) != (
        expected_answer["status"],
        expected_answer["subject_id"],
        expected_answer["location_id"],
        expected_answer["epistemic_status"],
        expected_answer["relation_path"],
    ):
        failures.append("ANSWER")
    if (
        payload.get("run_receipt", {}).get("status")
        != expected_answer["run_receipt_status"]
        or len(payload.get("frames", ())) != expected_answer["frames_in_compact_output"]
    ):
        failures.append("RUN_RECEIPT")
    governance = payload.get("governance", {})
    if (
        governance.get("operate") != expected_answer["operate"]
        or governance.get("physical_truth_claimed")
        is not expected_answer["physical_truth_claimed"]
    ):
        failures.append("GOVERNANCE")

    expected_presentation = contract["expected_presentation"]
    presentation = payload.get("presentation", {})
    if (
        presentation.get("schema"),
        presentation.get("context_schema"),
        presentation.get("presenter_id"),
        presentation.get("status"),
        presentation.get("fallback_used"),
        presentation.get("failure_code"),
        presentation.get("text"),
        payload.get("answer_summary"),
    ) != (
        expected_presentation["result_schema"],
        expected_presentation["context_schema"],
        expected_presentation["presenter_id"],
        expected_presentation["status"],
        expected_presentation["fallback_used"],
        None,
        expected_presentation["text"],
        expected_presentation["text"],
    ):
        failures.append("PRESENTATION")
    if any(
        fragment in str(payload.get("answer_summary", ""))
        for fragment in expected_presentation["forbidden_text_fragments"]
    ):
        failures.append("TEMPORAL_OVERCLAIM")
    context = payload.get("language_context", {})
    if context.get("schema") != expected_presentation["context_schema"]:
        failures.append("CONTEXT")
    return failures


def validate_fallback(
    normal: Mapping[str, object], fallback: Mapping[str, object], contract: Mapping[str, object]
) -> list[str]:
    failures: list[str] = []
    semantic_fields = ("subject_id", "status", "location_id", "epistemic_status", "relation_path")
    if any(normal.get("answer", {}).get(key) != fallback.get("answer", {}).get(key) for key in semantic_fields):
        failures.append("FALLBACK_ANSWER")
    expected = contract["expected_fallback"]
    presentation = fallback.get("presentation", {})
    if (
        presentation.get("status"),
        presentation.get("failure_code"),
        presentation.get("text"),
        fallback.get("answer_summary"),
    ) != (expected["status"], expected["failure_code"], expected["text"], expected["text"]):
        failures.append("FALLBACK_PRESENTATION")
    if "must-not-escape" in json.dumps(presentation, ensure_ascii=False):
        failures.append("FALLBACK_EXCEPTION_LEAK")
    return failures


class _ThrowingPresenter:
    presenter_id = "m41-throwing/1"

    def present(self, context):
        raise RuntimeError("m41-private-detail-must-not-escape")


def _installed_environment_failures(contract: Mapping[str, object]) -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    package_path = Path(whole_home_agent.__file__).resolve()
    prefix = Path(sys.prefix).resolve()
    cwd = Path.cwd().resolve()
    if sys.prefix == sys.base_prefix:
        failures.append("FRESH_VIRTUAL_ENVIRONMENT")
    if package_path.is_relative_to(ROOT) or not package_path.is_relative_to(prefix):
        failures.append("INSTALLED_IMPORT")
    if cwd.is_relative_to(ROOT):
        failures.append("RUN_LOCATION")
    installed_presentation = package_path.parent / "presentation.py"
    installed_hash = sha256(installed_presentation) if installed_presentation.is_file() else ""
    if installed_hash != contract["presentation_module_sha256"]:
        failures.append("INSTALLED_PRESENTATION_IDENTITY")
    try:
        package_version = metadata.version("whole-home-agent")
    except metadata.PackageNotFoundError:
        package_version = "NOT_INSTALLED"
    if package_version != contract["installed_environment"]["package_version"]:
        failures.append("INSTALLED_VERSION")
    return failures, {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "virtual_environment": sys.prefix != sys.base_prefix,
        "package_version": package_version,
        "package_inside_fresh_prefix": package_path.is_relative_to(prefix),
        "package_outside_source": not package_path.is_relative_to(ROOT),
        "working_directory_outside_source": not cwd.is_relative_to(ROOT),
        "installed_presentation_sha256": installed_hash,
    }


def check(arguments: argparse.Namespace) -> dict[str, object]:
    contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    failures, source = _source_identity(contract)
    if source.get("revision") != arguments.expected_revision:
        failures.append("REVISION")
    artifact_failures, artifacts = inspect_artifacts(arguments.wheel, arguments.sdist, contract)
    failures.extend(artifact_failures)
    environment_failures, environment = _installed_environment_failures(contract)
    failures.extend(environment_failures)

    counter = {"attempts": 0}
    payload: dict[str, object] = {}
    fallback: dict[str, object] = {}
    stdout = io.StringIO()
    stderr = io.StringIO()
    demo_start = time.perf_counter()
    exit_code = -1
    try:
        with deny_network(counter), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = cli_main(
                ["demo-recorded", "--compact", "--run-id", arguments.run_id]
            )
            payload = json.loads(stdout.getvalue())
            with mock.patch.object(
                public_demo,
                "DeterministicLocationPresenter",
                return_value=_ThrowingPresenter(),
            ):
                fallback = public_demo.run_public_demo(
                    replay_run_id=f"{arguments.run_id}-fallback",
                    include_frames=False,
                )
    except Exception:
        failures.append("DEMO_EXCEPTION")
    demo_elapsed_ms = (time.perf_counter() - demo_start) * 1000.0
    if exit_code != 0:
        failures.append("DEMO_EXIT")
    if counter["attempts"] != contract["network"]["demo_python_socket_attempt_count"]:
        failures.append("NETWORK")
    if payload:
        failures.extend(validate_demo(payload, contract))
    if payload and fallback:
        failures.extend(validate_fallback(payload, fallback, contract))
    else:
        failures.append("FALLBACK_MISSING")

    budgets = contract["time_budget_ms"]
    total_elapsed_ms = arguments.build_elapsed_ms + arguments.install_elapsed_ms + demo_elapsed_ms
    if (
        arguments.build_elapsed_ms > budgets["build_maximum"]
        or arguments.install_elapsed_ms > budgets["install_maximum"]
        or demo_elapsed_ms > budgets["demo_maximum"]
        or total_elapsed_ms > budgets["total_maximum"]
    ):
        failures.append("TIME_BUDGET")
    failures = sorted(set(failures))
    return {
        "schema_version": 1,
        "status": "PASS" if not failures else "STOP",
        "failure_classes": failures,
        "source": source,
        "artifacts": artifacts,
        "environment": environment,
        "demo": {
            "exit_code": exit_code,
            "network_attempt_count": counter["attempts"],
            "elapsed_ms": round(demo_elapsed_ms, 3),
            "answer_status": payload.get("answer", {}).get("status") if payload else None,
            "answer_location_id": payload.get("answer", {}).get("location_id") if payload else None,
            "presentation_status": payload.get("presentation", {}).get("status") if payload else None,
            "presentation_text": payload.get("presentation", {}).get("text") if payload else None,
            "fallback_status": fallback.get("presentation", {}).get("status") if fallback else None,
            "fallback_failure_code": fallback.get("presentation", {}).get("failure_code") if fallback else None,
            "structured_answer_retained_on_fallback": bool(payload and fallback)
            and not validate_fallback(payload, fallback, contract),
        },
        "timing_ms": {
            "build": round(arguments.build_elapsed_ms, 3),
            "install": round(arguments.install_elapsed_ms, 3),
            "demo": round(demo_elapsed_ms, 3),
            "total": round(total_elapsed_ms, 3),
        },
        "cleanup_required": True,
        "operate_enabled": False,
        "evidence_limit": "one local exact-revision offline package/install/demo run; no public CI, teammate, provider, real-home, or operation claim",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--sdist", required=True, type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--build-elapsed-ms", required=True, type=float)
    parser.add_argument("--install-elapsed-ms", required=True, type=float)
    parser.add_argument("--run-id", default="m41-installed-demo")
    return parser


def main(argv: list[str] | None = None) -> int:
    receipt = check(_parser().parse_args(argv))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
