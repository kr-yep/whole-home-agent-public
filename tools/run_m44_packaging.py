"""Run the single M44 explicit-cache build/install/installed-demo attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import tomllib
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SCRATCH_ROOT = ROOT.parent.resolve()
CONTRACT = ROOT / "configs" / "evaluation" / "m44-explicit-cache-packaging-v1.toml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitized_environment(source: Mapping[str, str], cache_root: Path) -> dict[str, str]:
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
    environment = {key: value for key, value in source.items() if key.upper() in allowed}
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "UV_CACHE_DIR": str(cache_root),
            "UV_NO_CONFIG": "1",
            "UV_OFFLINE": "1",
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )
    return environment


def expected_scratch_paths() -> dict[str, Path]:
    return {
        "source": SCRATCH_ROOT / "m44-packaging-worktree",
        "dist": SCRATCH_ROOT / "m44-release-dist",
        "venv": SCRATCH_ROOT / "m44-release-venv",
        "run": SCRATCH_ROOT / "m44-release-run",
    }


def validate_paths(
    source: Path, cache: Path, dist: Path, venv: Path, run: Path
) -> list[str]:
    expected = expected_scratch_paths()
    failures: list[str] = []
    values = {"source": source, "dist": dist, "venv": venv, "run": run}
    for key, value in values.items():
        if value.resolve(strict=False) != expected[key].resolve(strict=False):
            failures.append("SCRATCH_PATH")
        if not value.resolve(strict=False).is_relative_to(SCRATCH_ROOT):
            failures.append("SCRATCH_CONFINEMENT")
    expected_cache = (ROOT / ".tmp" / "m44-uv-cache").resolve(strict=False)
    if cache.resolve(strict=False) != expected_cache or not cache.resolve().is_relative_to(ROOT):
        failures.append("CACHE_PATH")
    if not source.is_dir() or not cache.is_dir() or cache.is_symlink():
        failures.append("INPUT_PATH")
    if any(path.exists() for path in (dist, venv, run)):
        failures.append("OUTPUT_NOT_NEW")
    return sorted(set(failures))


def build_command(uv: Path, python: Path, cache: Path, dist: Path) -> list[str]:
    return [
        str(uv),
        "--offline",
        "--no-config",
        "--no-python-downloads",
        "--cache-dir",
        str(cache),
        "build",
        "--no-build-isolation",
        "--python",
        str(python),
        "--out-dir",
        str(dist),
    ]


def venv_command(uv: Path, python: Path, cache: Path, venv: Path) -> list[str]:
    return [
        str(uv),
        "--offline",
        "--no-config",
        "--no-python-downloads",
        "--cache-dir",
        str(cache),
        "venv",
        "--python",
        str(python),
        str(venv),
    ]


def install_command(uv: Path, venv_python: Path, cache: Path, wheel: Path) -> list[str]:
    return [
        str(uv),
        "--offline",
        "--no-config",
        "--no-python-downloads",
        "--cache-dir",
        str(cache),
        "pip",
        "install",
        "--python",
        str(venv_python),
        f"{wheel}[demo]",
    ]


def _run(
    command: Sequence[str], *, cwd: Path, environment: Mapping[str, str]
) -> tuple[subprocess.CompletedProcess[str], float]:
    start = time.perf_counter()
    process = subprocess.run(
        list(command),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
        env=dict(environment),
    )
    return process, (time.perf_counter() - start) * 1000.0


def _git_source_identity(source: Path, revision: str) -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    values: dict[str, object] = {"revision": "", "tracked_clean": False, "untracked_count": -1}
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=source, check=False, capture_output=True, text=True
        )
        diff = subprocess.run(["git", "diff", "--quiet"], cwd=source, check=False)
        cached = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=source, check=False)
        untracked_process = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=source,
            check=False,
            capture_output=True,
            text=True,
        )
        untracked = tuple(line for line in untracked_process.stdout.splitlines() if line)
        values = {
            "revision": head.stdout.strip(),
            "tracked_clean": diff.returncode == 0 and cached.returncode == 0,
            "untracked_count": len(untracked),
        }
        if (
            head.returncode != 0
            or values["revision"] != revision
            or not values["tracked_clean"]
            or untracked
            or untracked_process.returncode != 0
        ):
            failures.append("SOURCE_IDENTITY")
    except OSError:
        failures.append("SOURCE_IDENTITY")
    return failures, values


def _preflight_versions(
    uv: Path, python: Path, environment: Mapping[str, str], contract: Mapping[str, object]
) -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    values: dict[str, object] = {}
    script = (
        "import importlib.metadata as m,json,platform;"
        "print(json.dumps({'python':platform.python_version(),"
        "'setuptools':m.version('setuptools'),'wheel':m.version('wheel')}))"
    )
    try:
        uv_process = subprocess.run(
            [str(uv), "--version"], check=False, capture_output=True, text=True, shell=False, env=dict(environment)
        )
        python_process = subprocess.run(
            [str(python), "-I", "-B", "-c", script],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            env=dict(environment),
        )
        python_values = json.loads(python_process.stdout) if python_process.returncode == 0 else {}
        uv_version = uv_process.stdout.strip().split()[1] if uv_process.returncode == 0 else ""
        values = {"uv": uv_version, **python_values}
        expected = contract["build_environment"]
        if values != {
            "uv": expected["uv_semantic_version"],
            "python": expected["python"],
            "setuptools": expected["setuptools"],
            "wheel": expected["wheel"],
        }:
            failures.append("BUILD_ENVIRONMENT")
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        failures.append("BUILD_ENVIRONMENT")
    return failures, values


def _installed_versions(
    python: Path, cwd: Path, environment: Mapping[str, str]
) -> tuple[list[str], dict[str, str]]:
    script = (
        "import importlib.metadata as m,json;"
        "print(json.dumps({n:m.version(n) for n in "
        "['whole-home-agent','av','numpy','pillow','streamlit']}))"
    )
    process, _elapsed = _run([str(python), "-I", "-B", "-c", script], cwd=cwd, environment=environment)
    if process.returncode != 0:
        return ["INSTALLED_VERSIONS"], {}
    try:
        return [], json.loads(process.stdout)
    except json.JSONDecodeError:
        return ["INSTALLED_VERSIONS"], {}


def execute(arguments: argparse.Namespace) -> dict[str, object]:
    contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    failures = validate_paths(
        arguments.source, arguments.cache, arguments.dist, arguments.venv, arguments.run
    )
    source_failures, source_identity = _git_source_identity(arguments.source, arguments.revision)
    failures.extend(source_failures)
    environment = sanitized_environment(os.environ, arguments.cache)
    version_failures, build_environment = _preflight_versions(
        arguments.uv, arguments.build_python, environment, contract
    )
    failures.extend(version_failures)

    stages: dict[str, dict[str, object]] = {}
    artifacts: dict[str, object] = {}
    installed_versions: dict[str, str] = {}
    installed_receipt: dict[str, object] = {}
    total_start = time.perf_counter()

    if not failures:
        arguments.dist.mkdir()
        arguments.run.mkdir()
        process, elapsed = _run(
            build_command(arguments.uv, arguments.build_python, arguments.cache, arguments.dist),
            cwd=arguments.source,
            environment=environment,
        )
        stages["build"] = {
            "exit_code": process.returncode,
            "elapsed_ms": round(elapsed, 3),
            "stdout_present": bool(process.stdout.strip()),
            "stderr_present": bool(process.stderr.strip()),
        }
        if process.returncode != 0:
            failures.append("BUILD")
        wheels = tuple(arguments.dist.glob("*.whl"))
        sdists = tuple(arguments.dist.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            failures.append("ARTIFACT_COUNT")
        else:
            artifacts = {
                "wheel_name": wheels[0].name,
                "wheel_bytes": wheels[0].stat().st_size,
                "wheel_sha256": sha256(wheels[0]),
                "sdist_name": sdists[0].name,
                "sdist_bytes": sdists[0].stat().st_size,
                "sdist_sha256": sha256(sdists[0]),
            }

    fresh_python = arguments.venv / "Scripts" / "python.exe"
    if not failures:
        process, elapsed = _run(
            venv_command(arguments.uv, arguments.build_python, arguments.cache, arguments.venv),
            cwd=arguments.run,
            environment=environment,
        )
        stages["venv"] = {
            "exit_code": process.returncode,
            "elapsed_ms": round(elapsed, 3),
            "stdout_present": bool(process.stdout.strip()),
            "stderr_present": bool(process.stderr.strip()),
        }
        if process.returncode != 0 or not fresh_python.is_file():
            failures.append("VENV")

    if not failures:
        wheel = next(arguments.dist.glob("*.whl"))
        process, elapsed = _run(
            install_command(arguments.uv, fresh_python, arguments.cache, wheel),
            cwd=arguments.run,
            environment=environment,
        )
        stages["install"] = {
            "exit_code": process.returncode,
            "elapsed_ms": round(elapsed, 3),
            "stdout_present": bool(process.stdout.strip()),
            "stderr_present": bool(process.stderr.strip()),
        }
        if process.returncode != 0:
            failures.append("INSTALL")

    if not failures:
        version_errors, installed_versions = _installed_versions(
            fresh_python, arguments.run, environment
        )
        failures.extend(version_errors)
        expected_versions = {
            "whole-home-agent": contract["installed_dependency_expectation"]["whole_home_agent"],
            "av": contract["installed_dependency_expectation"]["av"],
            "numpy": contract["installed_dependency_expectation"]["numpy"],
            "pillow": contract["installed_dependency_expectation"]["pillow"],
            "streamlit": contract["installed_dependency_expectation"]["streamlit"],
        }
        if installed_versions != expected_versions:
            failures.append("INSTALLED_VERSIONS")

    if not failures:
        wheel = next(arguments.dist.glob("*.whl"))
        sdist = next(arguments.dist.glob("*.tar.gz"))
        checker = arguments.source / contract["frozen_input"]["m41_checker"]
        build_elapsed = float(stages["build"]["elapsed_ms"])
        install_elapsed = float(stages["venv"]["elapsed_ms"]) + float(
            stages["install"]["elapsed_ms"]
        )
        command = [
            str(fresh_python),
            "-B",
            str(checker),
            "--wheel",
            str(wheel),
            "--sdist",
            str(sdist),
            "--expected-revision",
            arguments.revision,
            "--build-elapsed-ms",
            str(build_elapsed),
            "--install-elapsed-ms",
            str(install_elapsed),
            "--run-id",
            "m44-installed-demo",
        ]
        process, elapsed = _run(command, cwd=arguments.run, environment=environment)
        stages["installed_check"] = {
            "exit_code": process.returncode,
            "elapsed_ms": round(elapsed, 3),
            "stdout_present": bool(process.stdout.strip()),
            "stderr_present": bool(process.stderr.strip()),
        }
        try:
            installed_receipt = json.loads(process.stdout)
        except json.JSONDecodeError:
            failures.append("INSTALLED_CHECK_RECEIPT")
        if process.returncode != 0 or installed_receipt.get("status") != "PASS":
            failures.append("INSTALLED_CHECK")

    total_elapsed_ms = (time.perf_counter() - total_start) * 1000.0
    budgets = contract["time_budget_ms"]
    if total_elapsed_ms > float(budgets["total_maximum"]):
        failures.append("TOTAL_TIME_BUDGET")
    for key, budget_key in (
        ("build", "build_maximum"),
        ("venv", "venv_maximum"),
        ("install", "install_maximum"),
        ("installed_check", "installed_check_maximum"),
    ):
        if key in stages and float(stages[key]["elapsed_ms"]) > float(budgets[budget_key]):
            failures.append("STAGE_TIME_BUDGET")

    failures = sorted(set(failures))
    demo = installed_receipt.get("demo", {}) if installed_receipt else {}
    return {
        "schema_version": 1,
        "status": "PASS" if not failures else "STOP",
        "failure_classes": failures,
        "source": source_identity,
        "build_environment": build_environment,
        "stages": stages,
        "artifacts": artifacts,
        "installed_versions": installed_versions,
        "installed_check": {
            "status": installed_receipt.get("status") if installed_receipt else None,
            "failure_classes": installed_receipt.get("failure_classes", [])
            if installed_receipt
            else [],
            "demo": demo,
        },
        "total_elapsed_ms": round(total_elapsed_ms, 3),
        "network": {
            "uv_offline_flag_set": True,
            "configuration_discovery_disabled": True,
            "python_downloads_disabled": True,
            "proxy_index_token_or_credential_forwarded": False,
            "os_level_network_instrumented": False,
            "demo_python_socket_attempt_count": demo.get("network_attempt_count"),
        },
        "cleanup_required": any(
            path.exists()
            for path in (arguments.cache, arguments.dist, arguments.venv, arguments.run, arguments.source)
        ),
        "operate_enabled": False,
        "evidence_limit": "one exact-revision local explicit-cache package/install/demo attempt; upstream cache provenance, OS-level zero network, teammate/public CI, real-home, and operation remain unestablished",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", required=True, type=Path)
    parser.add_argument("--build-python", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--dist", required=True, type=Path)
    parser.add_argument("--venv", required=True, type=Path)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--revision", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    receipt = execute(_parser().parse_args(argv))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
