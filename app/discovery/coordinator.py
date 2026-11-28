"""StoreDiscovery coordinator — fan-out, validation and result assembly (P2-STORE-01).

Execution contract (self-contained so DB-free tests pin the behaviour):

- every allowed provider must be registered, else ``ValueError``;
- providers whose declared rights are ``DataUseRights.UNKNOWN`` are skipped with
  a structured issue — no candidate is returned, persisted or published;
- pagination safety: visited page tokens are tracked per provider; a repeated
  token (self-repeat or cycle) stops that provider with a structured issue, and
  a configured per-provider page-call budget (explicit setting; ``None`` = no
  engine cap, provider's own limits still apply; **a real network provider will
  require a finite budget — values stay undecided until OPEN-001 research is
  approved**) stops pagination when exceeded;
- a provider stop after earlier pages keeps the candidates already validated
  from those pages — only unvalidated data is dropped;
- each returned page is validated in full (page/contract metadata **and** every
  place's ``provider_id``) before any candidate from it is committed, so another
  provider's records mixed into a page are not accepted;
- pagination requests are bounded by visited-token tracking as well as budget;
- candidates beyond the requested radius are filtered out (inclusive boundary);
- repeated exact (provider_id, external_id) pairs collapse into the first
  candidate flagged ``SAME_PROVIDER_REPEAT`` — candidates are never merged, and
  an external id never becomes an internal id;
- cross-provider duplicate pairing is explicitly NOT performed: no shared
  identity key exists (``CROSS_PROVIDER_DUPLICATE_KEY_UNDEFINED``);
- empty result (providers OK, zero candidates) is valid SUCCESS — distinct from
  FAILED/PARTIAL via status and issues; a valid but empty page counts as a
  normally handled page, while a page that fails contract validation never does;
- status separates supplier-scope completion from whether valid data was
  obtained: SUCCESS = every requested scope completed normally (0 results
  included); PARTIAL = valid pages/results or a completed scope exist and at
  least one scope is not completed (error, rights limit, budget, token stop);
  RESTRICTED = no scope completed and every requested target was rights-blocked;
  FAILED = no valid page and no completed scope, with at least one failure or
  incomplete stop. ``UNCHANGED`` is not used for discovery runs.

Category consistency between requested 업종 and provider-returned 업종 cannot
be validated generically yet: neither side's taxonomy is fixed (업종 분류
미확정 — not decided here), so the engine passes the request through and lets
the provider filter; a provider that echoes records outside the requested
categories is not detectable without a taxonomy decision.

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
    """Provider-agnostic discovery engine; built with a provider registry.

    ``page_budget`` (optional) is an explicit per-provider ceiling on page
    requests per run; ``None`` means the engine applies no cap — no default
    limit is invented because real provider quotas are undecided (OPEN-001).
    """

    def __init__(
        self,
        providers: Mapping[str, PlaceSearchProvider],
        *,
        page_budget: int | None = None,
    ) -> None:
        if page_budget is not None and (
            isinstance(page_budget, bool)
            or not isinstance(page_budget, int)
            or page_budget < 1
        ):
            raise ValueError("page_budget must be a positive int or None")
        for provider_id, provider in providers.items():
            if provider.provider_id != provider_id:
                raise ValueError(
                    f"registry key {provider_id!r} does not match "
                    f"provider_id {provider.provider_id!r}"
                )
        self._providers = dict(providers)
        self._page_budget = page_budget

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
        # Completion is tracked per requested scope (provider id), independently of
        # how many candidates resulted: a scope that completed normally — even with
        # zero (valid, empty) pages/results — counts as completed. ``valid_pages``
        # counts validated pages so "valid data obtained, later page failed" stays
        # distinguishable from "nothing valid obtained at all".
        completed = failed = blocked = incomplete = 0
        valid_pages = 0

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
            visited_tokens: set[str | None] = set()
            requests = 0
            provider_completed = False
            try:
                while True:
                    if page_token is not None and page_token in visited_tokens:
                        issues.append(
                            _issue(
                                "pagination.token_repeat",
                                run_id=run_id,
                                job_id=job_id,
                                provider_id=provider_id,
                                reason="repeated page token detected (self-repeat or cycle); pagination stopped",
                            )
                        )
                        break
                    if self._page_budget is not None and requests >= self._page_budget:
                        issues.append(
                            _issue(
                                "pagination.budget_exhausted",
                                run_id=run_id,
                                job_id=job_id,
                                provider_id=provider_id,
                                reason="page call budget exhausted; pagination stopped",
                                retryable=True,
                            )
                        )
                        break
                    visited_tokens.add(page_token)
                    requests += 1
                    page = provider.search(
                        ProviderSearchRequest(
                            center=center,
                            radius_m=radius_m,
                            categories=discovery_input.categories,
                            page_token=page_token,
                        )
                    )
                    _check_page_contract(provider, page)
                    valid_pages += 1
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
                        provider_completed = True
                        break
            except ProviderExecutionError as exc:
                failed += 1
                issues.append(_provider_issue(exc, run_id=run_id, job_id=job_id))
                continue
            if provider_completed:
                completed += 1
            else:
                incomplete += 1

        if provider_ids and blocked == len(provider_ids):
            # Every requested target was rights-blocked; nothing could run.
            status = ExecutionStatus.RESTRICTED
        elif valid_pages == 0 and completed == 0 and (failed > 0 or incomplete > 0):
            # No valid page and no normally completed scope, but execution did
            # fail/stop somewhere — never "upgrade" this to PARTIAL.
            status = ExecutionStatus.FAILED
        elif completed < len(provider_ids):
            status = ExecutionStatus.PARTIAL
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
    for place in page.places:
        if place.provider_id != provider.provider_id:
            raise ProviderExecutionError(
                "place provider_id mismatch",
                provider_id=provider.provider_id,
                error_code="place_provider_id_mismatch",
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
