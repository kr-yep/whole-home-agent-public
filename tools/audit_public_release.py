"""Fail-closed audit for files proposed for the public repository.

The default ``git`` scan audits both the index and the current working-tree
versions of every tracked path.  ``--scan root`` instead audits every file
under the selected root except Git's own metadata.  The audit uses only the
Python standard library and never prints matched secret or PII values.

Generated media is an intentionally narrow exception.  It must live below
``examples/media/generated`` and have either a sidecar manifest or a directory
index manifest.  A record has this minimum shape::

    {
      "path": "clip.mp4",
      "sha256": "<64 lowercase hexadecimal characters>",
      "license": "CC0-1.0",
      "use_class": "D0_SYNTHETIC",
      "provenance": {"kind": "project_generated_synthetic"}
    }

An index uses ``{"media": [<record>, ...]}``.  ``license``, ``use_class``,
and ``provenance`` may be inherited from the index's top level.  Passing this
audit establishes only that these mechanical release checks passed; it does
not establish consent, factual provenance, or a right to publish.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence


AUDIT_SCHEMA_VERSION = 1
AUDIT_VERSION = "public-release-audit/1"
DEFAULT_MAX_FILE_BYTES = 5 * 1024 * 1024
GENERATED_MEDIA_ROOT = PurePosixPath("examples/media/generated")

MEDIA_SUFFIXES = {
    ".avi",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".png",
    ".tif",
    ".tiff",
    ".wav",
    ".webm",
    ".webp",
}

FORBIDDEN_FILE_ENDINGS = (
    ".7z",
    ".bak",
    ".bz2",
    ".ckpt",
    ".db",
    ".db-shm",
    ".db-wal",
    ".engine",
    ".ggml",
    ".gguf",
    ".gz",
    ".joblib",
    ".keras",
    ".key",
    ".log",
    ".npy",
    ".npz",
    ".onnx",
    ".p12",
    ".pem",
    ".pfx",
    ".pickle",
    ".pkl",
    ".h5",
    ".pth",
    ".pt",
    ".rar",
    ".safetensors",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
    ".tflite",
    ".tgz",
    ".whl",
    ".xz",
    ".zip",
    ".zst",
)

SENSITIVE_EXACT_NAMES = {
    ".env",
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "id_dsa",
    "id_ed25519",
    "id_ecdsa",
    "id_rsa",
    "secrets.json",
    "service-account.json",
}
SENSITIVE_PATH_PART = re.compile(
    r"(?:^|[._-])(?:api-key|api_key|apikey|auth-token|client-secret|credential|"
    r"credentials|password|passwords|private-key|private_key|secret|secrets|"
    r"service-account|token|tokens)(?:$|[._-])",
    re.IGNORECASE,
)
SENSITIVE_DIRECTORY_NAMES = {".aws", ".gnupg", ".kube", ".ssh"}

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}(?![\w.-])",
    re.IGNORECASE,
)
WINDOWS_HOME_PATTERN = re.compile(r"\b[A-Z]:[\\/]Users[\\/][^\\/\s]+", re.I)
POSIX_HOME_PATTERN = re.compile(r"/(?:home|Users)/[^/\s]+")
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
AWS_ACCESS_KEY_PATTERN = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
GITHUB_TOKEN_PATTERN = re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")
OPENAI_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")
GOOGLE_API_KEY_PATTERN = re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b")
SLACK_TOKEN_PATTERN = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")
STRIPE_LIVE_KEY_PATTERN = re.compile(r"\b[rs]k_live_[A-Za-z0-9]{16,}\b")
URI_CREDENTIAL_PATTERN = re.compile(
    r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@[^\s]+", re.IGNORECASE
)
ASSIGNED_SECRET_PATTERN = re.compile(
    r"(?im)^\s*[\"']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|"
    r"aws[_-]?secret[_-]?access[_-]?key|client[_-]?secret|password|passwd|"
    r"private[_-]?key)[\"']?\s*[:=]\s*[\"']?"
    r"([^\s\"'#;,}]{8,})"
)
TAIWAN_ID_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z][12][0-9]{8}(?![A-Z0-9])", re.I)
TAIWAN_MOBILE_PATTERN = re.compile(r"(?<![0-9])09[0-9]{2}[- ]?[0-9]{3}[- ]?[0-9]{3}(?![0-9])")
PLACEHOLDER_VALUES = {
    "changeme",
    "dummy",
    "example",
    "placeholder",
    "redacted",
    "replace-me",
    "replace_me",
    "test-only",
    "test_only",
}


@dataclass(frozen=True)
class FileRecord:
    """One file payload in a named release snapshot."""

    path: PurePosixPath
    data: bytes
    snapshot: str
    is_symlink: bool = False


@dataclass(frozen=True)
class Violation:
    """A non-sensitive description of one failed release rule."""

    rule_id: str
    path: str
    snapshot: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "path": self.path,
            "snapshot": self.snapshot,
            "message": self.message,
        }


class AuditError(RuntimeError):
    """Raised when the audit itself cannot establish a complete result."""


def _normalize_relative_path(raw_path: str) -> PurePosixPath:
    normalized = raw_path.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise AuditError("encountered a path outside the selected release root")
    return path


def _run_git(root: Path, arguments: Sequence[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise AuditError("git is unavailable") from exc
    if completed.returncode != 0:
        raise AuditError("git could not enumerate the release snapshot")
    return completed.stdout


def collect_git_snapshots(root: Path) -> dict[str, list[FileRecord]]:
    """Collect complete staged-index and tracked-working-tree snapshots."""

    root = root.resolve()
    raw_entries = _run_git(root, ["ls-files", "--stage", "-z"])
    entries: list[tuple[PurePosixPath, bool]] = []
    for item in raw_entries.split(b"\0"):
        if not item:
            continue
        try:
            metadata, raw_path = item.split(b"\t", 1)
            mode, _object_id, stage = metadata.decode("ascii").split(" ")
            path = _normalize_relative_path(raw_path.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise AuditError("git returned an unsupported index entry") from exc
        if stage != "0":
            raise AuditError("git index contains an unresolved merge entry")
        entries.append((path, mode == "120000"))

    index: list[FileRecord] = []
    working_tree: list[FileRecord] = []

    for path, index_is_symlink in sorted(entries, key=lambda item: str(item[0])):
        git_path = path.as_posix()
        index_data = _run_git(root, ["show", f":{git_path}"])
        index.append(
            FileRecord(
                path=path,
                data=index_data,
                snapshot="index",
                is_symlink=index_is_symlink,
            )
        )

        disk_path = root.joinpath(*path.parts)
        if not disk_path.exists() and not disk_path.is_symlink():
            continue
        if disk_path.is_symlink():
            working_tree.append(
                FileRecord(
                    path=path,
                    data=os.readlink(disk_path).encode("utf-8", errors="surrogateescape"),
                    snapshot="working_tree",
                    is_symlink=True,
                )
            )
            continue
        if not disk_path.is_file():
            working_tree.append(
                FileRecord(path=path, data=b"", snapshot="working_tree", is_symlink=True)
            )
            continue
        working_tree.append(
            FileRecord(
                path=path,
                data=disk_path.read_bytes(),
                snapshot="working_tree",
            )
        )

    return {"index": index, "working_tree": working_tree}


def collect_root_snapshot(root: Path) -> dict[str, list[FileRecord]]:
    """Collect all files below root, excluding only the repository's .git data."""

    root = root.resolve()
    if not root.is_dir():
        raise AuditError("selected release root is not a directory")
    records: list[FileRecord] = []
    for directory, names, filenames in os.walk(root, topdown=True, followlinks=False):
        directory_path = Path(directory)
        traversable_names: list[str] = []
        for name in sorted(name for name in names if name != ".git"):
            disk_path = directory_path / name
            if disk_path.is_symlink():
                relative = _normalize_relative_path(disk_path.relative_to(root).as_posix())
                records.append(
                    FileRecord(
                        path=relative,
                        data=os.readlink(disk_path).encode("utf-8", errors="surrogateescape"),
                        snapshot="root",
                        is_symlink=True,
                    )
                )
            else:
                traversable_names.append(name)
        names[:] = traversable_names
        for name in sorted(filenames):
            disk_path = directory_path / name
            relative = _normalize_relative_path(disk_path.relative_to(root).as_posix())
            if disk_path.is_symlink():
                records.append(
                    FileRecord(
                        path=relative,
                        data=os.readlink(disk_path).encode("utf-8", errors="surrogateescape"),
                        snapshot="root",
                        is_symlink=True,
                    )
                )
            elif disk_path.is_file():
                records.append(
                    FileRecord(path=relative, data=disk_path.read_bytes(), snapshot="root")
                )
    return {"root": records}


