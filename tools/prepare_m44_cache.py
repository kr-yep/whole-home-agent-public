"""Copy one frozen local uv-cache subset into the disposable M44 cache target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import time
import tomllib
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "configs" / "evaluation" / "m44-explicit-cache-packaging-v1.toml"
TARGET_RELATIVE = Path(".tmp") / "m44-uv-cache"


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_excluded(relative: str, excluded_prefixes: Sequence[str]) -> bool:
    return any(relative.startswith(prefix) for prefix in excluded_prefixes)


def iter_included_files(root: Path, excluded_prefixes: Sequence[str]) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = _relative(path, root)
        if _is_excluded(relative, excluded_prefixes):
            continue
        if path.is_symlink():
            raise ValueError("cache contains a symlink")
        if path.is_file():
            yield path


def tree_identity(root: Path, excluded_prefixes: Sequence[str]) -> dict[str, object]:
    digest = hashlib.sha256()
    count = 0
    total_bytes = 0
    forbidden_paths: list[str] = []
    allowed_sensitive_suffixes = (
        "/certifi/cacert.pem",
        "/streamlit/runtime/credentials.py",
        "/streamlit/runtime/secrets.py",
    )
    metadata_patterns = (
        re.compile(rb"https?://[^\s/:]+:[^\s/@]+@", re.IGNORECASE),
        re.compile(rb"authorization\s*[:=]", re.IGNORECASE),
        re.compile(rb"bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
        re.compile(rb"api[_-]?key\s*[:=]", re.IGNORECASE),
        re.compile(rb"[A-Z]:\\Users\\[^\\\s]+", re.IGNORECASE),
    )
    metadata_matches: list[str] = []
    for path in iter_included_files(root, excluded_prefixes):
        relative = _relative(path, root)
        data = path.read_bytes()
        file_hash = hashlib.sha256(data).hexdigest()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
        count += 1
        total_bytes += len(data)

        lowered = relative.lower()
        sensitive = (
            PurePosixPath(lowered).name.startswith((".env", "id_rsa", "credentials", "secrets"))
            or PurePosixPath(lowered).suffix in {".pem", ".key", ".p12", ".pfx"}
        )
        if sensitive and not lowered.endswith(allowed_sensitive_suffixes):
            forbidden_paths.append(relative)
        if not relative.startswith("archive-v0/") and len(data) <= 5_242_880:
            metadata_matches.extend(
                f"{relative}#pattern-{index}"
                for index, pattern in enumerate(metadata_patterns, start=1)
                if pattern.search(data)
            )

    reparse_count = sum(
        bool(path.stat(follow_symlinks=False).st_file_attributes & 0x400)
        for path in root.rglob("*")
        if hasattr(path.stat(follow_symlinks=False), "st_file_attributes")
    )
    return {
        "file_count": count,
        "total_bytes": total_bytes,
        "tree_sha256": digest.hexdigest(),
        "reparse_point_count": reparse_count,
        "forbidden_paths": forbidden_paths,
        "metadata_credential_pattern_count": len(metadata_matches),
        "metadata_credential_matches": metadata_matches,
    }


def validate_identity(identity: dict[str, object], expected: dict[str, object]) -> list[str]:
    failures: list[str] = []
    comparisons = {
        "file_count": expected["included_file_count"],
        "total_bytes": expected["included_bytes"],
        "tree_sha256": expected["included_tree_sha256"],
        "reparse_point_count": expected["reparse_point_count"],
        "metadata_credential_pattern_count": expected["metadata_credential_pattern_count"],
    }
    if any(identity.get(key) != value for key, value in comparisons.items()):
        failures.append("CACHE_SOURCE_IDENTITY")
    if identity.get("forbidden_paths"):
        failures.append("CACHE_SOURCE_FORBIDDEN_PATH")
    return failures


def validate_target(target: Path, root: Path = ROOT) -> list[str]:
    expected = (root.resolve() / TARGET_RELATIVE).resolve(strict=False)
    candidate = target.resolve(strict=False)
    failures: list[str] = []
    if candidate != expected or not candidate.is_relative_to(root.resolve()):
        failures.append("CACHE_TARGET_PATH")
    if not target.parent.is_dir() or target.parent.is_symlink():
        failures.append("CACHE_TARGET_PARENT")
    if target.exists() or target.is_symlink():
        failures.append("CACHE_TARGET_NOT_NEW")
    ignore_file = root / ".gitignore"
    if not ignore_file.is_file() or ".tmp/" not in {
        line.strip() for line in ignore_file.read_text(encoding="utf-8").splitlines()
    }:
        failures.append("CACHE_TARGET_NOT_IGNORED")
    return failures


def copy_subset(source: Path, target: Path, excluded_prefixes: Sequence[str]) -> None:
    target.mkdir(exist_ok=False)
    for source_file in iter_included_files(source, excluded_prefixes):
        relative = source_file.relative_to(source)
        target_file = target / relative
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_file, target_file)


def prepare(source: Path, target: Path, root: Path = ROOT) -> dict[str, object]:
    contract = tomllib.loads(CONTRACT.read_text(encoding="utf-8"))
    expected = contract["cache_source"]
    excluded = tuple(expected["excluded_prefixes"])
    failures = validate_target(target, root)
    source_identity: dict[str, object] = {}
    target_identity: dict[str, object] = {}
    elapsed_ms = 0.0
    if not source.is_dir() or source.is_symlink():
        failures.append("CACHE_SOURCE_PATH")
    if not failures:
        try:
            source_identity = tree_identity(source, excluded)
            failures.extend(validate_identity(source_identity, expected))
        except (OSError, ValueError):
            failures.append("CACHE_SOURCE_READ")
    if not failures:
        start = time.perf_counter()
        try:
            copy_subset(source, target, excluded)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            target_identity = tree_identity(target, ())
            failures.extend(validate_identity(target_identity, expected))
        except (OSError, ValueError):
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            failures.append("CACHE_TARGET_COPY")
        if elapsed_ms > float(contract["time_budget_ms"]["cache_seed_maximum"]):
            failures.append("CACHE_SEED_TIME_BUDGET")
    failures = sorted(set(failures))
    return {
        "schema_version": 1,
        "status": "PASS" if not failures else "STOP",
        "failure_classes": failures,
        "source_identity": source_identity,
        "target_identity": target_identity,
        "copy_elapsed_ms": round(elapsed_ms, 3),
        "source_mutated": False,
        "target_relative_path": TARGET_RELATIVE.as_posix(),
        "cleanup_required": target.exists(),
        "operate_enabled": False,
        "evidence_limit": "frozen local cache byte identity and copy only; upstream provenance, package build/install/demo, OS network attempts, teammate/public CI, and operation remain unestablished",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    receipt = prepare(arguments.source, arguments.target)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if receipt["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
