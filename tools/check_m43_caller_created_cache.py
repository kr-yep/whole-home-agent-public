"""Verify caller-created uv cache semantics without building or installing anything."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import tomllib
from typing import Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m43-caller-created-uv-cache-v1.toml"
TARGET_RELATIVE = Path(".tmp") / "m43-uv-cache"
Runner = Callable[..., subprocess.CompletedProcess[str]]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def target_has_exact_ignore_rule(root: Path = ROOT) -> bool:
    ignore_file = root / ".gitignore"
    if not ignore_file.is_file():
        return False
    rules = {
        line.strip()
        for line in ignore_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    return ".tmp/" in rules


def uv_cache_command(uv: Path, cache_root: Path) -> tuple[str, ...]:
    return (
        str(uv),
        "--offline",
        "--no-config",
        "--no-python-downloads",
        "--cache-dir",
        str(cache_root),
        "cache",
        "dir",
    )


def sanitized_environment(source: Mapping[str, str], cache_root: Path) -> dict[str, str]:
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
    environment = {key: value for key, value in source.items() if key.upper() in allowed}
    environment.update(
        {
            "UV_CACHE_DIR": str(cache_root),
            "UV_NO_CONFIG": "1",
            "UV_OFFLINE": "1",
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )
    return environment


def expected_cache_root(root: Path = ROOT) -> Path:
    return (root.resolve() / TARGET_RELATIVE).resolve(strict=False)


def validate_absent_target(cache_root: Path, root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    resolved_root = root.resolve()
    expected = expected_cache_root(root)
    candidate = cache_root.resolve(strict=False)
    parent = cache_root.parent
    if candidate != expected:
        failures.append("CACHE_PATH")
    if not candidate.is_relative_to(resolved_root):
        failures.append("CACHE_CONFINEMENT")
    if not parent.is_dir() or parent.is_symlink() or parent.resolve() != expected.parent:
        failures.append("CACHE_PARENT")
    if cache_root.exists() or cache_root.is_symlink():
        failures.append("CACHE_NOT_NEW")
    if not target_has_exact_ignore_rule(root):
        failures.append("CACHE_NOT_IGNORED")
    return sorted(set(failures))


def _parse_version(output: str, pattern: str) -> str | None:
    match = re.match(pattern, output.strip())
    return match.group(1) if match else None


def _create_and_probe(cache_root: Path, relative_path: str, payload: str) -> tuple[str, bool]:
    cache_root.mkdir(exist_ok=False)
    if cache_root.is_symlink() or not cache_root.is_dir():
        raise OSError("cache root is not a plain directory")
    probe = cache_root / relative_path
    data = payload.encode("ascii")
    with probe.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    readback_hash = sha256_bytes(probe.read_bytes())
    probe.unlink()
    return readback_hash, not probe.exists()


def run_preflight(
    uv: Path,
    cache_root: Path,
    *,
    root: Path = ROOT,
    source_environment: Mapping[str, str] | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, object]:
    contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    failures = validate_absent_target(cache_root, root)
    expected_probe_hash = sha256_bytes(contract["probe"]["payload"].encode("ascii"))
    created = False
    probe_hash = ""
    probe_removed = False
    version = None
    exit_code = -1
    elapsed_ms = 0.0
    stdout_matches = False
    stderr_present = False

    if not failures:
        try:
            probe_hash, probe_removed = _create_and_probe(
                cache_root, contract["probe"]["relative_path"], contract["probe"]["payload"]
            )
            created = cache_root.is_dir() and not cache_root.is_symlink()
        except OSError:
            failures.append("CALLER_CREATE_OR_WRITE")
        if probe_hash != expected_probe_hash or not probe_removed:
            failures.append("WRITE_PROBE")

    environment = sanitized_environment(source_environment or os.environ, cache_root)
    if not failures:
        try:
            version_process = runner(
                [str(uv), "--version"],
                check=False,
                capture_output=True,
                text=True,
                shell=False,
                env=environment,
            )
            version = _parse_version(
                version_process.stdout, contract["uv"]["version_parse_regex"]
            )
            if version_process.returncode != 0 or version != contract["uv"]["semantic_version"]:
                failures.append("UV_VERSION")
        except (OSError, subprocess.SubprocessError):
            failures.append("UV_VERSION")

    if not failures:
        start = time.perf_counter()
        try:
            process = runner(
                list(uv_cache_command(uv, cache_root)),
                check=False,
                capture_output=True,
                text=True,
                shell=False,
                env=environment,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            exit_code = process.returncode
            stdout_matches = bool(process.stdout.strip()) and Path(
                process.stdout.strip()
            ).resolve(strict=False) == cache_root.resolve(strict=False)
            stderr_present = bool(process.stderr.strip())
        except (OSError, subprocess.SubprocessError):
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            failures.append("UV_EXECUTION")
        if exit_code != 0:
            failures.append("UV_EXIT")
        if not stdout_matches:
            failures.append("UV_STDOUT_PATH")
        if elapsed_ms > float(contract["uv"]["maximum_elapsed_ms"]):
            failures.append("UV_TIME_BUDGET")
        if not cache_root.is_dir() or cache_root.is_symlink():
            failures.append("CACHE_AFTER_UV")

    target_removed = False
    if created and cache_root.exists():
        try:
            cache_root.rmdir()
            target_removed = not cache_root.exists()
        except OSError:
            failures.append("CACHE_NOT_EMPTY_OR_CLEANUP")
    if created and not target_removed:
        failures.append("CACHE_NOT_EMPTY_OR_CLEANUP")

    failures = sorted(set(failures))
    return {
        "schema_version": 1,
        "status": "PASS" if not failures else "STOP",
        "failure_classes": failures,
        "responsibility": {
            "caller_created_directory": created,
            "caller_write_probe_passed": probe_hash == expected_probe_hash and probe_removed,
            "uv_only_confirmed_path": exit_code == 0 and stdout_matches,
        },
        "uv": {
            "version": version,
            "cache_command_exit_code": exit_code,
            "cache_command_elapsed_ms": round(elapsed_ms, 3),
            "stdout_matches_exact_target": stdout_matches,
            "stderr_present": stderr_present,
        },
        "cache": {
            "relative_path": TARGET_RELATIVE.as_posix(),
            "confined_to_repository": cache_root.resolve(strict=False).is_relative_to(root.resolve()),
            "write_probe_sha256": probe_hash,
            "write_probe_removed_before_uv": probe_removed,
            "target_removed_non_recursively": target_removed,
            "target_exists_after_checker": cache_root.exists(),
        },
        "network": {
            "uv_offline_flag_set": True,
            "configuration_discovery_disabled": True,
            "python_downloads_disabled": True,
            "proxy_index_token_or_credential_forwarded": False,
            "os_level_network_instrumented": False,
            "network_attempt_count": None,
        },
        "build_install_or_demo_started": False,
        "cleanup_required": cache_root.exists(),
        "operate_enabled": False,
        "evidence_limit": "one caller-created cache write/path/cleanup preflight only; no package, default-cache root cause, OS-network-attempt, teammate, public-CI, or operation claim",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", required=True, type=Path)
    parser.add_argument("--cache-root", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    receipt = run_preflight(arguments.uv, arguments.cache_root)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