def _is_sensitive_path(path: PurePosixPath) -> bool:
    lowered_parts = tuple(part.casefold() for part in path.parts)
    name = lowered_parts[-1]
    if name in SENSITIVE_EXACT_NAMES:
        return True
    if name.startswith(".env.") and name not in {".env.example", ".env.template"}:
        return True
    if any(part in SENSITIVE_DIRECTORY_NAMES for part in lowered_parts[:-1]):
        return True
    return any(SENSITIVE_PATH_PART.search(part) for part in lowered_parts)


def _has_forbidden_ending(path: PurePosixPath) -> bool:
    lowered = path.name.casefold()
    return any(lowered.endswith(ending) for ending in FORBIDDEN_FILE_ENDINGS)


def _is_media(path: PurePosixPath) -> bool:
    return path.suffix.casefold() in MEDIA_SUFFIXES


def _inside_generated_media(path: PurePosixPath) -> bool:
    return path == GENERATED_MEDIA_ROOT or GENERATED_MEDIA_ROOT in path.parents


def _decode_text(data: bytes) -> str | None:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def _content_rule_ids(text: str) -> set[str]:
    violations: set[str] = set()
    if EMAIL_PATTERN.search(text):
        violations.add("email_or_pii")
    if TAIWAN_ID_PATTERN.search(text) or TAIWAN_MOBILE_PATTERN.search(text):
        violations.add("email_or_pii")
    if WINDOWS_HOME_PATTERN.search(text) or POSIX_HOME_PATTERN.search(text):
        violations.add("local_absolute_path")
    if PRIVATE_KEY_PATTERN.search(text):
        violations.add("private_key_material")
    if AWS_ACCESS_KEY_PATTERN.search(text):
        violations.add("credential_content")
    if (
        GITHUB_TOKEN_PATTERN.search(text)
        or GOOGLE_API_KEY_PATTERN.search(text)
        or OPENAI_KEY_PATTERN.search(text)
        or SLACK_TOKEN_PATTERN.search(text)
        or STRIPE_LIVE_KEY_PATTERN.search(text)
    ):
        violations.add("credential_content")
    if URI_CREDENTIAL_PATTERN.search(text):
        violations.add("credential_content")
    for match in ASSIGNED_SECRET_PATTERN.finditer(text):
        if match.group(1).casefold() not in PLACEHOLDER_VALUES:
            violations.add("credential_content")
            break
    return violations


