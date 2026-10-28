"""Small installed-by-tests capabilities for engine contracts, never product defaults.

These fixtures exercise querying, selections and parameter metadata independently
of the current agent-driven Skills. They contain no statistical estimators.
"""

from decision_layer.core.models import (
    Artifact,
    DatasetSpec,
    Filter,
    InputSourcePolicy,
    MethodManifest,
    ParamSpec,
    RoleSpec,
    SelectionOutput,
)
from decision_layer.methods import Method, MethodOutput
from decision_layer.methods.common import path_filters
from decision_layer.methods.context import Refused

MAX_GROUPS = 1000
METRIC = RoleSpec(kind="measure", default_binding="primary_metric")
DIMENSIONS = RoleSpec(
    kind="dimension",
    required=False,
    multiple=True,
    default_binding="preferred_dimensions",
    editor_parameter="next_dimension",
)
PATH = ParamSpec(
    type="drill_path",
    default=[],
    meaning="analysis_scope",
    source_policy=InputSourcePolicy(
        allowed=["literal", "input", "step"], default="previous_result", project="path"
    ),
)


class Lookup(Method):
    manifest = MethodManifest(
        kind="query",
        name="test.lookup",
        version="1.0.0",
        description="Test governed read",
        roles={
            "metric": METRIC,
            "related_metrics": RoleSpec(kind="measure", required=False, multiple=True),
            "dimensions": RoleSpec(kind="dimension", required=False, multiple=True),
        },
        parameters={
            "limit": ParamSpec(type="integer", default=100, minimum=1, maximum=1000),
            "order_by": ParamSpec(type="string", semantic_kind="measure"),
            "direction": ParamSpec(type="enum", enum=["asc", "desc"], default="desc"),
        },
        execution="semantic_pushdown",
        interpretation="descriptive",
        outputs=["table", "sample_summary"],
        provides=["metric_lookup"],
    )

    async def run(self, ctx, bindings, params):
        metric = bindings["metric"]
        measures = [metric, *bindings.get("related_metrics", [])]
        if params["order_by"] and params["order_by"] not in measures:
            raise Refused("Sort by a selected metric")
        dataset = await ctx.dataset(
            DatasetSpec(
                grain="aggregate",
                measures=measures,
                dimensions=bindings.get("dimensions", []),
                time=ctx.time_scope(metric),
                filters=ctx.scope.filters,
                order=[(params["order_by"] or metric, params["direction"])],
                limit_rows=params["limit"],
            )
        )
        return MethodOutput(
            primary=Artifact(
                type="table",
                data=[
                    dict(zip([c.ref for c in dataset.columns], row))
                    for row in dataset.rows
                ],
            ),
            artifacts=[
                Artifact(type="sample_summary", data={"population_complete": False})
            ],
        )


class Series(Method):
    manifest = MethodManifest(
        kind="query",
        name="test.series",
        version="1.0.0",
        description="Test scoped series",
        roles={
            "metric": METRIC,
            "related": RoleSpec(kind="measure", required=False, multiple=True),
        },
        requires_period=True,
        parameters={
            "granularity": ParamSpec(
                type="enum", enum=["day", "week", "month"], default="month"
            ),
            "current": ParamSpec(type="date_range", meaning="period"),
            "comparison": ParamSpec(type="date_range", meaning="period"),
            "vs_previous": ParamSpec(type="boolean", default=False),
            "drill_path": PATH,
        },
        execution="semantic_pushdown",
        interpretation="descriptive",
        outputs=["table", "estimate"],
        provides=["time_series"],
    )

    async def run(self, ctx, bindings, params):
        metric = bindings["metric"]
        dataset = await ctx.dataset(
            DatasetSpec(
                grain="aggregate",
                measures=[metric],
                time=ctx.time_scope(
                    metric, params["current"], granularity=params["granularity"]
                ),
                filters=[*ctx.scope.filters, *path_filters(ctx, params["drill_path"])],
                limit_rows=1000,
            )
        )
        from decision_layer.validation.builtin import freshness

        check = await freshness(ctx, metric, ctx.scope.date_range)
        return MethodOutput(
            primary=Artifact(
                type="table",
                data=[
                    dict(zip([c.ref for c in dataset.columns], row))
                    for row in dataset.rows
                ],
            ),
            validation=[check],
        )


