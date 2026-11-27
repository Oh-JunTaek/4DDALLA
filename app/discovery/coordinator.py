"""StoreDiscovery coordinator — fan-out, validation and result assembly (P2-STORE-01).

Execution contract (self-contained so DB-free tests pin the behaviour):

- every allowed provider must be registered, else ``ValueError``;
- providers whose declared rights are ``DataUseRights.UNKNOWN`` are skipped with
  a structured issue — no candidate is returned, persisted or published;
- pagination continues while ``next_page_token`` is set; provider failures are
  captured per provider (``ProviderExecutionError``) as structured issues and do
  not abort other providers;
- candidates beyond the requested radius are filtered out (inclusive boundary);
- repeated exact (provider_id, external_id) pairs collapse into the first
  candidate flagged ``SAME_PROVIDER_REPEAT`` — candidates are never merged, and
  an external id never becomes an internal id;
- cross-provider duplicate pairing is explicitly NOT performed: no shared
  identity key exists (``CROSS_PROVIDER_DUPLICATE_KEY_UNDEFINED``);
- empty result (providers OK, zero candidates) is valid SUCCESS — distinct from
  FAILED/PARTIAL via status and issues;
- status precedence: FAILED (all attempted providers failed) > PARTIAL (mixed) >
  RESTRICTED (nothing succeeded, at least one rights-blocked) > SUCCESS.

``run_id``/``job_id`` default to fresh UUIDs so the engine is usable standalone
(DB-free tests/demos); orchestration may pass the envelope's identifiers.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.contracts.enums import ErrorSeverity, ExecutionStatus
from app.contracts.envelope import ExecutionIssue

from .contracts import (
    DATA_USE_UNCONFIRMED_ISSUE_CODE,
    CandidateDuplicateStatus,
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
from .providers import PlaceSearchProvider, ProviderExecutionError, haversine_meters

_MODULE = "store_discovery"


def _evidence_for(place: ProviderPlace) -> tuple[EvidenceKind, ...]:
    """Which provider fields supplied this candidate (observation, not verdict)."""
    kinds = [
        EvidenceKind.PROVIDER_EXTERNAL_ID,
        EvidenceKind.DISPLAY_NAME,
        EvidenceKind.COORDINATES,
    ]
    if place.collected_at is not None:
        kinds.append(EvidenceKind.COLLECTION_TIME)
    return tuple(kinds)


def _sort_key(candidate: StoreCandidate) -> tuple:
    """Deterministic order: distance, then provider/external-id references."""
    return (
        candidate.approx_distance_m,
        tuple((ref.provider_id, ref.external_id) for ref in candidate.provider_refs),
    )


class StoreDiscovery:
    """Provider-agnostic discovery engine; built with a provider registry."""

    def __init__(self, providers: Mapping[str, PlaceSearchProvider]) -> None:
        for provider_id, provider in providers.items():
            if provider.provider_id != provider_id:
                raise ValueError(
                    f"registry key {provider_id!r} does not match "
                    f"provider_id {provider.provider_id!r}"
                )
        self._providers = dict(providers)

    def execute(
        self,
        discovery_input: StoreDiscoveryInput,
        *,
        run_id: UUID | None = None,
        job_id: UUID | None = None,
    ) -> StoreDiscoveryResult:
        """Run one discovery: validated input in, result candidates/issues out."""
        if run_id is None:
            run_id = uuid4()
        if job_id is None:
            job_id = uuid4()

        provider_ids = list(dict.fromkeys(discovery_input.allowed_provider_ids))
        missing = [pid for pid in provider_ids if pid not in self._providers]
        if missing:
            raise ValueError(
                f"no place provider registered for allowed id(s): {', '.join(missing)}"
            )

        radius_m = discovery_input.radius_m
        center = discovery_input.center
        candidates: list[StoreCandidate] = []
        issues: list[ExecutionIssue] = []
        kept: dict[tuple[str, str], StoreCandidate] = {}
        succeeded = failed = blocked = 0

        for provider_id in provider_ids:
            provider = self._providers[provider_id]
            if provider.data_use is DataUseRights.UNKNOWN:
                blocked += 1
                issues.append(
                    _issue(
                        DATA_USE_UNCONFIRMED_ISSUE_CODE,
                        run_id=run_id,
                        job_id=job_id,
                        provider_id=provider_id,
                        reason="declared data-use rights unconfirmed; not persisted or published",
                    )
                )
                continue

            page_token: str | None = None
            try:
                while True:
                    page = provider.search(
                        ProviderSearchRequest(
                            center=center,
                            radius_m=radius_m,
                            categories=discovery_input.categories,
                            page_token=page_token,
                        )
                    )
                    _check_page_contract(provider, page)
                    for place in page.places:
                        key = (provider_id, place.external_id)
                        if key in kept:
                            kept[
                                key
                            ].duplicate_status = (
                                CandidateDuplicateStatus.SAME_PROVIDER_REPEAT
                            )
                            continue
                        distance = haversine_meters(
                            center.latitude,
                            center.longitude,
                            place.latitude,
                            place.longitude,
                        )
                        if distance > radius_m:
                            continue
                        candidates.append(
                            StoreCandidate(
                                region_id=discovery_input.region_id,
                                display_name=place.display_name,
                                latitude=place.latitude,
                                longitude=place.longitude,
                                provider_refs=(
                                    ProviderPlaceRef(
                                        provider_id=provider_id,
                                        external_id=place.external_id,
                                    ),
                                ),
                                source_category=place.category,
                                collected_at=place.collected_at,
                                evidence=_evidence_for(place),
                                data_use=provider.data_use,
                                approx_distance_m=round(distance),
                            )
                        )
                        kept[key] = candidates[-1]
                    page_token = page.next_page_token
                    if not page_token:
                        break
            except ProviderExecutionError as exc:
                failed += 1
                issues.append(_provider_issue(exc, run_id=run_id, job_id=job_id))
                continue
            succeeded += 1

        if failed and succeeded == 0:
            status = ExecutionStatus.FAILED
        elif failed:
            status = ExecutionStatus.PARTIAL
        elif blocked and succeeded == 0:
            status = ExecutionStatus.RESTRICTED
        else:
            status = ExecutionStatus.SUCCESS

        candidates.sort(key=_sort_key)
        return StoreDiscoveryResult(
            region_id=discovery_input.region_id,
            radius_m=radius_m,
            status=status,
            candidates=candidates,
            issues=issues,
        )


def _check_page_contract(provider: PlaceSearchProvider, page: object) -> None:
    """Provider/version consistency of returned pages (engine-side gate)."""
    if not isinstance(page, ProviderSearchPage):
        raise ProviderExecutionError(
            "page contract violation",
            provider_id=provider.provider_id,
            error_code="page_contract_violation",
        )
    if page.provider_id != provider.provider_id:
        raise ProviderExecutionError(
            "page provider_id mismatch",
            provider_id=provider.provider_id,
            error_code="provider_id_mismatch",
        )
    if page.contract_version != provider.contract_version:
        raise ProviderExecutionError(
            "page contract_version mismatch",
            provider_id=provider.provider_id,
            error_code="contract_version_mismatch",
        )


def _issue(
    code: str,
    *,
    run_id: UUID,
    job_id: UUID,
    provider_id: str,
    reason: str,
    retryable: bool = False,
) -> ExecutionIssue:
    """Structured, redacted issue record for engine-side failures."""
    return ExecutionIssue(
        event_id=uuid4(),
        job_id=job_id,
        run_id=run_id,
        module=_MODULE,
        error_code=code,
        severity=ErrorSeverity.MEDIUM,
        occurred_at=datetime.now(UTC),
        retryable=retryable,
        fingerprint=f"{provider_id}:{code}",
        redacted_context={"provider_id": provider_id, "reason": reason},
    )


def _provider_issue(
    exc: ProviderExecutionError, *, run_id: UUID, job_id: UUID
) -> ExecutionIssue:
    """Convert a provider failure to an issue without leaking its message."""
    return _issue(
        exc.error_code,
        run_id=run_id,
        job_id=job_id,
        provider_id=exc.provider_id,
        reason="provider_error",
        retryable=exc.retryable,
    )
