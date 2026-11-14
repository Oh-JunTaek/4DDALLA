"""Skeleton of the common execution envelope (ENGINE_SPEC.md §1).

Field names and types follow Docs/ENGINE_SPEC.md §1:
schema_version, run_id, job_id, input_ref{object_type, object_id, version},
requested_at, and outputs execution_status, result_ref, evidence_refs,
issues, processed_at, engine_version. JSON examples in the spec are
illustrative; IDs are UUIDs. This module refines that skeleton for the shared
engine contracts (naive timestamps are rejected; ``issues`` elements have a
structured type); engine-specific payload types and API docs remain future
work (§12). Points the spec leaves open (strict version-string formats,
unknown-field policy, issue field typing) are flagged as undecided rather than
resolved implicitly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .enums import ErrorSeverity, ExecutionStatus


class InputRef(BaseModel):
    object_type: str
    object_id: UUID
    version: int


def _require_timezone_aware(value: datetime, field_name: str) -> datetime:
    """Reject naive datetimes; execution timestamps are timezone-aware (TIMESTAMPTZ semantics)."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


class ExecutionIssue(BaseModel):
    """Structured issue attached to an execution result (ENGINE_SPEC.md §1).

    Proposal mapping the error-record fields required by ENGINE_SPEC.md §10
    (``event_id``, ``job_id/run_id``, ``module``, ``error_code``, ``severity``,
    ``occurred_at``, ``retryable``, ``fingerprint``, ``redacted_context``).
    This is a result-level contract only: the physical ``error_events`` storage
    model (DATA_MODEL.md §3) is deliberately out of scope here. Proposal-level
    choices that the spec does not fully define: ``event_id`` is a UUID (the
    internal-ID convention of DATA_MODEL.md §2); ``job_id`` and ``run_id`` are
    both optional and unconstrained, because the spec writes them joined as
    "job_id/run_id" without defining their relation; ``redacted_context`` is a
    mapping of safe, already-redacted values; requiredness follows the spec's
    "include" list (``ENGINE_SPEC.md`` §10). These points remain undecided.
    """

    event_id: UUID
    job_id: UUID | None = None
    run_id: UUID | None = None
    module: str
    error_code: str
    severity: ErrorSeverity
    occurred_at: datetime
    retryable: bool
    fingerprint: str
    redacted_context: dict[str, Any]

    @field_validator("occurred_at")
    @classmethod
    def _occurred_at_must_be_aware(cls, value: datetime, info: ValidationInfo) -> datetime:
        """Contract timestamps must be timezone-aware (TIMESTAMPTZ semantics)."""
        return _require_timezone_aware(value, info.field_name)


class RunEnvelope(BaseModel):
    """Common execution envelope (ENGINE_SPEC.md §1).

    One envelope binds the input reference (``input_ref``, ``requested_at``) to
    the result fields (``execution_status``, ``result_ref``, ``evidence_refs``,
    ``issues``, ``processed_at``, ``engine_version``); the spec calls for
    engine-specific input/output payloads as separate Pydantic types, which
    remain out of scope here. Timestamps must be timezone-aware.
    ``schema_version`` keeps its "1.0" default for compatibility; a strict
    syntactic format for the version strings is not defined by the docs and is
    not enforced. Unknown fields keep Pydantic's default (ignore) handling;
    the intended policy is undocumented (flagged as undecided).
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

    @field_validator("requested_at", "processed_at")
    @classmethod
    def _timestamps_must_be_aware(cls, value: datetime, info: ValidationInfo) -> datetime:
        """Contract timestamps must be timezone-aware (TIMESTAMPTZ semantics)."""
        return _require_timezone_aware(value, info.field_name)
