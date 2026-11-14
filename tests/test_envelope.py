from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts.enums import ErrorSeverity, ExecutionStatus
from app.contracts.envelope import ExecutionIssue, InputRef, RunEnvelope


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


def _envelope_kwargs() -> dict[str, object]:
    return {
        "run_id": uuid4(),
        "job_id": uuid4(),
        "input_ref": InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=uuid4(), version=1),
        "requested_at": datetime.now(UTC),
        "execution_status": ExecutionStatus.SUCCESS,
        "processed_at": datetime.now(UTC),
        "engine_version": "0.1.0-bootstrap",
    }


def _issue_kwargs() -> dict[str, object]:
    return {
        "event_id": uuid4(),
        "job_id": None,
        "run_id": None,
        "module": "test.module",
        "error_code": "TEST_ERROR",
        "severity": ErrorSeverity.MEDIUM,
        "occurred_at": datetime.now(UTC),
        "retryable": False,
        "fingerprint": "fp-1",
        "redacted_context": {"safe": "value"},
    }


def test_envelope_version_defaults_preserved() -> None:
    # schema_version keeps its documented default ("1.0"); strict syntactic
    # formats are not defined by ENGINE_SPEC.md and are not enforced here.
    envelope = RunEnvelope(**_envelope_kwargs())
    assert envelope.schema_version == "1.0"
    assert envelope.result_ref is None
    assert envelope.evidence_refs == []
    assert envelope.issues == []


def test_envelope_string_uuids_are_coerced() -> None:
    run_id, job_id, object_id = uuid4(), uuid4(), uuid4()
    envelope = RunEnvelope(
        run_id=str(run_id),
        job_id=str(job_id),
        input_ref=InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=str(object_id), version=1),
        requested_at=datetime.now(UTC),
        execution_status=ExecutionStatus.SUCCESS,
        processed_at=datetime.now(UTC),
        engine_version="0.1.0-bootstrap",
    )
    assert envelope.run_id == run_id
    assert envelope.job_id == job_id
    assert envelope.input_ref.object_id == object_id


@pytest.mark.parametrize(
    "field",
    ["run_id", "job_id", "input_ref", "requested_at", "execution_status", "processed_at", "engine_version"],
)
def test_envelope_each_missing_required_field_rejected(field: str) -> None:
    kwargs = _envelope_kwargs()
    del kwargs[field]
    with pytest.raises(ValidationError):
        RunEnvelope(**kwargs)


@pytest.mark.parametrize("field", ["object_type", "object_id", "version"])
def test_input_ref_missing_required_field_rejected(field: str) -> None:
    kwargs = {"object_type": "SOURCE_CONTENT_VERSION", "object_id": uuid4(), "version": 1}
    del kwargs[field]
    with pytest.raises(ValidationError):
        InputRef(**kwargs)


@pytest.mark.parametrize("target", ["run_id", "job_id", "input_ref.object_id"])
def test_envelope_invalid_uuid_rejected(target: str) -> None:
    kwargs = _envelope_kwargs()
    if target == "run_id":
        kwargs["run_id"] = "not-a-uuid"
    elif target == "job_id":
        kwargs["job_id"] = "not-a-uuid"
    else:
        kwargs["input_ref"] = {
            "object_type": "SOURCE_CONTENT_VERSION",
            "object_id": "not-a-uuid",
            "version": 1,
        }
    with pytest.raises(ValidationError):
        RunEnvelope(**kwargs)


@pytest.mark.parametrize("bad_version", [1.5, "abc", None, [1]])
def test_input_ref_non_integer_version_rejected(bad_version: object) -> None:
    with pytest.raises(ValidationError):
        InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=uuid4(), version=bad_version)  # type: ignore[arg-type]


@pytest.mark.parametrize("field", ["requested_at", "processed_at"])
def test_envelope_naive_datetime_rejected(field: str) -> None:
    kwargs = _envelope_kwargs()
    kwargs[field] = datetime(2026, 11, 11, 11, 0, 0)  # naive: no tzinfo
    with pytest.raises(ValidationError, match="timezone-aware"):
        RunEnvelope(**kwargs)


def test_envelope_aware_datetime_roundtrip_preserves_instant() -> None:
    aware = datetime(2026, 11, 11, 11, 0, 0, tzinfo=timezone(timedelta(hours=9)))
    kwargs = _envelope_kwargs()
    kwargs["requested_at"] = aware
    kwargs["processed_at"] = aware
    envelope = RunEnvelope(**kwargs)
    restored = RunEnvelope.model_validate_json(envelope.model_dump_json())
    assert restored == envelope
    assert restored.requested_at.utcoffset() == timedelta(hours=9)


def test_envelope_default_lists_are_not_shared() -> None:
    first = RunEnvelope(**_envelope_kwargs())
    second = RunEnvelope(**_envelope_kwargs())
    first.evidence_refs.append("ev-1")
    first.issues.append(ExecutionIssue(**_issue_kwargs()))
    assert second.evidence_refs == []
    assert second.issues == []
    assert first.evidence_refs is not second.evidence_refs
    assert first.issues is not second.issues


def test_envelope_unknown_fields_ignored_by_default() -> None:
    # Current (Pydantic default) policy: unknown fields are ignored. The
    # intended policy is not documented in ENGINE_SPEC.md; recorded as
    # undecided rather than changed here.
    envelope = RunEnvelope.model_validate({**_envelope_kwargs(), "future_field": "x"})
    assert "future_field" not in envelope.model_fields_set
    assert "future_field" not in envelope.model_dump()


def test_envelope_json_roundtrip() -> None:
    envelope = RunEnvelope(
        **_envelope_kwargs(),
        result_ref="result-1",
        evidence_refs=["evidence-1"],
        issues=[ExecutionIssue(**_issue_kwargs())],
    )
    restored = RunEnvelope.model_validate_json(envelope.model_dump_json())
    assert restored == envelope
    assert str(envelope.run_id) in envelope.model_dump_json()


def test_execution_issue_valid_construction() -> None:
    issue = ExecutionIssue(**_issue_kwargs())
    assert issue.job_id is None
    assert issue.run_id is None
    assert issue.severity is ErrorSeverity.MEDIUM
    assert issue.redacted_context == {"safe": "value"}


@pytest.mark.parametrize(
    "field",
    ["event_id", "module", "error_code", "severity", "occurred_at", "retryable", "fingerprint", "redacted_context"],
)
def test_execution_issue_missing_required_field_rejected(field: str) -> None:
    kwargs = _issue_kwargs()
    del kwargs[field]
    with pytest.raises(ValidationError):
        ExecutionIssue(**kwargs)


def test_execution_issue_invalid_severity_rejected() -> None:
    kwargs = _issue_kwargs()
    kwargs["severity"] = "LOUD"
    with pytest.raises(ValidationError):
        ExecutionIssue(**kwargs)


@pytest.mark.parametrize("field", ["occurred_at"])
def test_execution_issue_naive_occurred_at_rejected(field: str) -> None:
    kwargs = _issue_kwargs()
    kwargs[field] = datetime(2026, 11, 11, 11, 0, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        ExecutionIssue(**kwargs)
