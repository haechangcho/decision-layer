"""Helpers shared by the query Methods."""
from __future__ import annotations

from typing import Any

from ...core.models import DatasetSpec, Filter
from ...validation.builtin import period_days
from ..context import ExecutionContext, Refused
from ..stats import pct_change
from ...i18n import _


def parse_range(value: Any, name: str) -> tuple[str, str] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, str) for v in value):
        return (value[0], value[1])
    raise Refused(_("{name} must be ['YYYY-MM-DD', 'YYYY-MM-DD']", name=name))


def path_filters(ctx: ExecutionContext, drill_path: list[dict[str, Any]] | None) -> list[Filter]:
    """drill_path = [{member: ref, value: v}, …] → equality filters (the branch chosen so far)."""
    out = []
    for step in drill_path or []:
        if not isinstance(step, dict) or "member" not in step or "value" not in step:
            raise Refused(_("drill_path items must be {{member, value}}"))
        ctx.obj(step["member"])
        out.append(Filter(member=step["member"], operator="equals", values=[step["value"]]))
    return out


async def totals(ctx: ExecutionContext, measures: list[str], metric: str,
                 date_range: tuple[str, str] | None, filters: list[Filter],
                 dimensions: list[str] | None = None, limit_rows: int | None = None) -> list[dict[str, Any]]:
    """Aggregate query → list of {ref: value} rows (one row when no dimensions)."""
    spec = DatasetSpec(grain="aggregate", measures=list(dict.fromkeys(measures)), dimensions=dimensions or [],
                       time=ctx.time_scope(metric, date_range), filters=[*ctx.scope.filters, *filters],
                       limit_rows=limit_rows)
    ds = await ctx.dataset(spec)
    refs = [c.ref for c in ds.columns]
    return [dict(zip(refs, row)) for row in ds.rows]


def rnd(x: Any, digits: int = 4) -> Any:
    """Round floats for display; statistics are always computed on the unrounded values."""
    return round(x, digits) if isinstance(x, float) else x


def per_day(kind, a, b, current, comparison) -> dict:
    """Additive/count totals of unequal periods are compared per day as well."""
    days_a, days_b = period_days(current), period_days(comparison)
    if kind not in ("additive", "count") or days_a == days_b or a is None or b is None:
        return {}
    pa, pb = a / days_a, b / days_b
    return {"per_day": {"current": rnd(pa), "comparison": rnd(pb), "change_pct": pct_change(pa, pb),
                        "current_days": days_a, "comparison_days": days_b}}
