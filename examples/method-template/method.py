"""Minimal runnable contribution example; not registered in the production server."""
from decision_layer.core.models import Artifact, DatasetSpec, MethodManifest, RoleSpec
from decision_layer.methods.base import Method, MethodOutput
from decision_layer.validation.builtin import non_empty


class MetricSnapshot(Method):
    manifest = MethodManifest(
        name="example.metric_snapshot", version="1.0.0", kind="query",
        description="Read one governed metric in the supplied period and population.",
        roles={"metric": RoleSpec(kind="measure", description="Governed metric")},
        execution="semantic_pushdown", interpretation="descriptive", outputs=["estimate"],
    )

    async def run(self, ctx, bindings, params):
        metric = bindings["metric"]
        dataset = await ctx.dataset(DatasetSpec(
            grain="aggregate", measures=[metric], time=ctx.time_scope(metric), filters=ctx.scope.filters))
        value = dataset.rows[0][0] if dataset.rows else None
        return MethodOutput(
            primary=Artifact(type="estimate", title=ctx.obj(metric).title, data={"value": value}),
            validation=[non_empty(int(value is not None))],
        )
