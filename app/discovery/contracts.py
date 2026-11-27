"""StoreDiscovery engine — contracts, provider interface, execution logic.

Implements the StoreDiscovery surface of ``Docs/ENGINE_SPEC.md`` §3:

- input: supported region, center point, 800/1000 m radius, category, allowed
  place-data providers;
- output: store candidates, provider external place references, duplicate
  flags, identity evidence, data use / retention rights, execution status and
  structured issues.

This first implementation (P2-STORE-01) contains:

- Pydantic input/output models built on the shared ``ContractModel`` base
  (unknown fields rejected, per P1-CONTRACT-02 / ENGINE_SPEC §12.1);
- a swappable ``PlaceSearchProvider`` protocol: center + radius search,
  category condition, pagination, provider-declared contract version and
  data-use rights, opaque external place ids;
- ``StoreDiscovery`` execution logic: input validation, haversine radius
  filtering, candidate collection, pagination, same-provider repeated
  external-id detection, empty-result vs failure distinction, partial success
  and provider-error handling, usage-rights gating;
- ``SyntheticPlaceProvider``: deterministic in-memory fixture data only.

Deliberately out of scope here (separate approval/decision required):

- physical persistence of candidates — the DATA_MODEL.md §3 entity list still
  has no approved DDL and no Alembic revision;
- any real place provider (DECISIONS.md OPEN-001), network calls, crawling,
  OCR/LLM or paid services;
- automatic identity merges — candidates are never merged on vendor/display
  name, and a provider external id is never an internal identifier:
  ``candidate_id`` is engine-generated and provider refs stay references;
- cross-provider duplicate pairing — no shared identity key exists yet, so the
  coordinator does not invent one from names or coordinates. Same-provider exact
  external-id repeats are decidable; cross-provider comparison is explicitly
  not performed (see ``CROSS_PROVIDER_DUPLICATE_KEY_UNDEFINED``).

Rights handling: a provider that does not declare confirmed storage/display/
retention rights (``DataUseRights.UNKNOWN``) is skipped with a structured
issue; no candidate from it is returned. Fixture rights on the synthetic
provider are test data modelling policy states — not claims about any real
provider.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field, StrictInt, field_validator

from app.contracts.enums import ExecutionStatus
from app.contracts.envelope import ContractModel, ExecutionIssue

#: Synthetic-provider fixtures declare this contract version; coordinator
#: compares ``ProviderSearchPage.contract_version`` against it.
DEFAULT_PROVIDER_CONTRACT_VERSION = "1.0.0"

#: Opaque marker documenting that no cross-provider duplicate key is defined
#: (name/coordinate guessing is deliberately not implemented).
CROSS_PROVIDER_DUPLICATE_KEY_UNDEFINED = "cross_provider_duplicate_key_undefined"

#: Issue code emitted when an allowed provider's data-use rights are unconfirmed.
DATA_USE_UNCONFIRMED_ISSUE_CODE = "data_use.unconfirmed"

_SUPPORTED_RADII_M = (800, 1000)

_LATITUDE = Annotated[float, Field(ge=-90.0, le=90.0, allow_inf_nan=False)]
_LONGITUDE = Annotated[float, Field(ge=-180.0, le=180.0, allow_inf_nan=False)]


class DataUseRights(StrEnum):
    """Provider-declared handling rights (fixture/modelled states, not a verdict).

    Values model the *declared* policy only; the engine never confirms rights
    itself, and a real provider's rights remain subject to OPEN-001 decisions.
    """

    STORE_ALLOWED = "STORE_ALLOWED"  # declared: storage/display within policy
    DISPLAY_ONLY = "DISPLAY_ONLY"  # declared: transient display, no retention
    UNKNOWN = "UNKNOWN"  # not confirmed -> coordinator blocks and records issue


class CandidateDuplicateStatus(StrEnum):
    """Duplicate signal decidable from provider-supplied references."""

    UNKNOWN = "UNKNOWN"  # no decidable signal (cross-provider key undefined)
    SAME_PROVIDER_REPEAT = "SAME_PROVIDER_REPEAT"  # repeated exact external id


class EvidenceKind(StrEnum):
    """What a candidate's identity evidence is — observations, not a verdict.

    Named per ENGINE_SPEC §3 but scoped honestly: these record which fields the
    provider response supplied. They imply no official/verified identity status.
    """

    PROVIDER_EXTERNAL_ID = "PROVIDER_EXTERNAL_ID"
    DISPLAY_NAME = "DISPLAY_NAME"
    COORDINATES = "COORDINATES"
    COLLECTION_TIME = "COLLECTION_TIME"


CANDIDATE_DUPLICATE_STATUS_VALUES = frozenset(
    status.value for status in CandidateDuplicateStatus
)


_LATITUDE = Annotated[float, Field(ge=-90.0, le=90.0, allow_inf_nan=False, strict=True)]
_LONGITUDE = Annotated[
    float, Field(ge=-180.0, le=180.0, allow_inf_nan=False, strict=True)
]


class _GeoPoint(ContractModel):
    """Latitude/longitude with range/finiteness checks.

    ``strict=True`` keeps the contract to real numbers: bool and numeric
    strings are rejected instead of silently coerced.
    """

    latitude: _LATITUDE
    longitude: _LONGITUDE


class Coordinate(_GeoPoint):
    """Center point of the radial search (WGS84 degrees)."""


class StoreDiscoveryInput(ContractModel):
    """Validated StoreDiscovery request (ENGINE_SPEC §3 input surface)."""

    region_id: str = Field(min_length=1)
    center: Coordinate
    radius_m: Annotated[StrictInt, Field(ge=1)]
    categories: tuple[str, ...] = ()
    allowed_provider_ids: tuple[str, ...]

    @field_validator("radius_m")
    @classmethod
    def _radius_supported(cls, value: int) -> int:
        if value not in _SUPPORTED_RADII_M:
            raise ValueError(
                f"radius_m must be one of {_SUPPORTED_RADII_M} (product policy)"
            )
        return value

    @field_validator("categories", "allowed_provider_ids")
    @classmethod
    def _no_blank_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError("must not contain blank items")
        return value

    @field_validator("allowed_provider_ids")
    @classmethod
    def _at_least_one_provider(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("allowed_provider_ids must name at least one provider")
        return value


class _Audited(ContractModel):
    collected_at: datetime | None = None  # provider-reported collection time

    @field_validator("collected_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("collected_at must be timezone-aware")
        return value


class ProviderPlaceRef(ContractModel):
    """Provider-issued external place reference; never an internal id."""

    provider_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)


class ProviderPlace(_GeoPoint, _Audited):
    """One place as reported by a provider (synthetic or, later, real)."""

    provider_id: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    category: str | None = None


class StoreCandidate(_GeoPoint, _Audited):
    """Discovery result candidate: references + evidence, not an entity record.

    No internal entity exists yet (no approved DDL), so identity stays
    candidate-scoped; ``candidate_id`` is engine-generated for this result and
    ``provider_refs`` keep external ids opaque and separate.
    """

    candidate_id: UUID = Field(default_factory=uuid4)
    region_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    provider_refs: tuple[ProviderPlaceRef, ...]
    source_category: str | None = None
    evidence: tuple[EvidenceKind, ...] = ()
    data_use: DataUseRights
    duplicate_status: CandidateDuplicateStatus = CandidateDuplicateStatus.UNKNOWN
    possible_duplicate_of: tuple[UUID, ...] = ()
    approx_distance_m: int = Field(ge=0)

    @field_validator("provider_refs")
    @classmethod
    def _at_least_one_ref(
        cls, value: tuple[ProviderPlaceRef, ...]
    ) -> tuple[ProviderPlaceRef, ...]:
        if not value:
            raise ValueError("provider_refs must not be empty")
        return value


class ProviderSearchRequest(ContractModel):
    """One page request handed to a provider (provider receives, validates)."""

    center: Coordinate
    radius_m: Annotated[StrictInt, Field(ge=1)]
    categories: tuple[str, ...] = ()
    page_token: str | None = None  # opaque provider token; None = first page


class ProviderSearchPage(ContractModel):
    """One provider page of places plus the next-page cursor, if any."""

    provider_id: str = Field(min_length=1)
    contract_version: str = Field(min_length=1)
    places: tuple[ProviderPlace, ...] = ()
    next_page_token: str | None = None


class StoreDiscoveryResult(ContractModel):
    """Engine output: candidates + issues + status for one discovery run."""

    region_id: str = Field(min_length=1)
    radius_m: int
    status: ExecutionStatus
    candidates: list[StoreCandidate] = Field(default_factory=list)
    issues: list[ExecutionIssue] = Field(default_factory=list)
