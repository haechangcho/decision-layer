"""Judgements about a change between two periods, shared by trend and drilldown (ADR-032).

The experiment behind ADR-032 showed a client explaining noise when the server
only returned raw values, so every two-period result carries:

- the overall change with its test (count proportions only, see stats.py),
- a per-day comparison when the periods differ in length (totals and counts),
- for totals whose ratios are declared (ADR-022), the multiplicative factor
  decomposition (LMDI-I): L = (Y1 − Y0) / ln(Y1/Y0), contribution_f = L · ln(f1/f0),
  which adds up exactly to Y1 − Y0; unequal periods get a 'period days' factor.
- group contributions for drilldown: additive Δ, or mix/rate for ratios with parts
      ΔR = Σ (s1_g − s0_g)(r0_g − R0)  +  Σ s1_g (r1_g − r0_g)
"""
from __future__ import annotations

import math
from typing import Any

from ..core.models import Filter, ValidationResult
from ..i18n import _
from ..validation import builtin as v
from .context import ExecutionContext, Refused, previous_period
from .stats import difference_test, pct_change, safe_div
from .common import analysis_period, parse_range, per_day, rnd, totals

MAX_CHAINS = 6
MAX_DEPTH = 4
SCALE_TOLERANCE = 1e-6
DAYS = "period_days"


def periods(ctx: ExecutionContext, params: dict[str, Any]) -> tuple[tuple[str, str], tuple[str, str]] | None:
    """(current, comparison) when the call compares periods, else None."""
    comparison = parse_range(params.get("comparison"), "comparison")
    if comparison is None and not params.get("vs_previous"):
        return None
    current = analysis_period(ctx, params)
    if not current:
        raise Refused(_("A current period is needed (current or scope.date_range)"))
    return current, comparison or previous_period(current)


async def period_change(ctx: ExecutionContext, metric: str, current: tuple[str, str], comparison: tuple[str, str],
                        filters: list[Filter], related: list[str] = ()) -> tuple[dict[str, Any], list[ValidationResult]]:
    """Overall change of metric (and related measures) between the periods, with its judgements."""
    metrics = list(dict.fromkeys([metric, *related]))
    units = {m: ctx.units_measure(m) for m in metrics}
    chains = factor_chains(ctx, metric) if ctx.obj(metric).metric_kind in ("additive", "count") else []
    chains = chains[:MAX_CHAINS]
    measures = list(dict.fromkeys([*metrics, *(u for u in units.values() if u),
                                   *(m for c in chains for m in c["measures"])]))
    now = (await totals(ctx, measures, metric, current, filters) or [{}])[0]
    before = (await totals(ctx, measures, metric, comparison, filters) or [{}])[0]

    def one(m: str) -> dict[str, Any]:
        a, b, u = now.get(m), before.get(m), units[m]
        out = {"metric": m, "title": ctx.obj(m).title, "current": rnd(a), "comparison": rnd(b),
               "change": None if a is None or b is None else rnd(a - b), "change_pct": pct_change(a, b),
               **per_day(ctx.obj(m).metric_kind, a, b, current, comparison)}
        if u and u != m:
            out["units"] = {"current": now.get(u), "comparison": before.get(u)}
        test = difference_test(a, now.get(u), b, before.get(u)) if u else None
        if test:
            out["test"] = test
        return out

    summary = {"current_period": list(current), "comparison_period": list(comparison), **one(metric)}
    if related:
        summary["related"] = [one(m) for m in metrics[1:]]
    if chains:
        decomposition = _decompose(ctx, metric, chains, now, before, current, comparison)
        if decomposition:
            summary["decomposition"] = decomposition
    n_a = summary.get("units", {}).get("current")
    n_b = summary.get("units", {}).get("comparison")
    validation = [v.non_empty(int(now.get(metric) is not None) + int(before.get(metric) is not None),
                              _("compared values")),
                  v.complete_period(current), v.comparable_periods(current, comparison),
                  *([v.min_sample(n_a, 30, _("current sample")), v.min_sample(n_b, 30, _("comparison sample"))]
                    if units[metric] else [])]
    return summary, validation


