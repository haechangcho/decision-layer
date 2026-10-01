"""query.drilldown — break a metric down by one dimension inside the branch chosen so far.

Multi-level drill-down is a chain of runs: each run
takes `drill_path` (the values picked at earlier levels, applied as equality
filters), breaks the metric down by the next dimension, and returns
`next_candidates` — ready-made drill_paths for the following level. The caller
(user, MCP client or Recipe) picks one; the server never guesses the subject.

Because the reported top group was selected out of N eligible groups, its
comparison to the rest carries `selected_among = N` and a Bonferroni-adjusted
threshold, so the top group is not called significant just for being the max.

With two periods (current and comparison, or vs_previous) it runs in period mode:
each group's values in both periods and its contribution to the change (additive
Δ, or mix/rate for ratios with declared parts), ranked by contribution, plus the
overall change with its test (ADR-032, change.py).
"""
from __future__ import annotations

from typing import Any

from ...core.models import Artifact, MethodManifest, ParamSpec, RoleSpec
from ...validation import builtin as v
from ..base import Method, MethodOutput, registry
from ..context import ExecutionContext, Refused
from ..stats import difference_test, is_proportion
from ...i18n import _
from .change import group_contributions, period_change, periods
from .common import path_filters, rnd, totals

MAX_GROUPS = 5_000
NEXT_CANDIDATES = 3


