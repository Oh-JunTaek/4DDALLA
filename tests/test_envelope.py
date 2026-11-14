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
        engine_version="0.1.0",
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
            engine_version="0.1.0",
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
            engine_version="0.1.0",
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
            engine_version="0.1.0",
        )


def _envelope_kwargs() -> dict[str, object]:
    return {
        "run_id": uuid4(),
        "job_id": uuid4(),
        "input_ref": InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=uuid4(), version=1),
        "requested_at": datetime.now(UTC),
        "execution_status": ExecutionStatus.SUCCESS,
        "processed_at": datetime.now(UTC),
        "engine_version": "0.1.0",
    }


def _issue_kwargs() -> dict[str, object]:
    return {
        "event_id": uuid4(),
        "job_id": uuid4(),
        "run_id": uuid4(),
        "module": "test.module",
        "error_code": "TEST_ERROR",
        "severity": ErrorSeverity.MEDIUM,
        "occurred_at": datetime.now(UTC),
        "retryable": False,
        "fingerprint": "fp-1",
        "redacted_context": {"safe": "value"},
    }


def test_envelope_version_defaults_preserved() -> None:
    # schema_version keeps its default "1.0", which is a supported
    # MAJOR.MINOR version; version strings are validated (P1-CONTRACT-02).
    envelope = RunEnvelope(**_envelope_kwargs())
    assert envelope.schema_version == "1.0"
    assert envelope.result_ref is None
    assert envelope.evidence_refs == []
    assert envelope.issues == []


@pytest.mark.parametrize("version", ["0.9", "2.0", "1", "1.0.0", "abc", "", " 1.0"])
def test_envelope_unsupported_or_malformed_schema_version_rejected(version: str) -> None:
    # P1-CONTRACT-02: MAJOR.MINOR format, checked against supported versions.
    kwargs = _envelope_kwargs()
    kwargs["schema_version"] = version
    with pytest.raises(ValidationError):
        RunEnvelope(**kwargs)


def test_envelope_supported_schema_version_accepted() -> None:
    kwargs = _envelope_kwargs()
    kwargs["schema_version"] = "1.0"
    assert RunEnvelope(**kwargs).schema_version == "1.0"


@pytest.mark.parametrize("version", ["0.1", "0.1.0.0", "0.1.0-bootstrap", "rc1", "0.1.0 ", "v0.1.0"])
def test_envelope_malformed_engine_version_rejected(version: str) -> None:
    # P1-CONTRACT-02: MAJOR.MINOR.PATCH format.
    kwargs = _envelope_kwargs()
    kwargs["engine_version"] = version
    with pytest.raises(ValidationError):
        RunEnvelope(**kwargs)


def test_envelope_valid_engine_version_accepted() -> None:
    kwargs = _envelope_kwargs()
    kwargs["engine_version"] = "0.1.0"
    assert RunEnvelope(**kwargs).engine_version == "0.1.0"


def test_envelope_string_uuids_are_coerced() -> None:
    run_id, job_id, object_id = uuid4(), uuid4(), uuid4()
    envelope = RunEnvelope(
        run_id=str(run_id),
        job_id=str(job_id),
        input_ref=InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=str(object_id), version=1),
        requested_at=datetime.now(UTC),
        execution_status=ExecutionStatus.SUCCESS,
        processed_at=datetime.now(UTC),
        engine_version="0.1.0",
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


@pytest.mark.parametrize("bad_version", [1.5, "abc", None, [1], True, 0, -1])
def test_input_ref_version_rejected_values(bad_version: object) -> None:
    # P1-CONTRACT-02: strict int, >= 1 (rejects bool/str/float/0/negative).
    with pytest.raises(ValidationError):
        InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=uuid4(), version=bad_version)  # type: ignore[arg-type]


def test_input_ref_version_accepts_positive_int() -> None:
    assert InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=uuid4(), version=1).version == 1


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


def test_envelope_unknown_fields_forbidden() -> None:
    # P1-CONTRACT-02: official engine input/output contracts reject unknown
    # fields (extra="forbid") instead of silently ignoring them.
    with pytest.raises(ValidationError):
        RunEnvelope.model_validate({**_envelope_kwargs(), "future_field": "x"})
    with pytest.raises(ValidationError):
        RunEnvelope(**_envelope_kwargs(), future_field="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        InputRef(object_type="SOURCE_CONTENT_VERSION", object_id=uuid4(), version=1, extra="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ExecutionIssue(**_issue_kwargs(), unexpected=1)  # type: ignore[call-arg]


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
    kwargs = _issue_kwargs()
    issue = ExecutionIssue(**kwargs)
    assert issue.job_id == kwargs["job_id"]
    assert issue.run_id == kwargs["run_id"]
    assert issue.severity is ErrorSeverity.MEDIUM
    assert issue.redacted_context == {"safe": "value"}


@pytest.mark.parametrize("value", [{"items": [1, "a", True, None, 2.5]}, {"nested": {"k": []}}, {}, {"n": 1.5}])
def test_execution_issue_redacted_context_json_compatible_accepted(value: object) -> None:
    # P1-CONTRACT-02: redacted_context accepts JSON-compatible data only.
    kwargs = _issue_kwargs()
    kwargs["redacted_context"] = value
    assert ExecutionIssue(**kwargs).redacted_context == value  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [{"bad": {1, 2}}, {"bad": float("nan")}, {"bad": float("inf")}, {"bad": datetime(2026, 11, 11)}, {"bad": object()}],
)
def test_execution_issue_redacted_context_non_json_rejected(value: object) -> None:
    kwargs = _issue_kwargs()
    kwargs["redacted_context"] = value
    with pytest.raises(ValidationError):
        ExecutionIssue(**kwargs)  # type: ignore[arg-type]


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
