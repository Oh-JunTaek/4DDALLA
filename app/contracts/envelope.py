"""Skeleton of the common execution envelope (ENGINE_SPEC.md §1).

Field names and types follow Docs/ENGINE_SPEC.md §1:
schema_version, run_id, job_id, input_ref{object_type, object_id, version},
requested_at, and outputs execution_status, result_ref, evidence_refs,
issues, processed_at, engine_version. JSON examples in the spec are
illustrative; IDs are UUIDs. This module refines that skeleton for the shared
engine contracts (naive timestamps are rejected; ``issues`` elements have a
structured type). Version strictness/formats, the unknown-field policy and
``redacted_context`` constraints were resolved in P1-CONTRACT-02; engine-specific
payload types and API docs remain future work (§12).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationInfo,
    field_validator,
)

from .enums import ErrorSeverity, ExecutionStatus

#: Schema versions accepted for the common envelope. Expanding the supported
#: set is a contract change (ENGINE_SPEC.md §12).
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0"})

_SCHEMA_VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+")
_ENGINE_VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


class ContractModel(BaseModel):
    """Shared base for contract models: unknown fields are rejected.

    Official engine input/output contracts inherit this so that unexpected or
    misspelled fields fail loudly instead of being silently dropped
    (P1-CONTRACT-02). Engine-specific payload models remain future work (§12).
    """

    model_config = ConfigDict(extra="forbid")


class InputRef(ContractModel):
    object_type: str
    object_id: UUID
    # strict int >= 1: rejects bool/str/float/0/negative values
    # (P1-CONTRACT-02), e.g. input_ref.version.
    version: Annotated[StrictInt, Field(ge=1)]


def _require_timezone_aware(value: datetime, field_name: str) -> datetime:
    """Reject naive datetimes; execution timestamps are timezone-aware (TIMESTAMPTZ semantics)."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class ExecutionIssue(ContractModel):
    """Structured issue attached to an execution result (ENGINE_SPEC.md §1).

    Proposal mapping the error-record fields required by ENGINE_SPEC.md §10
    (``event_id``, ``job_id/run_id``, ``module``, ``error_code``, ``severity``,
    ``occurred_at``, ``retryable``, ``fingerprint``, ``redacted_context``).
    This is a result-level contract only: the physical ``error_events`` storage
    model (DATA_MODEL.md §3) is deliberately out of scope here. ``event_id`` is
    a required UUID (the internal-ID convention of DATA_MODEL.md §2).
    ``job_id`` and ``run_id`` are both required: the spec writes them joined as
    "job_id/run_id" without defining their relation, and P1-CONTRACT-02 requires
    both identifiers on engine execution issues. ``redacted_context`` admits
    JSON-compatible data only; redaction itself stays the responsibility of the
    error-creation stage (§6). Field requiredness otherwise follows the spec's
    "include" list (``ENGINE_SPEC.md`` §10).
    """

    event_id: UUID
    job_id: UUID
    run_id: UUID
    module: str
    error_code: str
    severity: ErrorSeverity
    occurred_at: datetime
    retryable: bool
    fingerprint: str
    redacted_context: dict[str, Any]

    @field_validator("redacted_context")
    @classmethod
    def _redacted_context_must_be_json_compatible(
        cls, value: dict[str, Any], info: ValidationInfo
    ) -> dict[str, Any]:
        """JSON-compatible data only; redaction is the creator's responsibility (P1-CONTRACT-02, §6)."""
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("redacted_context must contain only JSON-compatible data") from exc
        return value

    @field_validator("occurred_at")
    @classmethod
    def _occurred_at_must_be_aware(cls, value: datetime, info: ValidationInfo) -> datetime:
        """Contract timestamps must be timezone-aware (TIMESTAMPTZ semantics)."""
        return _require_timezone_aware(value, info.field_name)


class RunEnvelope(ContractModel):
    """Common execution envelope (ENGINE_SPEC.md §1).

    One envelope binds the input reference (``input_ref``, ``requested_at``) to
    the result fields (``execution_status``, ``result_ref``, ``evidence_refs``,
    ``issues``, ``processed_at``, ``engine_version``); the spec calls for
    engine-specific input/output payloads as separate Pydantic types, which
    remain out of scope here. Timestamps must be timezone-aware.
    ``schema_version`` defaults to "1.0", a supported MAJOR.MINOR version;
    version strings are validated and unknown fields are rejected
    (P1-CONTRACT-02).
    """

    schema_version: str = "1.0"
    run_id: UUID
    job_id: UUID
    input_ref: InputRef
    requested_at: datetime
    execution_status: ExecutionStatus
    result_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    issues: list[ExecutionIssue] = Field(default_factory=list)
    processed_at: datetime
    engine_version: str

    @field_validator("engine_version")
    @classmethod
    def _engine_version_format(cls, value: str) -> str:
        """MAJOR.MINOR.PATCH format (P1-CONTRACT-02)."""
        if _ENGINE_VERSION_PATTERN.fullmatch(value) is None:
            raise ValueError("engine_version must use MAJOR.MINOR.PATCH format")
        return value

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """MAJOR.MINOR format and explicitly supported version (P1-CONTRACT-02)."""
        if _SCHEMA_VERSION_PATTERN.fullmatch(value) is None or value not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"unsupported schema_version {value!r}; supported versions: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
            )
        return value

    @field_validator("requested_at", "processed_at")
    @classmethod
    def _timestamps_must_be_aware(cls, value: datetime, info: ValidationInfo) -> datetime:
        """Contract timestamps must be timezone-aware (TIMESTAMPTZ semantics)."""
        return _require_timezone_aware(value, info.field_name)
