"""Small authored examples; production analytics remain in decision_layer.methods."""
from typing import Annotated, Literal
from pydantic import Field
from decision_layer.methods import (
    DateRange, Dimension, Equality, Filter, Measure, Refused, Table, method,
)


#region group_metric
@method("example.group_metric", version="1.0.0")
async def group_metric(ctx, *, metric: Measure, group: Dimension,
                       limit: Annotated[int, Field(ge=1, le=100)] = 5) -> Table:
    """Retrieve the largest governed metric values by a grouping dimension."""
    data = await ctx.aggregate(measures={"metric": metric}, dimensions={"group": group},
                               order=[(metric, "desc")], limit=limit)
    return Table.from_dataset(data, require_non_empty=True,
        warnings=["Top-N results do not establish complete population coverage."])
#endregion group_metric


#region series
@method("example.series", version="2.0.0")
async def series(ctx, *, metric: Measure,
                 granularity: Literal["day", "month"] = "month") -> Table:
    """Retrieve a governed metric by explicit time buckets."""
    data = await ctx.aggregate(measures={"metric": metric}, time_granularity=granularity)
    return Table.from_dataset(data, require_non_empty=True,
        warnings=["Missing buckets are unknown; they are not automatically zero."])
#endregion series


#region period_difference
@method("example.period_difference", version="1.0.0")
async def period_difference(ctx, *, metric: Measure, baseline: DateRange) -> Table:
    """Compare provider-aggregated values in two explicit periods."""
    current = await ctx.aggregate(measures={"metric": metric}, label="current")
    previous = await ctx.aggregate(measures={"metric": metric}, period=baseline,
                                   period_role="comparison", label="baseline")
    a, b = current.scalar("metric"), previous.scalar("metric")
    return Table([{"current": a, "baseline": b, "difference": a - b}],
        warnings=["Raw differences do not adjust unequal period lengths or test significance."])
#endregion period_difference


#region peer
@method("example.peer", version="1.0.0")
async def peer(ctx, *, metric: Measure, subject: Equality, peers: list[Filter]) -> Table:
    """Compare a subject within peer conditions against two excluding benchmarks."""
    if any(item.member == subject.member for item in [*ctx.scope.filters, *peers]):
        raise Refused("Keep the subject dimension out of shared and peer filters")
    excluded = Filter(member=subject.member, operator="notEquals", values=[subject.value])
    a = (await ctx.aggregate(measures={"metric": metric},
         filters=[*peers, subject.as_filter()], label="subject")).scalar("metric")
    b = (await ctx.aggregate(measures={"metric": metric},
         filters=[*peers, excluded], label="peers")).scalar("metric")
    c = (await ctx.aggregate(measures={"metric": metric}, filters=[excluded], label="overall")).scalar("metric")
    return Table([{"population": "peers", "value": b, "difference": a - b},
                  {"population": "overall", "value": c, "difference": a - c}],
        warnings=["Descriptive comparison only; this example does not validate sample counts or significance."])
#endregion peer


AUTHORED = (group_metric, series, period_difference, peer)
