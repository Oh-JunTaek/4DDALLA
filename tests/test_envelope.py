from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts.enums import ExecutionStatus
from app.contracts.envelope import InputRef, RunEnvelope


def make_envelope() -> RunEnvelope:
    now = datetime.now(UTC)
    return RunEnvelope(
        run_id=uuid4(),
        job_id=uuid4(),
        input_ref=InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=uuid4(), version=1),
        requested_at=now,
        execution_status=ExecutionStatus.SUCCESS,
        processed_at=now,
        engine_version="0.1.0-bootstrap",
    )


def test_envelope_minimal_valid() -> None:
    envelope = make_envelope()
    assert envelope.schema_version == "1.0"
    assert envelope.result_ref is None
    assert envelope.evidence_refs == []
    assert envelope.issues == []


def test_envelope_missing_required_field_rejected() -> None:
    with pytest.raises(ValidationError):
        RunEnvelope(
            run_id=uuid4(),
            job_id=uuid4(),
            # input_ref intentionally omitted
            requested_at=datetime.now(UTC),
            execution_status=ExecutionStatus.SUCCESS,
            processed_at=datetime.now(UTC),
            engine_version="0.1.0-bootstrap",
        )


def test_envelope_non_uuid_rejected() -> None:
    with pytest.raises(ValidationError):
        RunEnvelope(
            run_id="not-a-uuid",
            job_id=uuid4(),
            input_ref=InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=uuid4(), version=1),
            requested_at=datetime.now(UTC),
            execution_status=ExecutionStatus.SUCCESS,
            processed_at=datetime.now(UTC),
            engine_version="0.1.0-bootstrap",
        )


def test_envelope_bad_execution_status_rejected() -> None:
    with pytest.raises(ValidationError):
        RunEnvelope(
            run_id=uuid4(),
            job_id=uuid4(),
            input_ref=InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=uuid4(), version=1),
            requested_at=datetime.now(UTC),
            execution_status="SOME_UNKNOWN_STATE",
            processed_at=datetime.now(UTC),
            engine_version="0.1.0-bootstrap",
        )
