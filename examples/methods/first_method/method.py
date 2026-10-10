"""Example implementation imported by the notebook; edit this Python module."""
from decision_layer.methods import Artifact, DatasetSpec, MethodManifest, ParamSpec, RoleSpec
from decision_layer.methods import Method, MethodOutput
from decision_layer.methods import Refused
from decision_layer.validation.builtin import non_empty


class GroupMetric(Method):
    manifest = MethodManifest(
        name="example.group_metric", version="1.0.0", kind="query",
        label="Metric by group",
        description="Retrieve the largest metric values by a selected dimension.",
        roles={
            "metric": RoleSpec(kind="measure", description="Existing governed metric"),
            "dimension": RoleSpec(kind="dimension", description="Grouping dimension"),
        },
        parameters={
            "limit": ParamSpec(type="integer", default=5, minimum=1, maximum=100),
        },
        execution="semantic_pushdown", interpretation="descriptive",
        outputs=["table"], provides=["group_metric_lookup"],
    )

    async def run(self, ctx, bindings, params):
        if not ctx.provider.capabilities().aggregate_queries:
            raise Refused("The provider does not support aggregate queries.")

        # 이 줄 앞뒤에 breakpoint()를 두고 직접 실행 셀에서 확인할 수 있습니다.
        dataset = await ctx.dataset(DatasetSpec(
            grain="aggregate",
            measures=[bindings["metric"]],
            dimensions=[bindings["dimension"]],
            time=ctx.time_scope(bindings["metric"]),
            filters=ctx.scope.filters,
            order=[(bindings["metric"], "desc")],
            limit_rows=params["limit"],
        ), with_sql=ctx.provider.capabilities().compiled_sql)

        columns = [column.ref for column in dataset.columns]
        rows = [dict(zip(columns, row)) for row in dataset.rows]
        return MethodOutput(
            primary=Artifact(type="table", title="Metric by group", data=rows),
            validation=[non_empty(len(rows))],
            warnings=["Top-N lookup only; it does not establish complete population coverage."],
        )
