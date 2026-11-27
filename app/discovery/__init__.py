"""StoreDiscovery engine package (P2-STORE-01, first implementation).

Exports the engine contracts, the swappable place-provider interface, the
synthetic fixture provider and the execution coordinator. See
``Docs/ENGINE_SPEC.md`` §3 for the contract surface and the package modules
for details.
"""

from .contracts import (
    CANDIDATE_DUPLICATE_STATUS_VALUES,
    CROSS_PROVIDER_DUPLICATE_KEY_UNDEFINED,
    CandidateDuplicateStatus,
    Coordinate,
    DataUseRights,
    EvidenceKind,
    ProviderPlace,
    ProviderPlaceRef,
    ProviderSearchPage,
    ProviderSearchRequest,
    StoreCandidate,
    StoreDiscoveryInput,
    StoreDiscoveryResult,
)
from .coordinator import DATA_USE_UNCONFIRMED_ISSUE_CODE, StoreDiscovery
from .providers import (
    DEFAULT_PROVIDER_CONTRACT_VERSION,
    SYNTHETIC_PLACES,
    PlaceSearchProvider,
    ProviderExecutionError,
    SyntheticPlaceProvider,
    haversine_meters,
)

__all__ = [
    "CANDIDATE_DUPLICATE_STATUS_VALUES",
    "CROSS_PROVIDER_DUPLICATE_KEY_UNDEFINED",
    "DATA_USE_UNCONFIRMED_ISSUE_CODE",
    "DEFAULT_PROVIDER_CONTRACT_VERSION",
    "SYNTHETIC_PLACES",
    "CandidateDuplicateStatus",
    "Coordinate",
    "DataUseRights",
    "EvidenceKind",
    "PlaceSearchProvider",
    "ProviderExecutionError",
    "ProviderPlace",
    "ProviderPlaceRef",
    "ProviderSearchPage",
    "ProviderSearchRequest",
    "StoreCandidate",
    "StoreDiscovery",
    "StoreDiscoveryInput",
    "StoreDiscoveryResult",
    "SyntheticPlaceProvider",
    "haversine_meters",
]
