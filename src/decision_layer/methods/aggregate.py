"""Governed aggregate retrieval through the same Method and Run contracts."""
from ..core.models import Artifact, DatasetSpec, MethodManifest, ParamSpec, RoleSpec
from .base import Method, MethodOutput
from .context import Refused
from .common import path_filters


class Aggregate(Method):
    manifest = MethodManifest(
        name="query.aggregate", version="1.0.0", kind="query", label="Metric lookup",
        description="Retrieve existing metrics by dimensions without statistical or causal judgement.",
        roles={
            "metric": RoleSpec(kind="measure", label="Analysis metric", default_binding="primary_metric"),
            "related_metrics": RoleSpec(kind="measure", required=False, multiple=True, label="Related metrics"),
            "dimensions": RoleSpec(kind="dimension", required=False, multiple=True, label="Group by"),
        },
        parameters={
            "limit": ParamSpec(type="integer", default=100, minimum=1, maximum=1000, label="Result rows"),
            "direction": ParamSpec(type="enum", enum=["asc", "desc"], default="desc", label="Sort direction"),
            "order_by": ParamSpec(type="string", semantic_kind="measure", label="Sort metric"),
            "with_sql": ParamSpec(type="boolean", default=False, label="Include compiled query", ui_group="hidden"),
            "granularity": ParamSpec(type="enum", enum=["day", "week", "month", "quarter", "year"], label="Time unit"),
            "drill_path": ParamSpec(type="drill_path", default=[], label="Selected groups"),
        },
        execution="semantic_pushdown", interpretation="descriptive", outputs=["table", "sample_summary"], provides=["metric_lookup"],
    )

    async def run(self, ctx, bindings, params):
        metric = bindings["metric"]
        if not ctx.provider.capabilities().aggregate_queries:
            raise Refused("The connected semantic layer does not support aggregate queries.")
        spec = DatasetSpec(
            grain="aggregate", measures=list(dict.fromkeys([metric, *bindings.get("related_metrics", [])])),
            dimensions=bindings.get("dimensions", []), time=ctx.time_scope(metric, granularity=params["granularity"]),
            filters=[*ctx.scope.filters, *path_filters(ctx, params["drill_path"])],
            order=[(params["order_by"] or metric, params["direction"])], limit_rows=params["limit"],
        )
        if params["order_by"] and params["order_by"] not in spec.measures:
            raise Refused("Sort by a selected metric.")
        dataset = await ctx.dataset(spec, with_sql=params["with_sql"])
        return MethodOutput(primary=Artifact(type="table", title=ctx.obj(metric).title,
            data=[dict(zip([column.ref for column in dataset.columns], row)) for row in dataset.rows]),
            artifacts=[Artifact(type="sample_summary", data={"returned_rows": len(dataset.rows),
                "requested_limit": params["limit"], "population_complete": False,
                "selection_supported": False, "statistical_judgement": "not_tested",
                "columns": [column.model_dump(mode="json") for column in dataset.columns]})])