class Drilldown(Method):
    manifest = MethodManifest(
        name="query.drilldown", version="2.0.0", kind="query",
        description=("Breaks a metric down by one dimension to see which values are high or low. drill_path carries the "
                     "values picked at earlier levels as filters, so calls chain down level by level; pass one of the "
                     "result's next_candidates as the next call's drill_path. With two periods (current and comparison, "
                     "or vs_previous) it shows which groups made the change, and whether the overall change is significant."),
        roles={
            "metric": RoleSpec(kind="measure", description="Metric to break down"),
            "dimensions": RoleSpec(kind="dimension", multiple=True,
                                   description="Dimensions in drill order (upper → lower); ones already in drill_path are skipped"),
        },
        parameters={
            "drill_path": ParamSpec(type="drill_path", default=[],
                                    description="Values picked at earlier levels [{member, value}, …]"),
            "next_dimension": ParamSpec(type="string", description="Dimension for this level (default: the first unused one in dimensions)"),
            "rank_by": ParamSpec(type="enum", enum=["value", "vs_rest", "count"], default="value",
                                 description="Rank by metric value, difference from the rest, or count", ui_group="basic"),
            "direction": ParamSpec(type="enum", enum=["desc", "asc"], default="desc",
                                   description="desc = highest first, asc = lowest first"),
            "top_n": ParamSpec(type="integer", default=10, description="Groups to show", ui_group="basic"),
            "min_count": ParamSpec(type="integer", default=30,
                                   description="Groups below this count are left out of the ranking and next candidates", ui_group="basic"),
            "current": ParamSpec(type="date_range", description="Current period for period mode. Defaults to the scope's period"),
            "comparison": ParamSpec(type="date_range", description="Comparison period (turns on period mode)"),
            "vs_previous": ParamSpec(type="boolean", default=False,
                                     description="Period mode against the equal-length period right before"),
        },
        execution="semantic_pushdown", interpretation="descriptive",
        outputs=["breakdown_table", "estimate", "interval"],
    )

    async def run(self, ctx: ExecutionContext, bindings: dict[str, Any], params: dict[str, Any]) -> MethodOutput:
        metric = bindings["metric"]
        dims = bindings["dimensions"] if isinstance(bindings["dimensions"], list) else [bindings["dimensions"]]
        path = params.get("drill_path") or []
        filters = path_filters(ctx, path)
        used = {step["member"] for step in path}
        dim = params.get("next_dimension") or next((d for d in dims if d not in used), None)
        if dim is None:
            raise Refused(_("No dimension left to drill into (all dimensions are in drill_path)"))
        if ctx.obj(dim).kind not in ("dimension", "time_dimension"):
            raise Refused(_("'{ref}' is not a dimension", ref=dim))
        if dim in used:
            raise Refused(_("'{ref}' is already fixed in drill_path", ref=dim))
        remaining = [d for d in dims if d not in used and d != dim]
        top_n, min_count = int(params["top_n"]), int(params["min_count"])
        compared = periods(ctx, params)
        if compared:
            return await self._periods(ctx, metric, dim, path, filters, remaining, top_n, compared)

        count = ctx.units_measure(metric)
        measures = [metric, *([count] if count and count != metric else [])]
        overall = (await totals(ctx, measures, metric, None, filters) or [{}])[0]
        rows = await totals(ctx, measures, metric, None, filters, dimensions=[dim], limit_rows=MAX_GROUPS)
        total_value, total_n = overall.get(metric), overall.get(count) if count else None
        proportion = is_proportion(total_value, total_n)

        groups = []
        for r in rows:
            value, n = r.get(metric), r.get(count) if count else None
            g = {"value": r.get(dim), "metric": value, "count": n,
                 "share_of_count": round(n / total_n * 100, 2) if n is not None and total_n else None,
                 "vs_overall": None if value is None or total_value is None else round(value - total_value, 4),
                 "eligible": value is not None and (n is None or n >= min_count)}
            rest = _rest(total_value, total_n, value, n) if proportion else None
            if rest is not None:
                g["rest"] = rest
                g["vs_rest"] = round(value - rest["metric"], 4)
            groups.append(g)

        eligible = [g for g in groups if g["eligible"]]
        n_eligible = len(eligible)
        for g in groups:
            if "rest" in g:
                g["test"] = difference_test(g["metric"], g["count"], g["rest"]["metric"], g["rest"]["count"],
                                            selected_among=n_eligible if g["eligible"] else None)
                g["rest"]["metric"] = round(g["rest"]["metric"], 4)
        key = {"value": "metric", "vs_rest": "vs_rest", "count": "count"}[params["rank_by"]]
        if key == "vs_rest" and not proportion:
            key = "vs_overall"
        eligible.sort(key=lambda g: g.get(key) if g.get(key) is not None else float("-inf"),
                      reverse=params["direction"] == "desc")
        small = [g for g in groups if not g["eligible"]]
        for i, g in enumerate(eligible, 1):
            g["rank"] = i
        for g in groups:
            g["metric"] = rnd(g["metric"])

        candidates = [{
            "label": f"{ctx.obj(dim).title} = {g['value']}",
            "drill_path": [*path, {"member": dim, "value": g["value"]}],
            "next_dimension": remaining[0] if remaining else None,
            "metric": g["metric"], "count": g["count"],
        } for g in eligible[:NEXT_CANDIDATES] if remaining]

        artifacts = [Artifact(type="estimate", title=_("this population overall"), data={
            "metric": metric, "value": rnd(total_value), "count": total_n, "drill_path": path})]
        top = eligible[0] if eligible else None
        if top and top.get("test"):
            artifacts.append(Artifact(type="interval", title=_("Top '{value}' vs the rest (pp, 95% CI)", value=top["value"]),
                                      data={"group": top["value"], **top["test"]}))
        warnings = []
        if len(rows) >= MAX_GROUPS:
            warnings.append(_("More than {limit} groups; only part were fetched", limit=MAX_GROUPS))
        if small:
            warnings.append(_("{groups} groups below {minimum} were left out of the ranking", groups=len(small), minimum=min_count))
        if not proportion:
            warnings.append(_("Not a count-based proportion, so no interval against the rest was computed"))

        return MethodOutput(
            primary=Artifact(type="breakdown_table", title=f"{ctx.obj(metric).title} by {ctx.obj(dim).title}", data={
                "metric": metric, "dimension": dim, "drill_path": path,
                "rank_by": key, "direction": params["direction"], "selected_among": n_eligible,
                "rows": eligible[:top_n], "excluded_small": len(small),
                "next_dimension": remaining[0] if remaining else None, "next_candidates": candidates,
            }),
            artifacts=artifacts, warnings=warnings,
            validation=[v.non_empty(len(rows), _("groups")),
                        v.complete_period(ctx.scope.date_range),
                        *([v.min_sample(total_n, min_count, _("sample in this population"))] if count else []),
                        await v.freshness(ctx, metric, ctx.scope.date_range)],
        )


    async def _periods(self, ctx, metric, dim, path, filters, remaining, top_n, compared) -> MethodOutput:
        current, comparison = compared
        summary, validation = await period_change(ctx, metric, current, comparison, filters)
        rows, kind = await group_contributions(ctx, metric, dim, current, comparison, filters, MAX_GROUPS)
        key = "contribution" if kind else "change"
        rows.sort(key=lambda r: abs(r.get(key) or 0), reverse=True)
        candidates = [{
            "label": f"{ctx.obj(dim).title} = {r['value']}",
            "drill_path": [*path, {"member": dim, "value": r["value"]}],
            "next_dimension": remaining[0] if remaining else None, key: r.get(key),
        } for r in rows[:NEXT_CANDIDATES] if remaining]
        warnings = [] if kind else [_("'{title}' has no declared numerator and denominator, so group changes are "
                                      "shown without splitting the overall change", title=ctx.obj(metric).title)]
        return MethodOutput(
            primary=Artifact(type="contribution_table", title=_("Contribution to the change of {metric} by {dimension}",
                                                                 metric=ctx.obj(metric).title, dimension=ctx.obj(dim).title),
                             data={"metric": metric, "dimension": dim, "drill_path": path, "decomposition": kind,
                                   "current_period": list(current), "comparison_period": list(comparison),
                                   "rows": rows[:top_n], "groups": len(rows),
                                   # what the hidden groups add, so shown rows + this = the whole change
                                   "other_contribution": rnd(sum(r.get(key) or 0 for r in rows[top_n:])) if kind else None,
                                   "next_dimension": remaining[0] if remaining else None,
                                   "next_candidates": candidates}),
            artifacts=[Artifact(type="estimate", title=_("change between the periods"), data=summary)],
            warnings=warnings,
            validation=[v.non_empty(len(rows), _("groups")), *validation,
                        await v.freshness(ctx, metric, current)],
        )


def _rest(total: float | None, total_n: float | None, value: float | None, n: float | None) -> dict | None:
    """Everything outside the group, from overall and group event counts (proportions only)."""
    if None in (total, total_n, value, n) or total_n - n <= 0:
        return None
    events = total * total_n / 100 - value * n / 100
    rest_n = total_n - n
    return {"metric": events / rest_n * 100, "count": rest_n}


registry.register(Drilldown())