def _strict_json(data: bytes) -> object | None:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate manifest key")
            result[key] = value
        return result

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None


def _manifest_candidates(media_path: PurePosixPath) -> tuple[PurePosixPath, ...]:
    parent = media_path.parent
    stem_sidecar = parent / f"{media_path.stem}.manifest.json"
    full_sidecar = parent / f"{media_path.name}.manifest.json"
    candidates = [full_sidecar, stem_sidecar, parent / "media_manifest.json", parent / "manifest.json"]
    return tuple(dict.fromkeys(candidates))


def _manifest_records(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("media"), list):
        defaults = {
            key: payload[key]
            for key in ("license", "use_class", "provenance")
            if key in payload
        }
        records: list[dict[str, object]] = []
        for item in payload["media"]:
            if isinstance(item, dict):
                merged = dict(defaults)
                merged.update(item)
                records.append(merged)
        return records
    return [payload]


def _record_target_path(record: Mapping[str, object], manifest_path: PurePosixPath) -> PurePosixPath | None:
    raw_path = record.get("path")
    if not isinstance(raw_path, str):
        return None
    try:
        normalized = _normalize_relative_path(raw_path)
    except AuditError:
        return None
    if normalized.parts and normalized.parts[0] == "examples":
        return normalized
    combined = manifest_path.parent / normalized
    if ".." in combined.parts:
        return None
    return combined


def _is_project_generated_synthetic(value: object) -> bool:
    if isinstance(value, dict):
        value = value.get("kind", value.get("type", value.get("origin")))
    if not isinstance(value, str):
        return False
    normalized = value.casefold().replace("-", "_").replace(" ", "_")
    return normalized == "project_generated_synthetic"