class Groups(Method):
    manifest = MethodManifest(
        kind="query",
        name="test.groups",
        version="2.0.0",
        description="Test ranked selection",
        roles={"metric": METRIC, "dimensions": DIMENSIONS},
        parameters={
            "drill_path": PATH,
            "next_dimension": ParamSpec(
                type="string", semantic_kind="dimension", semantic_role="dimensions"
            ),
            "rank_by": ParamSpec(
                type="enum",
                enum=["value", "vs_rest", "count"],
                default="value",
                ui_group="hidden",
            ),
            "direction": ParamSpec(type="enum", enum=["asc", "desc"], default="desc"),
            "top_n": ParamSpec(type="integer", default=10, minimum=1, maximum=1000),
            "min_count": ParamSpec(type="integer", default=30, minimum=0),
            "vs_previous": ParamSpec(type="boolean", default=False),
        },
        execution="semantic_pushdown",
        interpretation="descriptive",
        outputs=["breakdown_table"],
        provides=["group_breakdown"],
        selection_outputs=["ranked_groups"],
    )

    async def run(self, ctx, bindings, params):
        metric, path = bindings["metric"], params["drill_path"]
        dimensions = bindings.get("dimensions", [])
        used = {p["member"] for p in path}
        dimension = params["next_dimension"] or next(
            (d for d in dimensions if d not in used), None
        )
        if dimension is None:
            raise Refused("Select a grouping dimension")
        count = ctx.count_measure(metric)
        ds = await ctx.dataset(
            DatasetSpec(
                grain="aggregate",
                measures=list(dict.fromkeys([metric, *([count] if count else [])])),
                dimensions=[dimension],
                filters=[*ctx.scope.filters, *path_filters(ctx, path)],
                time=ctx.time_scope(metric),
                order=[(metric, params["direction"])],
                limit_rows=MAX_GROUPS,
            )
        )
        refs = [c.ref for c in ds.columns]
        rows = [dict(zip(refs, row)) for row in ds.rows]
        complete = len(rows) < MAX_GROUPS
        rows = [row for row in rows if not count or row[count] >= params["min_count"]]
        rows.sort(key=lambda row: row[metric], reverse=params["direction"] == "desc")
        candidates = [
            {
                "path": [*path, {"member": dimension, "value": r[dimension]}],
                "score": r[metric],
            }
            for r in rows
        ]
        next_candidates = (
            [{"drill_path": c["path"]} for c in candidates]
            if any(d not in used | {dimension} for d in dimensions)
            else []
        )
        return MethodOutput(
            primary=Artifact(
                type="breakdown_table",
                data={
                    "dimension": dimension,
                    "path": path,
                    "rows": [
                        {"value": r[dimension], "metric": r[metric]}
                        for r in rows[: params["top_n"]]
                    ],
                    "next_candidates": next_candidates,
                },
            ),
            selections={
                "ranked_groups": SelectionOutput(
                    complete=complete,
                    rank_by="metric",
                    direction=params["direction"],
                    candidates=candidates,
                )
            },
        )


class Peers(Method):
    manifest = MethodManifest(
        kind="query",
        name="test.peers",
        version="1.0.0",
        description="Test population scope",
        roles={"metric": METRIC},
        parameters={
            "subject": ParamSpec(
                type="drill_path",
                required=True,
                label="Who to compare",
                meaning="comparison_subject",
                source_policy=InputSourcePolicy(
                    allowed=["literal", "input", "step"],
                    default="previous_result",
                    project="condition",
                ),
            ),
            "peers": ParamSpec(
                type="drill_path",
                default=[],
                meaning="comparison_population",
                source_policy=InputSourcePolicy(
                    allowed=["literal", "input", "step"],
                    default="parameter_parents",
                    parameter="subject",
                    project="parents",
                ),
            ),
            "min_count": ParamSpec(type="integer", default=1, minimum=1),
        },
        execution="semantic_pushdown",
        interpretation="descriptive",
        outputs=["table"],
        provides=["peer_comparison"],
    )

    async def run(self, ctx, bindings, params):
        subject = path_filters(ctx, params["subject"])
        peers = path_filters(ctx, params["peers"])
        excluded = [f.model_copy(update={"operator": "notEquals"}) for f in subject]
        rows = []
        for conditions in ([*peers, *subject], [*peers, *excluded], excluded):
            ds = await ctx.dataset(
                DatasetSpec(
                    grain="aggregate",
                    measures=[bindings["metric"]],
                    time=ctx.time_scope(bindings["metric"]),
                    filters=[*ctx.scope.filters, *conditions],
                )
            )
            if not ds.rows:
                raise Refused("Population missing")
            rows.append({"metric": ds.rows[0][0]})
        return MethodOutput(primary=Artifact(type="table", data={"rows": rows}))


class ComparisonContract(Method):
    """Metadata-only fixture for generic alternate-role/default validation."""

    manifest = MethodManifest(
        kind="query",
        name="test.comparison",
        version="1.0.0",
        description="Test contract",
        execution="semantic_pushdown",
        interpretation="descriptive",
        outputs=["table"],
        roles={
            "metric": METRIC,
            "treatment": RoleSpec(
                kind="dimension", required=False, exclusive_group="split"
            ),
            "treatment_measure": RoleSpec(
                kind="measure", required=False, exclusive_group="split"
            ),
            "conditions": RoleSpec(kind="dimension", multiple=True),
            "sample_count": RoleSpec(
                kind="measure", required=False, default_binding="unit_count"
            ),
        },
        parameters={
            "target": ParamSpec(
                type="group", ui_group="basic", semantic_role="treatment"
            ),
            "comparison": ParamSpec(
                type="group", ui_group="basic", semantic_role="treatment"
            ),
            "min_target_retention": ParamSpec(
                type="number", default=0.5, minimum=0, maximum=1
            ),
        },
    )

    async def run(self, ctx, bindings, params):
        raise AssertionError("Metadata-only test fixture")


METHODS = [Lookup(), Series(), Groups(), Peers(), ComparisonContract()]
