"""Place-provider interface and the synthetic fixture provider (P2-STORE-01).

Real place providers are NOT selected or integrated in this ticket
(DECISIONS.md OPEN-001); external APIs, crawling and cost are out of scope.
``PlaceSearchProvider`` is the swappable structural contract; the only
implementation here is ``SyntheticPlaceProvider`` serving deterministic
in-memory fixtures for DB-free tests and local demos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from .contracts import (
    DEFAULT_PROVIDER_CONTRACT_VERSION,
    Coordinate,
    DataUseRights,
    ProviderPlace,
    ProviderSearchPage,
    ProviderSearchRequest,
)

_SYNTHETIC_CENTER = Coordinate(latitude=37.497900, longitude=127.098300)
_SYNTHETIC_PROVIDER_ID = "synthetic"

# Fixture distances are haversine from _SYNTHETIC_CENTER in metres (1 deg lat
# ~ 111195 m). "near" ~40, "mid" ~300, "cafe-far" ~820, "shop-far" ~2400:
# an 800 m search excludes cafe-far/shop-far; 1000 m includes cafe-far.
# Coordinates are synthetic test data, not real store locations.
SYNTHETIC_PLACES = (
    ProviderPlace(
        provider_id=_SYNTHETIC_PROVIDER_ID,
        external_id="syn-cafe-near",
        display_name="합성 카페 Near",
        category="카페",
        latitude=_SYNTHETIC_CENTER.latitude + 40 / 111195,
        longitude=_SYNTHETIC_CENTER.longitude,
    ),
    ProviderPlace(
        provider_id=_SYNTHETIC_PROVIDER_ID,
        external_id="syn-brunch-mid",
        display_name="합성 식당 Mid",
        category="분식",
        latitude=_SYNTHETIC_CENTER.latitude + 300 / 111195,
        longitude=_SYNTHETIC_CENTER.longitude,
    ),
    ProviderPlace(
        provider_id=_SYNTHETIC_PROVIDER_ID,
        external_id="syn-cafe-far",
        display_name="합성 카페 Far",
        category="카페",
        latitude=_SYNTHETIC_CENTER.latitude + 820 / 111195,
        longitude=_SYNTHETIC_CENTER.longitude,
        collected_at=datetime(2026, 11, 26, tzinfo=UTC),
    ),
    ProviderPlace(
        provider_id=_SYNTHETIC_PROVIDER_ID,
        external_id="syn-shop-far",
        display_name="합성 상점 Far",
        category="기타",
        latitude=_SYNTHETIC_CENTER.latitude + 2400 / 111195,
        longitude=_SYNTHETIC_CENTER.longitude,
    ),
)


class ProviderExecutionError(RuntimeError):
    """A provider failed to complete a search/page (transport, limits, contract).

    ``message`` is kept generic by convention: the coordinator never copies it
    into results/issues, so URLs, connection text or other transport detail
    cannot leak there.
    """

    def __init__(
        self,
        message: str,
        *,
        provider_id: str,
        error_code: str = "provider_error",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider_id = provider_id
        self.error_code = error_code
        self.retryable = retryable


@runtime_checkable
class PlaceSearchProvider(Protocol):
    """Structural place-search contract: radial search + declared rights/version.

    provider_id / contract_version / data_use are declared attributes;
    ``search`` returns one page. Providers enforce their own request budgets
    and surface exhaustion as ``ProviderExecutionError`` — the coordinator never
    bypasses provider limits, pagination or terms.
    """

    provider_id: str
    contract_version: str
    data_use: DataUseRights

    def search(self, request: ProviderSearchRequest) -> ProviderSearchPage:
        """Return one page of places for the request (first page if no token)."""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class SyntheticPlaceProvider:
    """Deterministic in-memory provider: category filter, radius, pagination.

    Pure fixture: no network, no files, no randomness; safe for DB-free tests.
    """

    provider_id: str = _SYNTHETIC_PROVIDER_ID
    contract_version: str = DEFAULT_PROVIDER_CONTRACT_VERSION
    data_use: DataUseRights = DataUseRights.STORE_ALLOWED
    places: tuple[ProviderPlace, ...] = SYNTHETIC_PLACES
    page_size: int = 2

    def __post_init__(self) -> None:
        if not self.provider_id:
            raise ValueError("provider_id must not be empty")
        if self.page_size < 1:
            raise ValueError("page_size must be >= 1")
        for place in self.places:
            if place.provider_id != self.provider_id:
                raise ValueError("fixture provider_id does not match provider")

    def search(self, request: ProviderSearchRequest) -> ProviderSearchPage:
        matched = [
            place
            for place in self.places
            if _within_radius(place, request.center, request.radius_m)
            and (not request.categories or place.category in request.categories)
        ]
        start = _page_offset(request.page_token)
        page_places = tuple(matched[start : start + self.page_size])
        return ProviderSearchPage(
            provider_id=self.provider_id,
            contract_version=self.contract_version,
            places=page_places,
            next_page_token=(
                str(start + len(page_places))
                if start + len(page_places) < len(matched)
                else None
            ),
        )


def _page_offset(token: str | None) -> int:
    if token is None:
        return 0
    try:
        offset = int(token)
    except ValueError:
        raise ValueError(f"invalid page_token: {token!r}") from None
    if offset < 0:
        raise ValueError(f"invalid page_token: {token!r}")
    return offset


def _within_radius(place: ProviderPlace, center: Coordinate, radius_m: int) -> bool:
    return (
        _haversine_m(center.latitude, center.longitude, place.latitude, place.longitude)
        <= radius_m
    )


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance on a 6371 km sphere (meters)."""
    radius_m = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    a = min(1.0, max(0.0, a))
    return radius_m * 2 * math.asin(math.sqrt(a))


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Public wrapper over the haversine helper (tests/logs may reuse it)."""
    return _haversine_m(lat1, lon1, lat2, lon2)
