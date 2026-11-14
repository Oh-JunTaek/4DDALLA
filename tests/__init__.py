from __future__ import annotations

from app.contracts.enums import (
    CollectionPermissionStatus,
    ContentClassification,
    ErrorSeverity,
    ExecutionStatus,
    MonitorChangeType,
    PromotionLifecycle,
    PromotionScopeType,
    PromotionValidationStatus,
    PublicationBucket,
    ScopeCompleteness,
    SourceIdentityStatus,
    StoreApplicabilityStatus,
)

EXPECTED_VALUES = {
    SourceIdentityStatus: {"VERIFIED", "REVIEW_REQUIRED", "REJECTED"},
    CollectionPermissionStatus: {"ALLOWED", "RESTRICTED", "UNKNOWN"},
    PromotionValidationStatus: {"VALIDATED", "REVIEW_REQUIRED", "REJECTED"},
    StoreApplicabilityStatus: {"CONFIRMED", "UNCERTAIN", "EXCLUDED"},
    PromotionLifecycle: {"UPCOMING", "ACTIVE", "ENDED", "CANCELLED", "UNKNOWN"},
    PublicationBucket: {"CONFIRMED_LIST", "UNCERTAIN_LIST", "UPCOMING_LIST", "HIDDEN"},
    ExecutionStatus: {"SUCCESS", "UNCHANGED", "PARTIAL", "FAILED", "RESTRICTED"},
    ContentClassification: {"PROMOTION", "NON_PROMOTION", "UNDETERMINED"},
    MonitorChangeType: {"NEW", "UPDATED", "ASSET_UPDATED", "MISSING_FROM_LIST", "UNAVAILABLE"},
    PromotionScopeType: {"ALL_STORES", "ALL_EXCEPT", "SELECTED_STORES", "REGIONAL", "UNKNOWN"},
    ScopeCompleteness: {"COMPLETE", "INCOMPLETE", "UNKNOWN"},
    ErrorSeverity: {"CRITICAL", "HIGH", "MEDIUM", "LOW"},
}


def test_enum_values_match_transcribed_contract() -> None:
    for enum_cls, expected in EXPECTED_VALUES.items():
        assert {member.value for member in enum_cls} == expected


def test_enum_members_are_strings() -> None:
    for enum_cls in EXPECTED_VALUES:
        assert issubclass(enum_cls, str)
