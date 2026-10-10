"""A minimal contribution contract, using an isolated registry and no live source."""
import pytest

from decision_layer.core.models import Artifact, DatasetSpec, MethodManifest, ParamSpec, RoleSpec
from decision_layer.methods import InvalidBinding, Method, MethodOutput, MethodRegistry
from decision_layer.validation.builtin import non_empty
from tests.support.semantic import AMOUNT, DT, Q3, ctx


class ExampleMethod(Method):
    manifest = MethodManifest(
        name="example.metric_snapshot", version="1.0.0", kind="query",
        description="Contribution example: read a governed metric without redefining it.",
        roles={"metric": RoleSpec(kind="measure", label="Metric", default_binding="primary_metric")},
        parameters={"limit": ParamSpec(type="integer", default=1, minimum=1, maximum=10)},
        execution="semantic_pushdown", interpretation="descriptive", outputs=["estimate"],
        provides=["metric_lookup"],
    )

    async def run(self, context, bindings, params):
        metric = bindings["metric"]
        dataset = await context.dataset(DatasetSpec(
            grain="aggregate", measures=[metric], time=context.time_scope(metric),
            filters=context.scope.filters, limit_rows=params["limit"]))
        value = dataset.rows[0][0] if dataset.rows else None
        return MethodOutput(
            primary=Artifact(type="estimate", title=context.obj(metric).title, data={"value": value}),
            validation=[non_empty(int(value is not None))],
        )


@pytest.fixture
def contribution_registry():
    registry = MethodRegistry()
    registry.register(ExampleMethod())
    return registry


@pytest.fixture
def provider(cube_meta):
    from tests.support.semantic import FakeProvider
    return FakeProvider(cube_meta)


async def test_contribution_executes_with_provenance(provider, contribution_registry):
    result = await contribution_registry.run("example.metric_snapshot", ctx(provider), {"metric": AMOUNT})
    expected = sum(row["amount"] for row in provider.orders if Q3[0] <= row[DT] <= Q3[1])
    assert result.status == "success" and result.primary.data["value"] == expected
    assert result.provides == ["metric_lookup"]
    assert result.provenance.queries and AMOUNT in result.provenance.semantic_refs


@pytest.mark.parametrize("bindings,params", [({}, {}), ({"metric": AMOUNT}, {"limit": 0}), ({"metric": AMOUNT}, {"code": "print(1)"})])
async def test_contribution_rejects_invalid_contract(provider, contribution_registry, bindings, params):
    with pytest.raises(InvalidBinding):
        await contribution_registry.run("example.metric_snapshot", ctx(provider), bindings, params)
    assert provider.calls == 0


async def test_contribution_empty_result_exposes_no_capability(provider, contribution_registry):
    execute = provider.execute
    async def empty(*args, **kwargs):
        dataset = await execute(*args, **kwargs)
        dataset.rows = []
        return dataset
    provider.execute = empty
    result = await contribution_registry.run("example.metric_snapshot", ctx(provider), {"metric": AMOUNT})
    assert result.status == "refused" and result.provides == []


async def test_contribution_preserves_query_limits(provider, contribution_registry):
    context = ctx(provider)
    context.max_queries = 0
    result = await contribution_registry.run("example.metric_snapshot", context, {"metric": AMOUNT})
    assert result.status == "refused" and provider.calls == 0
