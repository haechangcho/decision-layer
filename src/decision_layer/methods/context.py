"""Execution context shared by Methods: the analysis scope, the dataset planner
entry point and the query budget. Methods never call a provider directly
(ADR-005); they ask the context for datasets.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Awaitable, Callable

from ..core.errors import DecisionLayerError, UnknownSemanticObject
from ..core.periods import ExecutionPolicy, PeriodChoice
from ..core.models import (
    Dataset, DatasetSpec, Filter, QueryAttempt, QueryProvenance, SemanticCatalog, SemanticObject, TimeScope,
)
from ..semantic.provider import Credentials, SemanticProvider
from ..i18n import _


class QueryBudgetExceeded(DecisionLayerError):
    code = "QUERY_BUDGET_EXCEEDED"
    http_status = 422


class NeedsInput(DecisionLayerError):
    """A choice only the user can make (e.g. which time dimension the period applies to)."""
    code = "NEEDS_INPUT"
    http_status = 200

    def __init__(self, question: str, field: str, candidates: list[dict[str, Any]]) -> None:
        super().__init__(question, field=field, candidates=candidates)
        self.question, self.field, self.candidates = question, field, candidates


class Refused(DecisionLayerError):
    """Fail closed (ADR-020): the request can't be answered correctly with what is available."""
    code = "REFUSED"
    http_status = 200


@dataclass
class Scope:
    """What every step of an analysis shares: period, the date it applies to, common filters."""
    date_range: tuple[str, str] | None = None
    time_dimension: str | None = None
    filters: list[Filter] = field(default_factory=list)

    def with_filters(self, extra: list[Filter]) -> "Scope":
        return Scope(self.date_range, self.time_dimension, [*self.filters, *extra])


@dataclass
class ExecutionContext:
    provider: SemanticProvider
    credentials: Credentials
    catalog: SemanticCatalog
    scope: Scope = field(default_factory=Scope)
    max_queries: int = 30
    queries: list[QueryProvenance] = field(default_factory=list)
    execution_policy: ExecutionPolicy | None = None
    attempts: list[QueryAttempt] = field(default_factory=list)
    step_id: str | None = None
    persist_attempts: Callable[[], Awaitable[None]] | None = None
    allowed_measures: set[str] | None = None
    _attempt_count: int = 0

    def obj(self, ref: str) -> SemanticObject:
        o = self.catalog.get(ref)
        if o is None:
            raise UnknownSemanticObject(_("'{ref}' was not found or you don't have access to it", ref=ref), ref=ref)
        return o

    async def dataset(self, spec: DatasetSpec, *, with_sql: bool = False) -> Dataset:
        if max(self._attempt_count, len(self.queries)) >= self.max_queries:
            raise QueryBudgetExceeded(_("The query budget ({limit}) is used up", limit=self.max_queries))
        if self.execution_policy:
            dates = spec.time.date_range if spec.time else None
            if self.scope.date_range and dates is None:
                raise Refused(_("This query did not apply the selected period. Check the Method's date handling."))
            issue = self.execution_policy.issue(PeriodChoice(mode="range", date_range=dates) if dates else PeriodChoice(mode="all"))
            if issue:
                raise Refused(_(issue))
        refs = [*spec.measures, *spec.dimensions, *(f.member for f in spec.filters), *(ref for ref, direction in spec.order)]
        if spec.time:
            refs.append(spec.time.dimension)
        if spec.entity:
            refs.append(spec.entity)
        for ref in refs:
            if not self.obj(ref).public:
                raise UnknownSemanticObject("Semantic object is unavailable.")
            if self.allowed_measures is not None and self.obj(ref).kind == "measure" and ref not in self.allowed_measures:
                raise Refused("The query selects a measure outside this Recipe's scope.")
        for required in self.scope.filters:
            if required not in spec.filters:
                raise Refused("The query did not apply a required Run filter.")
        await self.provider.validate_dataset(spec, self.credentials)
        attempt = QueryAttempt(spec=spec.model_copy(deep=True), step_id=self.step_id)
        self.attempts.append(attempt)
        self._attempt_count += 1
        if self.persist_attempts:
            await self.persist_attempts()
        try:
            ds = await self.provider.execute(spec, self.credentials, with_sql=with_sql)
            self.queries.extend(ds.provenance)
            if self.execution_policy and len(ds.rows) > self.execution_policy.max_result_rows:
                raise Refused(_("The result exceeds the server row limit. Narrow the period or filters."))
            attempt.status = "success"
            return ds
        except BaseException as exc:
            attempt.status = "failed"
            attempt.error_code = exc.code if isinstance(exc, DecisionLayerError) else "QUERY_INTERRUPTED" if isinstance(exc, asyncio.CancelledError) else "PROVIDER_ERROR"
            raise
        finally:
            if self.persist_attempts:
                await self.persist_attempts()

    # ── scope helpers ──────────────────────────────────────────────────────
    def time_dimension_for(self, metric: str) -> str:
        """Explicit scope > the metric cube's only time dimension > optional provider hint > ask."""
        if self.scope.time_dimension:
            if self.obj(self.scope.time_dimension).kind != "time_dimension":
                raise Refused(_("'{ref}' is not a time dimension", ref=self.scope.time_dimension))
            return self.scope.time_dimension
        obj = self.obj(metric)
        candidates = [o for o in self.catalog.objects
                      if o.kind == "time_dimension" and o.ref in obj.dimension_refs]
        if len(candidates) == 1:
            return candidates[0].ref
        hint = obj.time_dimension
        if hint and any(c.ref == hint for c in candidates):
            return hint
        if not candidates:
            raise Refused(_("The metric '{ref}' has no declared time dimension, so a period can't be applied", ref=metric))
        raise NeedsInput(_("Which date should the period apply to?"), "time_dimension",
                         [{"value": c.ref, "label": c.title} for c in candidates])

    def time_scope(self, metric: str, date_range: tuple[str, str] | None = None,
                   granularity: str | None = None) -> TimeScope | None:
        """TimeScope for the metric, or None when neither a period nor a granularity is asked for."""
        rng = date_range or self.scope.date_range
        if not rng and not granularity:
            return None
        return TimeScope(dimension=self.time_dimension_for(metric), date_range=rng, granularity=granularity)

    def count_measure(self, metric: str) -> str | None:
        """A sample count identified by the provider, never a guessed sibling metric."""
        ref = self.obj(metric).count_measure
        return ref if ref and self.catalog.get(ref) else None

    def units_measure(self, metric: str) -> str | None:
        """The declared count denominator, or a provider-confirmed sample count."""
        # Declared parts decide: only count/count is a share of units. Ratios of amounts or other
        # sums (value per unit, amount shares) get none, so no interval is
        # attached by coincidence. Undeclared measures need a provider-confirmed sample count.
        parts = self.obj(metric).ratio_parts
        if parts:
            num, den = (self.obj(p) for p in parts)
            return parts[1] if num.metric_kind == den.metric_kind == "count" else None
        return self.count_measure(metric)


def previous_period(date_range: tuple[str, str]) -> tuple[str, str]:
    """The period of equal length right before date_range."""
    start, end = (date.fromisoformat(d) for d in date_range)
    days = (end - start).days + 1
    return ((start - timedelta(days=days)).isoformat(), (start - timedelta(days=1)).isoformat())
