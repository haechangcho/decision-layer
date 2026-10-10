"""query.trend — a metric and related measures over time, side by side.

Returns the series (value and unit count per period for each metric) and each
series' largest period-over-period move. When two periods are given (current and
comparison, or vs_previous) it also returns the change between them with the
server-side judgements ADR-032 requires: the test of the difference, the per-day
comparison for unequal periods, and the factor decomposition (change.py).
Co-movement over time is descriptive; it does not show that measures are related.
"""
from __future__ import annotations

from typing import Any

from ...core.models import Artifact, DatasetSpec, InputSourcePolicy, MethodManifest, ParamSpec, RoleSpec
from ...i18n import _
from ...validation import builtin as v
from ..base import Method, MethodOutput, registry
from ..context import ExecutionContext, Refused
from .change import period_change, periods
from .common import analysis_period, path_filters, rnd

MAX_PERIODS = 400


class Trend(Method):
    manifest = MethodManifest(
        name="query.trend", version="1.0.0", kind="query", label="Change over time",
        description=("Shows a metric and related measures over time (per day, week or month) side by side. With "
                     "two periods (current and comparison, or vs_previous) it also reports the change between them: "
                     "whether it is significant, the per-day comparison when the periods differ in length, and the "
                     "factor decomposition of a total. Descriptive: moving together over time does not show that "
                     "measures are related."),
        roles={
            "metric": RoleSpec(kind="measure", label="Analysis metric", default_binding="primary_metric", description="Metric to follow over time (its date decides the periods)"),
            "related": RoleSpec(kind="measure", multiple=True, required=False, description="Measures to show alongside"),
        },
        parameters={
            "granularity": ParamSpec(type="enum", enum=["day", "week", "month", "quarter"], default="month",
                                     label="Time unit", description="Time unit of the series", ui_group="basic"),
            "current": ParamSpec(type="date_range", label="Fixed analysis period", meaning="period", ui_group="hidden", description="Current period for the change. Defaults to the scope's period"),
            "comparison": ParamSpec(type="date_range", label="Fixed comparison period", meaning="period", ui_group="hidden", description="Comparison period for the change"),
            "vs_previous": ParamSpec(type="boolean", default=False,
                                     label="Compare with previous period", meaning="period", description="Compare with the equal-length period right before", ui_group="options"),
            "drill_path": ParamSpec(type="drill_path", default=[], label="Analysis scope", meaning="analysis_scope", ui_group="hidden",
                                    source_policy=InputSourcePolicy(allowed=["literal", "input", "step"], default="previous_result", project="path"), description="[{member, value}] narrows the population (optional)"),
        },
        execution="semantic_pushdown", interpretation="descriptive", requires_period=True,
        outputs=["time_series", "estimate", "interval"],
        provides=["time_series", "period_change"],
        provides_when={"period_change": ["comparison", "vs_previous"]},
    )

    async def run(self, ctx: ExecutionContext, bindings: dict[str, Any], params: dict[str, Any]) -> MethodOutput:
        metric = bindings["metric"]
        related = bindings.get("related") or []
        related = related if isinstance(related, list) else [related]
        filters = path_filters(ctx, params.get("drill_path"))
        compared = periods(ctx, params)
        if compared:  # the series spans both periods
            span = (min(p[0] for p in compared), max(p[1] for p in compared))
        elif analysis_period(ctx, params):
            span = analysis_period(ctx, params)
        else:
            raise Refused(_("A period is needed (scope.date_range)"))

        metrics = list(dict.fromkeys([metric, *related]))
        units = {m: ctx.units_measure(m) for m in metrics}
        measures = list(dict.fromkeys([*metrics, *(u for u in units.values() if u)]))
        time = ctx.time_scope(metric, span, granularity=params["granularity"])
        ds = await ctx.dataset(DatasetSpec(
            grain="aggregate", measures=measures, time=time, order=[(time.dimension, "asc")],
            filters=[*ctx.scope.filters, *filters], limit_rows=MAX_PERIODS))
        refs = [c.ref for c in ds.columns]
        series = []
        for r in (dict(zip(refs, row)) for row in ds.rows):
            item = {"period": str(r.get(time.dimension))[:10]}
            for m in metrics:
                item[m] = rnd(r.get(m))
                if units[m] and units[m] != m:
                    item[f"{m}#units"] = r.get(units[m])
            series.append(item)
        moves = []
        for m in metrics:
            pairs = [(a["period"], b["period"], a[m], b[m]) for a, b in zip(series, series[1:])
                     if a[m] is not None and b[m] is not None]
            if pairs:
                p0, p1, x0, x1 = max(pairs, key=lambda p: abs(p[3] - p[2]))
                moves.append({"metric": m, "title": ctx.obj(m).title, "from": p0, "to": p1,
                              "before": x0, "after": x1, "change": rnd(x1 - x0)})

        artifacts = [Artifact(type="table", title=_("largest period-over-period move per series"), data=moves)]
        validation = [v.non_empty(len(series), _("periods"))]
        if compared:
            summary, checks = await period_change(ctx, metric, *compared, filters, related)
            artifacts.insert(0, Artifact(type="estimate", title=_("change between the periods"), data=summary))
            validation += checks
        else:
            validation.append(v.complete_period(span))
        validation.append(await v.freshness(ctx, metric, compared[0] if compared else span, filters=filters))
        return MethodOutput(
            primary=Artifact(type="time_series", title=_("{metric} over time", metric=ctx.obj(metric).title), data={
                "metric": metric, "related": related, "granularity": params["granularity"],
                "analysis_period": {"date_range": list(span), "source": "method_parameters" if params.get("current") or compared else "run_scope"},
                "units": {m: u for m, u in units.items() if u and u != m}, "rows": series}),
            artifacts=artifacts,
            warnings=[_("Moving together over time does not show that the measures are related.")] if related else [],
            validation=validation,
            provides=["time_series", "period_change"] if compared else ["time_series"],
        )


registry.register(Trend())
