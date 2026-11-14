"""Shared Pydantic contract foundation (namespace 4ddalla.contracts.v1).

Skeleton for the common ENUM set used by all engine modules. Values are
transcribed from Docs/ENGINE_SPEC.md §2 ("상태값 단일 기준").
Do not change values without a contract change (ENGINE_SPEC.md §12).
"""

from __future__ import annotations

from enum import StrEnum


class SourceIdentityStatus(StrEnum):
    VERIFIED = "VERIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


class CollectionPermissionStatus(StrEnum):
    ALLOWED = "ALLOWED"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class PromotionValidationStatus(StrEnum):
    VALIDATED = "VALIDATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


class StoreApplicabilityStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    UNCERTAIN = "UNCERTAIN"
    EXCLUDED = "EXCLUDED"


class PromotionLifecycle(StrEnum):
    UPCOMING = "UPCOMING"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class PublicationBucket(StrEnum):
    CONFIRMED_LIST = "CONFIRMED_LIST"
    UNCERTAIN_LIST = "UNCERTAIN_LIST"
    UPCOMING_LIST = "UPCOMING_LIST"
    HIDDEN = "HIDDEN"


class ExecutionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    UNCHANGED = "UNCHANGED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    RESTRICTED = "RESTRICTED"


class ContentClassification(StrEnum):
    PROMOTION = "PROMOTION"
    NON_PROMOTION = "NON_PROMOTION"
    UNDETERMINED = "UNDETERMINED"


class MonitorChangeType(StrEnum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    ASSET_UPDATED = "ASSET_UPDATED"
    MISSING_FROM_LIST = "MISSING_FROM_LIST"
    UNAVAILABLE = "UNAVAILABLE"


class PromotionScopeType(StrEnum):
    ALL_STORES = "ALL_STORES"
    ALL_EXCEPT = "ALL_EXCEPT"
    SELECTED_STORES = "SELECTED_STORES"
    REGIONAL = "REGIONAL"
    UNKNOWN = "UNKNOWN"


class ScopeCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNKNOWN = "UNKNOWN"


class ErrorSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


__all__ = [
    "CollectionPermissionStatus",
    "ContentClassification",
    "ErrorSeverity",
    "ExecutionStatus",
    "MonitorChangeType",
    "PromotionLifecycle",
    "PromotionScopeType",
    "PromotionValidationStatus",
    "PublicationBucket",
    "ScopeCompleteness",
    "SourceIdentityStatus",
    "StoreApplicabilityStatus",
]
