"""Strict local JSON admission boundary for closed-schema D0 fixtures."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

from .errors import ErrorCode, FixtureError
from .model import (
    ClaimCandidate,
    ClaimOperation,
    EpistemicStatus,
    Predicate,
    ReplayFixture,
    TimestampBasis,
    UseClass,
)


_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "fixture_id",
        "fixture_revision",
        "use_class",
        "timestamp_basis",
        "claims",
    }
)
_CLAIM_FIELDS = frozenset(
    {
        "claim_id",
        "source_sequence",
        "operation",
        "subject_id",
        "predicate",
        "object_id",
        "epistemic_status",
    }
)
_MAX_IDENTIFIER_LENGTH = 256
_MAX_SOURCE_SEQUENCE = (1 << 63) - 1


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FixtureError(
                f"duplicate JSON object key: {key!r}",
                error_code=ErrorCode.INVALID_JSON,
                details={"field": key},
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise FixtureError(
        f"non-finite JSON number is not allowed: {value}",
        error_code=ErrorCode.INVALID_JSON,
        details={"value": value},
    )


def _require_exact_fields(
    value: dict[str, Any], expected: frozenset[str], *, context: str
) -> None:
    actual = set(value)
    extra = sorted(actual - expected)
    missing = sorted(expected - actual)
    if extra:
        raise FixtureError(
            f"{context} contains unknown field(s): {', '.join(extra)}",
            error_code=ErrorCode.UNKNOWN_FIELD,
            details={"context": context, "fields": extra},
        )
    if missing:
        raise FixtureError(
            f"{context} is missing required field(s): {', '.join(missing)}",
            error_code=ErrorCode.MISSING_FIELD,
            details={"context": context, "fields": missing},
        )


def _require_mapping(value: Any, *, context: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise FixtureError(
            f"{context} must be a JSON object",
            error_code=ErrorCode.INVALID_FIELD_TYPE,
            details={"context": context, "expected": "object"},
        )
    return value


def _require_string(value: Any, *, field: str) -> str:
    if type(value) is not str:
        raise FixtureError(
            f"{field} must be a string",
            error_code=ErrorCode.INVALID_FIELD_TYPE,
            details={"field": field, "expected": "string"},
        )
    return value


def _require_identifier(value: Any, *, field: str) -> str:
    identifier = _require_string(value, field=field)
    if (
        not identifier
        or identifier != identifier.strip()
        or len(identifier) > _MAX_IDENTIFIER_LENGTH
        or any(ord(character) < 32 or ord(character) == 127 for character in identifier)
    ):
        raise FixtureError(
            f"{field} must be a non-empty, trimmed identifier",
            error_code=ErrorCode.INVALID_FIELD_VALUE,
            details={"field": field},
        )
    return identifier


def _require_enum(value: Any, enum_type: type[Any], *, field: str) -> Any:
    raw = _require_string(value, field=field)
    try:
        return enum_type(raw)
    except ValueError as error:
        allowed: Iterable[str] = (member.value for member in enum_type)
        raise FixtureError(
            f"unsupported {field}: {raw!r}",
            error_code=ErrorCode.INVALID_FIELD_VALUE,
            details={"field": field, "value": raw, "allowed": sorted(allowed)},
        ) from error


def _parse_operation(value: Any, *, predicate: Predicate, context: str) -> ClaimOperation:
    raw = _require_string(value, field=f"{context}.operation")
    if raw == "take_out":
        if predicate is not Predicate.INSIDE:
            raise FixtureError(
                "take_out is only valid for the inside predicate",
                error_code=ErrorCode.INVALID_FIELD_VALUE,
                details={"field": f"{context}.operation", "predicate": predicate.value},
            )
        return ClaimOperation.RETRACT
    try:
        return ClaimOperation(raw)
    except ValueError as error:
        raise FixtureError(
            f"unsupported {context}.operation: {raw!r}",
            error_code=ErrorCode.INVALID_FIELD_VALUE,
            details={
                "field": f"{context}.operation",
                "value": raw,
                "allowed": ["assert", "retract", "take_out"],
            },
        ) from error


def _parse_claim(value: Any, source_offset: int) -> ClaimCandidate:
    context = f"claims[{source_offset}]"
    record = _require_mapping(value, context=context)
    _require_exact_fields(record, _CLAIM_FIELDS, context=context)

    source_sequence = record["source_sequence"]
    if (
        type(source_sequence) is not int
        or source_sequence < 0
        or source_sequence > _MAX_SOURCE_SEQUENCE
    ):
        raise FixtureError(
            f"{context}.source_sequence must be an integer from 0 to {_MAX_SOURCE_SEQUENCE}",
            error_code=ErrorCode.INVALID_FIELD_VALUE,
            details={"field": f"{context}.source_sequence"},
        )

    predicate = _require_enum(
        record["predicate"], Predicate, field=f"{context}.predicate"
    )
    operation = _parse_operation(
        record["operation"], predicate=predicate, context=context
    )
    return ClaimCandidate(
        claim_id=_require_identifier(record["claim_id"], field=f"{context}.claim_id"),
        source_sequence=source_sequence,
        operation=operation,
        subject_id=_require_identifier(
            record["subject_id"], field=f"{context}.subject_id"
        ),
        predicate=predicate,
        object_id=_require_identifier(
            record["object_id"], field=f"{context}.object_id"
        ),
        epistemic_status=_require_enum(
            record["epistemic_status"],
            EpistemicStatus,
            field=f"{context}.epistemic_status",
        ),
        source_offset=source_offset,
    )


def load_fixture(path: str | os.PathLike[str]) -> ReplayFixture:
    """Load one local UTF-8 JSON fixture through the frozen, closed B0 schema."""

    try:
        path_text = os.fspath(path)
    except TypeError as error:
        raise FixtureError(
            "fixture path must be a local filesystem path",
            error_code=ErrorCode.INVALID_FIXTURE_PATH,
        ) from error
    if not isinstance(path_text, str) or "://" in path_text:
        raise FixtureError(
            "fixture path must be a local filesystem path, not a URL",
            error_code=ErrorCode.INVALID_FIXTURE_PATH,
        )

    try:
        source_path = Path(path_text).resolve(strict=True)
        if not source_path.is_file():
            raise OSError("path is not a regular file")
        raw_bytes = source_path.read_bytes()
    except (OSError, RuntimeError) as error:
        raise FixtureError(
            f"fixture cannot be read: {path_text}",
            error_code=ErrorCode.INVALID_FIXTURE_PATH,
            details={"path": path_text},
        ) from error

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FixtureError(
            "fixture must be UTF-8 without an incompatible byte-order mark",
            error_code=ErrorCode.INVALID_JSON,
            details={"path": str(source_path)},
        ) from error

    try:
        document = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except FixtureError:
        raise
    except json.JSONDecodeError as error:
        raise FixtureError(
            f"fixture is not valid JSON: line {error.lineno}, column {error.colno}",
            error_code=ErrorCode.INVALID_JSON,
            details={"line": error.lineno, "column": error.colno},
        ) from error

    root = _require_mapping(document, context="fixture")
    _require_exact_fields(root, _TOP_LEVEL_FIELDS, context="fixture")
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise FixtureError(
            "schema_version must be integer 1",
            error_code=ErrorCode.INVALID_FIELD_VALUE,
            details={"field": "schema_version", "supported": [1]},
        )
    claims_value = root["claims"]
    if type(claims_value) is not list:
        raise FixtureError(
            "claims must be a JSON array",
            error_code=ErrorCode.INVALID_FIELD_TYPE,
            details={"field": "claims", "expected": "array"},
        )

    claims = tuple(_parse_claim(value, index) for index, value in enumerate(claims_value))
    return ReplayFixture(
        schema_version=1,
        fixture_id=_require_identifier(root["fixture_id"], field="fixture_id"),
        fixture_revision=_require_identifier(
            root["fixture_revision"], field="fixture_revision"
        ),
        use_class=_require_enum(root["use_class"], UseClass, field="use_class"),
        timestamp_basis=_require_enum(
            root["timestamp_basis"], TimestampBasis, field="timestamp_basis"
        ),
        claims=claims,
        source_path=source_path,
        content_hash=hashlib.sha256(raw_bytes).hexdigest(),
    )