# ── factor decomposition ─────────────────────────────────────────────────
def factor_chains(ctx: ExecutionContext, metric: str, depth: int = 0) -> list[dict[str, Any]]:
    """metric = base × r1 × r2 … from declared ratio parts, ordered from the base outwards."""
    if depth >= MAX_DEPTH:
        return []
    out = []
    for o in ctx.catalog.objects:
        if o.kind != "measure" or not o.ratio_parts or o.ratio_parts[0] != metric or o.ratio_parts[1] == metric:
            continue
        den = o.ratio_parts[1]
        for sub in [{"ratios": [], "base": den}, *factor_chains(ctx, den, depth + 1)]:
            ratios = [*sub["ratios"], (o.ref, metric)]
            base = sub["base"]
            out.append({"ratios": ratios, "base": base, "measures": [base, *(r for r, _m in ratios)],
                        "label": " × ".join(ctx.obj(m).title for m in [base, *(r for r, _m in ratios)])})
    return out


def _decompose(ctx, metric, chains, now, before, current, comparison) -> dict[str, Any] | None:
    y1, y0 = now.get(metric), before.get(metric)
    if not y1 or not y0 or y1 <= 0 or y0 <= 0:
        return None
    days1, days0 = v.period_days(current), v.period_days(comparison)
    L = (y1 - y0) / math.log(y1 / y0) if y1 != y0 else y1
    results, skipped = [], []
    for chain in chains:
        rows = _chain_rows(ctx, chain, now, before, days1, days0)
        if rows is None:
            skipped.append(chain["label"])
            continue
        for r in rows:
            r["contribution"] = rnd(L * math.log(r.pop("_ratio")))
            r["share_of_change"] = round(r["contribution"] / (y1 - y0) * 100, 2) if y1 != y0 else None
        results.append({"formula": chain["label"] + (_(" (period days split out)") if days1 != days0 else ""),
                        "factors": rows})
    if not results:
        return None
    out = {"method": _("LMDI (factor contributions add up to the change)"), "decompositions": results}
    if skipped:
        out["skipped"] = [_("{formula}: the product of the factors doesn't match the metric (unit or scale), "
                            "so it was left out", formula=f) for f in skipped]
    return out


def _chain_rows(ctx, chain, now, before, days1, days0) -> list[dict[str, Any]] | None:
    values = {m: (now.get(m), before.get(m)) for m in chain["measures"]}
    if any(a is None or b is None or a <= 0 or b <= 0 for a, b in values.values()):
        return None
    # a ratio measure may carry a constant factor (e.g. ×100 for %): it must be the same in both periods
    metric = chain["ratios"][-1][1]
    s1 = now[metric] / math.prod(a for a, _b in values.values())
    s0 = before[metric] / math.prod(b for _a, b in values.values())
    if abs(s1 / s0 - 1) > SCALE_TOLERANCE:
        return None
    rows = []
    for m in [chain["base"], *(r for r, _m in chain["ratios"])]:
        a, b = values[m]
        if m == chain["base"] and days1 != days0:
            rows.append(_row(DAYS, _("period days"), days1, days0))
            rows.append(_row(m, _("{title} (per day)", title=ctx.obj(m).title), a / days1, b / days0))
        else:
            rows.append(_row(m, ctx.obj(m).title, a, b))
    return rows


def _row(ref: str, title: str, a: float, b: float) -> dict[str, Any]:
    return {"factor": ref, "title": title, "current": rnd(a), "comparison": rnd(b),
            "change_pct": pct_change(a, b), "_ratio": a / b}


