"""Execution context shared by Methods: the analysis scope, the dataset planner
entry point and the query budget. Methods never call a provider directly
(ADR-005); they ask the context for datasets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from ..core.errors import DecisionLayerError, UnknownSemanticObject
from ..core.ids import SemanticRef
from ..core.models import (
    Dataset, DatasetSpec, Filter, QueryProvenance, SemanticCatalog, SemanticObject, TimeScope,
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

    def obj(self, ref: str) -> SemanticObject:
        o = self.catalog.get(ref)
        if o is None:
            raise UnknownSemanticObject(_("'{ref}' was not found or you don't have access to it", ref=ref), ref=ref)
        return o

    async def dataset(self, spec: DatasetSpec, *, with_sql: bool = False) -> Dataset:
        if len(self.queries) >= self.max_queries:
            raise QueryBudgetExceeded(_("The query budget ({limit}) is used up", limit=self.max_queries))
        ds = await self.provider.execute(spec, self.credentials, with_sql=with_sql)
        self.queries.extend(ds.provenance)
        return ds

    # ── scope helpers ──────────────────────────────────────────────────────
    def time_dimension_for(self, metric: str) -> str:
        """Explicit scope > the metric cube's only time dimension > optional provider hint > ask."""
        if self.scope.time_dimension:
            if self.obj(self.scope.time_dimension).kind != "time_dimension":
                raise Refused(_("'{ref}' is not a time dimension", ref=self.scope.time_dimension))
            return self.scope.time_dimension
        cube = SemanticRef.parse(metric).cube
        candidates = [o for o in self.catalog.objects
                      if o.kind == "time_dimension" and SemanticRef.parse(o.ref).cube == cube]
        if len(candidates) == 1:
            return candidates[0].ref
        hint = _hinted_time_dimension(self.obj(metric), metric)
        if hint and any(c.ref == hint for c in candidates):
            return hint
        if not candidates:
            raise Refused(_("The cube of '{ref}' has no time dimension, so a period can't be applied", ref=metric))
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
        """The row count of the metric's cube, used for sample sizes and proportion intervals."""
        cube = SemanticRef.parse(metric).cube
        counts = [o for o in self.catalog.objects
                  if o.kind == "measure" and o.metric_kind == "count" and SemanticRef.parse(o.ref).cube == cube]
        preferred = [o for o in counts if SemanticRef.parse(o.ref).member == "count"]
        pick = preferred or counts
        return pick[0].ref if pick else None

    def units_measure(self, metric: str) -> str | None:
        """What a rate is 'per': its declared count denominator, else the cube's row count."""
        # Declared parts decide: only count/count is a share of units. Ratios of amounts or other
        # sums (value per unit, amount shares) get none, so no interval is
        # attached by coincidence. Undeclared measures fall back to the row count + is_proportion.
        parts = self.obj(metric).ratio_parts
        if parts:
            num, den = (self.obj(p) for p in parts)
            return parts[1] if num.metric_kind == den.metric_kind == "count" else None
        return self.count_measure(metric)


def _hinted_time_dimension(metric: SemanticObject, metric_ref: str) -> str | None:
    """Optional provider hint (e.g. Cube measure meta preAggregation.timeDimension); never required."""
    meta = metric.metadata or {}
    pre = meta.get("preAggregation") or meta.get("pre_aggregation") or {}
    name = pre.get("timeDimension") or pre.get("time_dimension")
    if not name:
        return None
    ref = SemanticRef.parse(metric_ref)
    return str(SemanticRef(provider=ref.provider, instance=ref.instance, cube=ref.cube, member=name.split(".")[-1]))


def previous_period(date_range: tuple[str, str]) -> tuple[str, str]:
    """The period of equal length right before date_range."""
    start, end = (date.fromisoformat(d) for d in date_range)
    days = (end - start).days + 1
    return ((start - timedelta(days=days)).isoformat(), (start - timedelta(days=1)).isoformat())
