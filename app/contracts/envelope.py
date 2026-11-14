"""Skeleton of the common execution envelope (ENGINE_SPEC.md §1).

Field names and types follow Docs/ENGINE_SPEC.md §1:
schema_version, run_id, job_id, input_ref{object_type, object_id, version},
requested_at, and outputs execution_status, result_ref, evidence_refs,
issues, processed_at, engine_version. JSON examples in the spec are
illustrative; IDs are UUIDs. This skeleton is refined in the first
implementation ticket together with tests and API docs (§12).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from .enums import ExecutionStatus


class InputRef(BaseModel):
    object_type: str
    object_id: UUID
    version: int


class RunEnvelope(BaseModel):
    schema_version: str = "1.0"
    run_id: UUID
    job_id: UUID
    input_ref: InputRef
    requested_at: datetime
    execution_status: ExecutionStatus
    result_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    issues: list[Any] = Field(default_factory=list)
    processed_at: datetime
    engine_version: str
