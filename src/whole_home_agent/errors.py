"""Typed, machine-readable failures for the offline B0 replay core."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class ErrorCode(str, Enum):
    """Stable failure identifiers exposed at the package and CLI boundaries."""

    INVALID_FIXTURE_PATH = "invalid_fixture_path"
    INVALID_JSON = "invalid_json"
    INVALID_SCHEMA = "invalid_schema"
    UNKNOWN_FIELD = "unknown_field"
    MISSING_FIELD = "missing_field"
    INVALID_FIELD_TYPE = "invalid_field_type"
    INVALID_FIELD_VALUE = "invalid_field_value"
    SOURCE_ORDER = "source_order"
    CLAIM_IDENTITY_CONFLICT = "claim_identity_conflict"
    CONTAINMENT_CYCLE = "containment_cycle"
    INVALID_SOURCE = "invalid_source"
    SOURCE_FAILURE = "source_failure"
    INVALID_ARCHIVE = "invalid_archive"
    ARCHIVE_CONFLICT = "archive_conflict"
    ARCHIVE_NOT_FOUND = "archive_not_found"
    UNSUPPORTED_QUESTION = "unsupported_question"
    INVALID_PRESENTER_CONFIG = "invalid_presenter_config"


class B0Error(Exception):
    """Base class for expected fail-closed B0 boundary failures."""

    default_error_code = ErrorCode.INVALID_SCHEMA

    def __init__(
        self,
        message: str,
        *,
        error_code: ErrorCode | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code or self.default_error_code
        self.details = dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable error envelope."""

        result: dict[str, Any] = {
            "error_code": self.error_code.value,
            "message": str(self),
        }
        if self.details:
            result["details"] = self.details
        return result


class FixtureError(B0Error):
    """The fixture could not be admitted into the closed B0 schema."""

    default_error_code = ErrorCode.INVALID_SCHEMA


class ClaimConflictError(B0Error):
    """One claim identity was reused for a different canonical payload."""

    default_error_code = ErrorCode.CLAIM_IDENTITY_CONFLICT


class CycleError(B0Error):
    """A committed containment relation would create a cycle."""

    default_error_code = ErrorCode.CONTAINMENT_CYCLE


class SourceError(B0Error):
    """A bounded candidate source failed or violated its declared contract."""

    default_error_code = ErrorCode.SOURCE_FAILURE


class ArchiveError(B0Error):
    """A durable D0 replay archive failed validation or could not be read."""

    default_error_code = ErrorCode.INVALID_ARCHIVE


class QuestionError(B0Error):
    """A free-text request could not be reduced to one allowlisted location query."""

    default_error_code = ErrorCode.UNSUPPORTED_QUESTION


class PresenterConfigError(B0Error):
    """An optional presenter configuration crossed the local-only boundary."""

    default_error_code = ErrorCode.INVALID_PRESENTER_CONFIG