# ── group contributions (drilldown period mode) ────────────────────────────
async def group_contributions(ctx: ExecutionContext, metric: str, dim: str, current, comparison,
                              filters: list[Filter], max_groups: int) -> tuple[list[dict[str, Any]], str | None]:
    """Per-group values in both periods and each group's contribution to the change.
    Returns (rows, decomposition kind): 'additive', 'mix_rate', or None (values only)."""
    obj = ctx.obj(metric)
    if obj.metric_kind in ("additive", "count"):
        return await _additive(ctx, metric, dim, current, comparison, filters, max_groups), "additive"
    if obj.metric_kind == "ratio" and obj.ratio_parts:
        rows = await _mix_rate(ctx, metric, obj.ratio_parts, dim, current, comparison, filters, max_groups)
        if rows is not None:
            return rows, "mix_rate"
    now = {r[dim]: r.get(metric) for r in await totals(ctx, [metric], metric, current, filters, [dim], max_groups)}
    before = {r[dim]: r.get(metric) for r in await totals(ctx, [metric], metric, comparison, filters, [dim], max_groups)}
    return [{"value": g, "current": rnd(now.get(g)), "comparison": rnd(before.get(g)),
             "change": None if now.get(g) is None or before.get(g) is None else rnd(now[g] - before[g])}
            for g in now.keys() | before.keys()], None


async def _additive(ctx, metric, dim, current, comparison, filters, max_groups):
    v1 = {r[dim]: r.get(metric) or 0 for r in await totals(ctx, [metric], metric, current, filters, [dim], max_groups)}
    v0 = {r[dim]: r.get(metric) or 0 for r in await totals(ctx, [metric], metric, comparison, filters, [dim], max_groups)}
    total = sum(v1.values()) - sum(v0.values())
    return [{"value": g, "current": rnd(v1.get(g, 0)), "comparison": rnd(v0.get(g, 0)),
             "contribution": rnd(v1.get(g, 0) - v0.get(g, 0)),
             "share_of_change": round((v1.get(g, 0) - v0.get(g, 0)) / total * 100, 2) if total else None}
            for g in v1.keys() | v0.keys()]


async def _mix_rate(ctx, metric, parts, dim, current, comparison, filters, max_groups):
    num, den = parts
    over1 = (await totals(ctx, [metric, num, den], metric, current, filters) or [{}])[0]
    over0 = (await totals(ctx, [metric, num, den], metric, comparison, filters) or [{}])[0]
    g1 = {r[dim]: r for r in await totals(ctx, [num, den], metric, current, filters, [dim], max_groups)}
    g0 = {r[dim]: r for r in await totals(ctx, [num, den], metric, comparison, filters, [dim], max_groups)}
    # the metric may be scaled (e.g. ×100 for %): recover the factor from the overall value
    scale = safe_div(over0.get(metric), safe_div(over0.get(num), over0.get(den))) \
        or safe_div(over1.get(metric), safe_div(over1.get(num), over1.get(den)))
    d1 = sum((r.get(den) or 0) for r in g1.values())
    d0 = sum((r.get(den) or 0) for r in g0.values())
    if not scale or not d0 or not d1:
        return None
    scale = round(scale, 6)
    R0 = scale * sum((r.get(num) or 0) for r in g0.values()) / d0
    R1 = scale * sum((r.get(num) or 0) for r in g1.values()) / d1
    rows = []
    for g in g1.keys() | g0.keys():
        a, b = g1.get(g, {}), g0.get(g, {})
        s1, s0 = (a.get(den) or 0) / d1, (b.get(den) or 0) / d0
        r1 = scale * a[num] / a[den] if a.get(den) and a.get(num) is not None else None
        r0 = scale * b[num] / b[den] if b.get(den) and b.get(num) is not None else None
        base = r0 if r0 is not None else R0          # a new group starts from the overall rate
        mix = (s1 - s0) * (base - R0)
        rate = s1 * ((r1 if r1 is not None else base) - base)
        rows.append({"value": g, "current": rnd(r1), "comparison": rnd(r0),
                     "share_current": round(s1 * 100, 2), "share_comparison": round(s0 * 100, 2),
                     "mix_effect": rnd(mix), "rate_effect": rnd(rate), "contribution": rnd(mix + rate),
                     "share_of_change": round((mix + rate) / (R1 - R0) * 100, 2) if R1 != R0 else None})
    return rows
