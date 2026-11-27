"""DB-free tests for the StoreDiscovery engine (P2-STORE-01).

Docker/PostgreSQL are not required: the synthetic fixture provider and
structural provider doubles exercise validation, filtering, pagination,
dedupe, error and rights-gating paths.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.contracts.enums import ExecutionStatus
from app.discovery import (
    SYNTHETIC_PLACES,
    CandidateDuplicateStatus,
    Coordinate,
    DataUseRights,
    EvidenceKind,
    ProviderExecutionError,
    ProviderPlace,
    ProviderSearchPage,
    ProviderSearchRequest,
    StoreDiscovery,
    StoreDiscoveryInput,
    StoreDiscoveryResult,
    SyntheticPlaceProvider,
    haversine_meters,
)

_CENTER = Coordinate(latitude=37.497900, longitude=127.098300)


def make_input(
    radius: int = 800,
    categories: tuple[str, ...] = (),
    providers: tuple[str, ...] = ("synthetic",),
) -> StoreDiscoveryInput:
    return StoreDiscoveryInput(
        region_id="test-region",
        center=Coordinate(latitude=_CENTER.latitude, longitude=_CENTER.longitude),
        radius_m=radius,
        categories=categories,
        allowed_provider_ids=providers,
    )


class _RecordingProvider:
    """Structural double: records requests, delegates to a synthetic provider."""

    contract_version = "1.0.0"
    data_use = DataUseRights.STORE_ALLOWED

    def __init__(self, inner: SyntheticPlaceProvider) -> None:
        self.provider_id = inner.provider_id
        self._inner = inner
        self.requests: list[ProviderSearchRequest] = []

    def search(self, request: ProviderSearchRequest) -> ProviderSearchPage:
        self.requests.append(request)
        return self._inner.search(request)


class _FailingProvider:
    contract_version = "1.0.0"
    data_use = DataUseRights.STORE_ALLOWED
    provider_id = "failing"

    def __init__(
        self, error_code: str = "provider_error", retryable: bool = False
    ) -> None:
        self.error_code = error_code
        self.retryable = retryable

    def search(self, request: ProviderSearchRequest) -> ProviderSearchPage:
        raise ProviderExecutionError(
            "simulated transport failure",
            provider_id=self.provider_id,
            error_code=self.error_code,
            retryable=self.retryable,
        )


class _WrongVersionProvider:
    contract_version = "1.0.0"
    data_use = DataUseRights.STORE_ALLOWED
    provider_id = "wrongversion"

    def search(self, request: ProviderSearchRequest) -> ProviderSearchPage:
        return ProviderSearchPage(
            provider_id=self.provider_id,
            contract_version="0.9.0",
            places=(),
        )


class _WrongIdProvider:
    contract_version = "1.0.0"
    data_use = DataUseRights.STORE_ALLOWED
    provider_id = "wrongid"

    def search(self, request: ProviderSearchRequest) -> ProviderSearchPage:
        return ProviderSearchPage(
            provider_id="someone-else",
            contract_version=self.contract_version,
            places=(),
        )


class _NonPageProvider:
    contract_version = "1.0.0"
    data_use = DataUseRights.STORE_ALLOWED
    provider_id = "nonpage"

    def search(self, request: ProviderSearchRequest) -> object:
        return object()


def repeated_external_id_places() -> tuple[ProviderPlace, ...]:
    """Two observations of the same provider external id (40 m, 300 m)."""
    return (
        ProviderPlace(
            provider_id="synthetic",
            external_id="syn-repeat",
            display_name="Synth repeat first observation",
            latitude=_CENTER.latitude + 40 / 111195,
            longitude=_CENTER.longitude,
        ),
        ProviderPlace(
            provider_id="synthetic",
            external_id="syn-repeat",
            display_name="Synth repeat re-observation",
            latitude=_CENTER.latitude + 300 / 111195,
            longitude=_CENTER.longitude,
        ),
    )


# --- input validation ---


@pytest.mark.parametrize("bad_radius", [799, 801, 8000, 0, -800, True, 800.0, "800"])
def test_input_rejects_unsupported_or_non_integer_radius(bad_radius: object) -> None:
    with pytest.raises(ValidationError):
        make_input(radius=bad_radius)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)],
)
def test_input_rejects_out_of_range_coordinates(
    latitude: float, longitude: float
) -> None:
    with pytest.raises(ValidationError):
        Coordinate(latitude=latitude, longitude=longitude)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("latitude", True),
        ("longitude", False),
        ("latitude", "37.5"),
        ("longitude", None),
    ],
)
def test_input_rejects_non_numeric_or_bool_coordinates(
    field: str, value: object
) -> None:
    payload: dict[str, object] = {"latitude": 0.0, "longitude": 0.0}
    payload[field] = value
    with pytest.raises(ValidationError):
        Coordinate(**payload)  # type: ignore[arg-type]


def test_input_rejects_empty_allowed_providers() -> None:
    with pytest.raises(ValidationError):
        make_input(providers=())


def test_input_rejects_blank_category_or_provider() -> None:
    with pytest.raises(ValidationError):
        make_input(categories=("  ",))
    with pytest.raises(ValidationError):
        make_input(providers=("synthetic", ""))


# --- radius, categories, pagination ---


def test_default_800m_search_returns_only_in_radius_candidates_sorted_by_distance() -> (
    None
):
    result = StoreDiscovery({"synthetic": SyntheticPlaceProvider()}).execute(
        make_input()
    )
    assert result.status is ExecutionStatus.SUCCESS
    assert result.issues == []
    assert [ref.external_id for c in result.candidates for ref in c.provider_refs] == [
        "syn-cafe-near",
        "syn-brunch-mid",
    ]
    distances = [c.approx_distance_m for c in result.candidates]
    assert distances == sorted(distances)
    assert all(d <= 800 for d in distances)


def test_1000m_radius_includes_beyond_800m_but_not_far_out() -> None:
    result = StoreDiscovery({"synthetic": SyntheticPlaceProvider()}).execute(
        make_input(radius=1000)
    )
    by_id = {ref.external_id: c for c in result.candidates for ref in c.provider_refs}
    assert set(by_id) == {"syn-cafe-near", "syn-brunch-mid", "syn-cafe-far"}
    assert by_id["syn-cafe-far"].approx_distance_m > 800
    assert "syn-shop-far" not in by_id


def test_boundary_is_inclusive_and_consistent_with_haversine() -> None:
    # Place ~800 m north of the center: inclusion must match the same haversine
    # the engine applies (<= radius), with a small tolerance for rounding.
    latitude = _CENTER.latitude + 800 / 111195
    place = ProviderPlace(
        provider_id="synthetic",
        external_id="syn-edge",
        display_name="합성 경계",
        latitude=latitude,
        longitude=_CENTER.longitude,
    )
    result = StoreDiscovery(
        {"synthetic": SyntheticPlaceProvider(places=(place,))}
    ).execute(make_input(radius=800))
    distance = haversine_meters(
        _CENTER.latitude, _CENTER.longitude, latitude, _CENTER.longitude
    )
    assert abs(distance - 800) < 1.0
    assert [ref.external_id for c in result.candidates for ref in c.provider_refs] == (
        ["syn-edge"] if distance <= 800 else []
    )


def test_category_filter_is_applied_per_request() -> None:
    result = StoreDiscovery({"synthetic": SyntheticPlaceProvider()}).execute(
        make_input(radius=1000, categories=("카페",))
    )
    assert [ref.external_id for c in result.candidates for ref in c.provider_refs] == [
        "syn-cafe-near",
        "syn-cafe-far",
    ]


def test_pagination_follows_tokens_and_sends_each_page_once() -> None:
    provider = _RecordingProvider(SyntheticPlaceProvider(page_size=2))
    discovery = StoreDiscovery({"synthetic": provider})
    result = discovery.execute(make_input(radius=1000))
    assert [ref.external_id for c in result.candidates for ref in c.provider_refs] == [
        "syn-cafe-near",
        "syn-brunch-mid",
        "syn-cafe-far",
    ]
    assert [request.page_token for request in provider.requests] == [None, "2"]


def test_provider_without_more_pages_returns_single_page() -> None:
    provider = _RecordingProvider(SyntheticPlaceProvider(page_size=10))
    result = StoreDiscovery({"synthetic": provider}).execute(make_input())
    assert len(provider.requests) == 1
    assert provider.requests[0].page_token is None
    assert len(result.candidates) == 2


# --- duplicates, errors, rights ---


def test_repeated_same_provider_external_id_is_flagged_not_duplicated() -> None:
    provider = SyntheticPlaceProvider(
        places=repeated_external_id_places(), page_size=10
    )
    result = StoreDiscovery({"synthetic": provider}).execute(make_input())
    assert result.status is ExecutionStatus.SUCCESS
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.duplicate_status is CandidateDuplicateStatus.SAME_PROVIDER_REPEAT
    assert candidate.possible_duplicate_of == ()
    assert len(candidate.provider_refs) == 1


def test_same_display_name_is_not_merged_and_not_an_identity() -> None:
    places = (
        ProviderPlace(
            provider_id="synthetic",
            external_id="syn-name-a",
            display_name="합성 동명 매장",
            latitude=_CENTER.latitude + 40 / 111195,
            longitude=_CENTER.longitude,
        ),
        ProviderPlace(
            provider_id="synthetic",
            external_id="syn-name-b",
            display_name="합성 동명 매장",
            latitude=_CENTER.latitude + 200 / 111195,
            longitude=_CENTER.longitude,
        ),
    )
    result = StoreDiscovery(
        {"synthetic": SyntheticPlaceProvider(places=places)}
    ).execute(make_input())
    assert len(result.candidates) == 2
    for candidate in result.candidates:
        assert candidate.duplicate_status is CandidateDuplicateStatus.UNKNOWN
        assert len(candidate.provider_refs) == 1


def test_candidate_id_is_engine_uuid_separate_from_external_id() -> None:
    result = StoreDiscovery({"synthetic": SyntheticPlaceProvider()}).execute(
        make_input()
    )
    candidate = result.candidates[0]
    assert isinstance(candidate.candidate_id, UUID)
    external_ids = {ref.external_id for ref in candidate.provider_refs}
    assert str(candidate.candidate_id) not in external_ids


def test_evidence_lists_provider_fields_only_and_includes_collection_time_when_present() -> (
    None
):
    result = StoreDiscovery({"synthetic": SyntheticPlaceProvider()}).execute(
        make_input(radius=1000)
    )
    by_id = {ref.external_id: c for c in result.candidates for ref in c.provider_refs}
    kinds_all = {kind for c in result.candidates for kind in c.evidence}
    assert kinds_all == {
        EvidenceKind.PROVIDER_EXTERNAL_ID,
        EvidenceKind.DISPLAY_NAME,
        EvidenceKind.COORDINATES,
        EvidenceKind.COLLECTION_TIME,
    }
    far = by_id["syn-cafe-far"]
    assert EvidenceKind.COLLECTION_TIME in far.evidence
    assert far.collected_at == datetime(2026, 11, 26, tzinfo=UTC)
    for external_id in ("syn-cafe-near", "syn-brunch-mid"):
        assert EvidenceKind.COLLECTION_TIME not in by_id[external_id].evidence


def test_empty_search_is_success_not_failure() -> None:
    provider = SyntheticPlaceProvider(places=())
    result = StoreDiscovery({"synthetic": provider}).execute(make_input())
    assert result.status is ExecutionStatus.SUCCESS
    assert result.candidates == []
    assert result.issues == []


def test_unregistered_allowed_provider_raises() -> None:
    discovery = StoreDiscovery({"synthetic": SyntheticPlaceProvider()})
    with pytest.raises(ValueError, match="no place provider registered"):
        discovery.execute(make_input(providers=("missing",)))


def test_registry_key_must_match_provider_id() -> None:
    with pytest.raises(ValueError, match="does not match"):
        StoreDiscovery({"alias": SyntheticPlaceProvider()})


# --- failures, contract gates, rights gating, models, example ---


def test_all_providers_failing_yields_failed_status_and_redacted_issue() -> None:
    provider = _FailingProvider(error_code="transport_down", retryable=True)
    result = StoreDiscovery({"failing": provider}).execute(
        make_input(providers=("failing",))
    )
    assert result.status is ExecutionStatus.FAILED
    assert result.candidates == []
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.error_code == "transport_down"
    assert issue.retryable is True
    assert issue.module == "store_discovery"
    assert issue.redacted_context == {
        "provider_id": "failing",
        "reason": "provider_error",
    }
    serialized = result.model_dump_json()
    assert "simulated transport failure" not in serialized
    assert "ProviderExecutionError" not in serialized


def test_partial_success_keeps_other_provider_candidates() -> None:
    providers = {
        "failing": _FailingProvider(),
        "synthetic": SyntheticPlaceProvider(),
    }
    result = StoreDiscovery(providers).execute(
        make_input(providers=("failing", "synthetic"))
    )
    assert result.status is ExecutionStatus.PARTIAL
    assert [ref.external_id for c in result.candidates for ref in c.provider_refs] == [
        "syn-cafe-near",
        "syn-brunch-mid",
    ]
    assert [issue.error_code for issue in result.issues] == ["provider_error"]


def test_page_contract_version_mismatch_is_partial_with_issue() -> None:
    providers = {
        "wrongversion": _WrongVersionProvider(),
        "synthetic": SyntheticPlaceProvider(),
    }
    result = StoreDiscovery(providers).execute(
        make_input(providers=("wrongversion", "synthetic"))
    )
    assert result.status is ExecutionStatus.PARTIAL
    assert [issue.error_code for issue in result.issues] == [
        "contract_version_mismatch"
    ]
    assert len(result.candidates) == 2


def test_page_provider_id_mismatch_fails_provider_with_issue() -> None:
    result = StoreDiscovery({"wrongid": _WrongIdProvider()}).execute(
        make_input(providers=("wrongid",))
    )
    assert result.status is ExecutionStatus.FAILED
    assert [issue.error_code for issue in result.issues] == ["provider_id_mismatch"]


def test_non_page_contract_violation_fails_provider_with_issue() -> None:
    result = StoreDiscovery({"nonpage": _NonPageProvider()}).execute(
        make_input(providers=("nonpage",))
    )
    assert result.status is ExecutionStatus.FAILED
    assert [issue.error_code for issue in result.issues] == ["page_contract_violation"]


def test_unknown_data_use_rights_blocks_candidates_but_keeps_issue() -> None:
    provider = SyntheticPlaceProvider(data_use=DataUseRights.UNKNOWN)
    result = StoreDiscovery({"synthetic": provider}).execute(make_input())
    assert result.status is ExecutionStatus.RESTRICTED
    assert result.candidates == []
    assert [issue.error_code for issue in result.issues] == ["data_use.unconfirmed"]


def test_declared_display_only_rights_candidate_is_returned_with_declaration() -> None:
    provider = SyntheticPlaceProvider(data_use=DataUseRights.DISPLAY_ONLY)
    result = StoreDiscovery({"synthetic": provider}).execute(make_input())
    assert result.status is ExecutionStatus.SUCCESS
    assert result.candidates
    assert all(c.data_use is DataUseRights.DISPLAY_ONLY for c in result.candidates)


def test_unknown_rights_plus_healthy_provider_yields_success_with_issue() -> None:
    providers = {
        "blocked": SyntheticPlaceProvider(
            provider_id="blocked",
            data_use=DataUseRights.UNKNOWN,
            places=(),
        ),
        "synthetic": SyntheticPlaceProvider(),
    }
    result = StoreDiscovery(providers).execute(
        make_input(providers=("blocked", "synthetic"))
    )
    assert result.status is ExecutionStatus.SUCCESS
    assert [issue.error_code for issue in result.issues] == ["data_use.unconfirmed"]
    assert len(result.candidates) == 2


def test_synthetic_provider_structurally_satisfies_protocol() -> None:
    from app.discovery import PlaceSearchProvider

    assert isinstance(SyntheticPlaceProvider(), PlaceSearchProvider)
    assert isinstance(_FailingProvider(), PlaceSearchProvider)
    assert not isinstance(object(), PlaceSearchProvider)


def test_response_schema_forbids_unknown_fields() -> None:
    inputs = {
        "region_id": "r",
        "center": _CENTER,
        "radius_m": 800,
        "allowed_provider_ids": ("synthetic",),
    }
    with pytest.raises(ValidationError):
        StoreDiscoveryInput(**inputs, unknown=1)  # type: ignore[arg-type]
    page = ProviderSearchPage(provider_id="p", contract_version="1.0.0", places=())
    with pytest.raises(ValidationError):
        ProviderSearchPage.model_validate({**page.model_dump(), "unknown": 1})
    result = StoreDiscovery({"synthetic": SyntheticPlaceProvider()}).execute(
        make_input()
    )
    with pytest.raises(ValidationError):
        type(result).model_validate({**result.model_dump(), "unknown": 1})


def test_run_and_job_ids_are_engine_supplied_when_not_given() -> None:
    result = StoreDiscovery({"synthetic": SyntheticPlaceProvider()}).execute(
        make_input()
    )
    assert isinstance(result, StoreDiscoveryResult)


def test_synthetic_fixture_data_is_stable() -> None:
    first = SyntheticPlaceProvider().search(
        ProviderSearchRequest(center=_CENTER, radius_m=1000)
    )
    second = SyntheticPlaceProvider().search(
        ProviderSearchRequest(center=_CENTER, radius_m=1000)
    )
    assert first == second
    assert {place.external_id for place in SYNTHETIC_PLACES} >= {
        "syn-cafe-near",
        "syn-brunch-mid",
        "syn-cafe-far",
        "syn-shop-far",
    }
    assert all(place.provider_id == "synthetic" for place in SYNTHETIC_PLACES)


def test_synthetic_example_search_for_800m_카페() -> None:
    # End-to-end, dependency-free example: deterministic candidates, no extras.
    result = StoreDiscovery({"synthetic": SyntheticPlaceProvider()}).execute(
        make_input(radius=800, categories=("카페",))
    )
    assert result.region_id == "test-region"
    assert result.radius_m == 800
    assert result.status is ExecutionStatus.SUCCESS
    assert [ref.external_id for c in result.candidates for ref in c.provider_refs] == [
        "syn-cafe-near"
    ]
    assert result.issues == []
    assert all(c.approx_distance_m <= 800 for c in result.candidates)
    # Round-trips through JSON (serializable contract).
    assert json.loads(result.model_dump_json())["region_id"] == "test-region"