def _valid_license(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    return value.strip().casefold() not in {"none", "tbd", "unknown", "unreviewed"}


def _media_has_valid_manifest(media: FileRecord, files: Mapping[PurePosixPath, FileRecord]) -> bool:
    expected_hash = hashlib.sha256(media.data).hexdigest()
    candidates = list(_manifest_candidates(media.path))
    candidates.extend(
        path
        for path in files
        if path.parent == media.path.parent and re.fullmatch(r"manifest_v\d+\.json", path.name, re.I)
    )
    for manifest_path in dict.fromkeys(candidates):
        manifest = files.get(manifest_path)
        if manifest is None:
            continue
        payload = _strict_json(manifest.data)
        for record in _manifest_records(payload):
            if _record_target_path(record, manifest_path) != media.path:
                continue
            if record.get("sha256") != expected_hash:
                continue
            if not _valid_license(record.get("license")):
                continue
            if record.get("use_class") != "D0_SYNTHETIC":
                continue
            if not _is_project_generated_synthetic(record.get("provenance")):
                continue
            return True
    return False


def _audit_snapshot(records: Iterable[FileRecord], max_file_bytes: int) -> list[Violation]:
    records = list(records)
    by_path = {record.path: record for record in records}
    violations: list[Violation] = []
    messages = {
        "credential_content": "file contains a high-confidence credential pattern",
        "email_or_pii": "file contains an email address or high-confidence PII pattern",
        "local_absolute_path": "file contains a user-home absolute path",
        "private_key_material": "file contains private key material",
    }

    for record in records:
        path_text = record.path.as_posix()
        if record.is_symlink:
            violations.append(Violation("symlink", path_text, record.snapshot, "symbolic links are not allowed in the public release"))
            continue
        if _is_sensitive_path(record.path):
            violations.append(Violation("sensitive_path", path_text, record.snapshot, "path name indicates credentials, tokens, passwords, or secrets"))
        if _has_forbidden_ending(record.path):
            violations.append(Violation("forbidden_artifact", path_text, record.snapshot, "database, log, model, credential, backup, or archive artifact is not allowed"))
        if len(record.data) > max_file_bytes:
            violations.append(Violation("file_too_large", path_text, record.snapshot, f"file exceeds the {max_file_bytes}-byte public limit"))

        if _is_media(record.path):
            if not _inside_generated_media(record.path):
                violations.append(Violation("media_not_allowlisted", path_text, record.snapshot, "media is allowed only below examples/media/generated"))
            elif not _media_has_valid_manifest(record, by_path):
                violations.append(Violation("media_manifest_invalid", path_text, record.snapshot, "generated media lacks a matching hash, license, D0 use class, and project-synthetic provenance"))
            continue

        text = _decode_text(record.data)
        if text is None:
            continue
        for rule_id in sorted(_content_rule_ids(text)):
            violations.append(Violation(rule_id, path_text, record.snapshot, messages[rule_id]))

    return violations


def audit_repository(
    root: Path,
    *,
    scan_mode: str = "git",
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> dict[str, object]:
    """Audit a repository and return a deterministic JSON-serializable receipt."""

    if max_file_bytes < 1:
        raise AuditError("maximum file size must be positive")
    root = root.resolve()
    if scan_mode == "git":
        snapshots = collect_git_snapshots(root)
    elif scan_mode == "root":
        snapshots = collect_root_snapshot(root)
    else:
        raise AuditError("scan mode must be 'git' or 'root'")

    violations: list[Violation] = []
    for records in snapshots.values():
        violations.extend(_audit_snapshot(records, max_file_bytes))
    violations.sort(key=lambda item: (item.path, item.rule_id, item.snapshot, item.message))
    scanned_paths = {record.path.as_posix() for records in snapshots.values() for record in records}
    scanned_instances = sum(len(records) for records in snapshots.values())
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "audit_version": AUDIT_VERSION,
        "status": "PASS" if not violations else "FAIL",
        "scan_mode": scan_mode,
        "operate_enabled": False,
        "max_file_bytes": max_file_bytes,
        "scanned_file_count": len(scanned_paths),
        "scanned_snapshot_count": scanned_instances,
        "violation_count": len(violations),
        "violations": [violation.as_dict() for violation in violations],
        "evidence_limit": "mechanical file audit only; not publication authority, consent, provenance truth, or secret-scanner completeness",
    }


def _error_receipt(scan_mode: str, message: str) -> dict[str, object]:
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "audit_version": AUDIT_VERSION,
        "status": "ERROR",
        "scan_mode": scan_mode,
        "operate_enabled": False,
        "violation_count": 0,
        "violations": [],
        "error": message,
        "evidence_limit": "audit did not complete",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository or directory to audit (default: repository containing this tool)",
    )
    parser.add_argument(
        "--scan",
        choices=("git", "root"),
        default="git",
        help="scan tracked/index versions or every file below root",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=DEFAULT_MAX_FILE_BYTES,
        help="reject files larger than this many bytes",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = audit_repository(
            args.root,
            scan_mode=args.scan,
            max_file_bytes=args.max_file_bytes,
        )
    except AuditError as exc:
        receipt = _error_receipt(args.scan, str(exc))
        exit_code = 2
    except OSError:
        receipt = _error_receipt(args.scan, "audit failed due to a filesystem error")
        exit_code = 2
    else:
        exit_code = 0 if receipt["status"] == "PASS" else 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
