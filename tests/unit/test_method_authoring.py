"""Contributor-facing calls still exercise the ordinary registry and provider boundary."""
from typing import Annotated, Literal
from dataclasses import replace
from pydantic import Field
import pytest

from decision_layer.dev import MethodSession
from decision_layer.methods import (
    DateRange, Dimension, Entity, Equality, Estimate, Filter,
    InvalidBinding, Measure, Refused, Scope, Table, TimeSeries, method,
)
from decision_layer.core.models import DatasetSpec, SemanticCatalog, SemanticObject, TimeScope
from decision_layer.core.periods import ExecutionPolicy
from decision_layer.testing import FixtureProvider, QueryFixture
from examples.methods.first_method.fixtures import METRIC, DIMENSION, DATE, DATES, fixture_provider


@method("example.authored", version="1.0.0", interpretation="association")
async def grouped(ctx, *, metric: Measure, group: Dimension,
                  limit: Annotated[int, Field(ge=1, le=100)] = 5) -> Table:
    """Retrieve a metric by a governed grouping dimension."""
    data = await ctx.aggregate(measures={"metric": metric}, dimensions={"group": group},
                               order=[(metric, "desc")], limit=limit)
    return Table.from_dataset(data, require_non_empty=True)


async def test_signature_generates_contract_and_three_call_styles():
    assert grouped.manifest.roles["metric"].kind == "measure"
    assert grouped.manifest.parameters["limit"].minimum == 1
    assert grouped.manifest.parameters["limit"].default == 5
    for arguments in [
        {"measures": {"metric": METRIC}, "dimensions": {"group": DIMENSION}, "params": {"limit": 3}},
        {"bindings": {"metric": METRIC, "group": DIMENSION}, "params": {"limit": 3}},
        {"metric": METRIC, "group": DIMENSION, "limit": 3},
    ]:
        provider = fixture_provider()
        session = await MethodSession.fixture(provider)
        session.register(grouped)
        trial = await session.run(grouped, scope=Scope(DATES, DATE), **arguments)
        assert trial.result.status == "success"
        assert trial.result.interpretation == "association"
        assert trial.result.primary.data == [{"metric": 30, "group": "A"}, {"metric": 20, "group": "B"}, {"metric": 10, "group": "C"}]
        assert trial.attempts[0].spec.time.date_range == DATES
        provider.assert_consumed()


@pytest.mark.parametrize("arguments", [
    {"measures": {"group": METRIC}, "dimensions": {"group": DIMENSION}},
    {"metric": METRIC, "group": DIMENSION, "limit": 0},
    {"metric": METRIC, "group": DIMENSION, "limit": True},
    {"metric": METRIC, "group": DIMENSION, "unknown": 3},
    {"bindings": {"metric": METRIC}, "measures": {"metric": METRIC}},
])
async def test_invalid_inputs_issue_no_queries(arguments):
    provider = fixture_provider()
    session = await MethodSession.fixture(provider)
    session.register(grouped)
    with pytest.raises(InvalidBinding):
        await session.run(grouped, scope=Scope(DATES, DATE), **arguments)
    assert not provider.calls


def test_registration_rejects_unsupported_contracts_and_bad_defaults():
    with pytest.raises(ValueError, match="annotation"):
        @method("example.bad", version="1.0.0", interpretation="descriptive")
        async def wrong(ctx, *, config: dict) -> Table:
            return Table([])
    @method("example.bad_default", version="1.0.0", interpretation="descriptive")
    async def bad_default(ctx, *, limit: Annotated[int, Field(ge=1)] = 0) -> Table:
        return Table([])
    from decision_layer.methods import MethodRegistry
    with pytest.raises(InvalidBinding):
        MethodRegistry().register(bad_default)


async def test_shared_filters_labels_and_comparison_periods():
    @method("example.filtered", version="1.0.0", interpretation="descriptive")
    async def filtered(ctx, *, metric: Measure, baseline: DateRange) -> Table:
        await ctx.aggregate(measures={"metric": metric}, label="current")
        data = await ctx.aggregate(measures={"metric": metric}, period=baseline,
                                   period_role="comparison", label="baseline")
        return Table.from_dataset(data)
    base = fixture_provider()
    condition = Filter(member=DIMENSION, operator="equals", values=["A"])
    current = DatasetSpec(grain="aggregate", measures=[METRIC], filters=[condition],
        time=TimeScope(dimension=DATE, date_range=DATES), limit_rows=50001)
    baseline = current.model_copy(update={"time": TimeScope(dimension=DATE, date_range=("2026-08-01", "2026-08-31"))})
    provider = FixtureProvider(base.catalog, [QueryFixture(current, [[12]]), QueryFixture(baseline, [[10]])])
    session = await MethodSession.fixture(provider)
    session.register(filtered)
    trial = await session.run(filtered, measures={"metric": METRIC}, filters=[condition], scope=Scope(DATES, DATE),
                               params={"baseline": ("2026-08-01", "2026-08-31")})
    assert [attempt.label for attempt in trial.attempts] == ["current", "baseline"]
    provider.assert_consumed()


async def test_current_period_expansion_and_entity_ref_are_refused():
    @method("example.expand", version="1.0.0", interpretation="descriptive")
    async def expand(ctx, *, metric: Measure) -> Table:
        data = await ctx.aggregate(measures={"metric": metric}, period=("2026-08-01", "2026-09-30"))
        return Table.from_dataset(data)
    provider = fixture_provider()
    session = await MethodSession.fixture(provider)
    session.register(expand)
    trial = await session.run(expand, measures={"metric": METRIC}, scope=Scope(DATES, DATE))
    assert trial.result.status == "refused" and not provider.calls


async def test_missing_dependency_refuses_before_queries():
    @method("example.optional", version="1.0.0", interpretation="descriptive",
            requires_packages={"decision-layer-nonexistent-test-package": ">=1"})
    async def optional(ctx, *, metric: Measure) -> Table:
        return Table.from_dataset(await ctx.aggregate(measures={"metric": metric}))
    provider = fixture_provider()
    session = await MethodSession.fixture(provider)
    session.register(optional)
    result = (await session.run(optional, measures={"metric": METRIC}, scope=Scope(DATES, DATE))).result
    assert result.status == "refused" and not provider.calls
    assert "Optional dependency" in result.warnings[0]


async def test_catalog_unknown_relations_do_not_claim_compatibility():
    session = await MethodSession.fixture(fixture_provider())
    assert session.catalog.search(kind="metric", text="Revenue")[0].ref == METRIC
    assert session.catalog.require(DIMENSION).kind == "dimension"
    assert all(item["compatibility"] == "declared" for item in session.catalog.relations(METRIC))
    session.catalog.objects[0].dimension_refs = []
    assert all(item["compatibility"] == "unknown" for item in session.catalog.relations(METRIC))


def test_typed_outputs_reject_malformed_payloads():
    with pytest.raises(ValueError):
        Table([1])
    with pytest.raises(ValueError):
        Table([{"bad": float("nan")}])
    with pytest.raises(ValueError):
        Estimate(True)


async def test_table_preserves_monthly_query_metadata_and_rows():
    from examples.methods.scenarios.__main__ import run_scenario
    from examples.methods.scenarios.scenarios import scenarios, M
    trial = await run_scenario(next(s for s in scenarios() if s.name == "trend"))
    artifact = trial.result.primary
    assert artifact.type == "table"
    assert [(row["time"], row["metric"]) for row in artifact.data] == [
        ("2026-01-01", 20), ("2026-02-01", 30)]
    columns = {column.name: column for column in artifact.columns}
    assert columns["metric"].ref == M
    assert columns["metric"].role == "measure"
    assert columns["time"].role == "time"
    assert columns["time"].granularity == "month"
    from decision_layer.core.models import Artifact
    restored = Artifact.model_validate_json(artifact.model_dump_json())
    assert restored == artifact


def test_plain_tables_and_historical_artifacts_need_no_column_metadata():
    from decision_layer.core.models import Artifact
    output = Table([{"date": "2026-01-01", "value": 20}])
    assert output.primary.columns == []
    old = Artifact.model_validate({"type": "time_series", "data": {
        "metric": "value", "rows": [{"period": "2026-01-01", "value": 20}],
    }})
    assert old.columns == []
    assert old.data["rows"][0]["value"] == 20


async def test_legacy_time_series_method_contract_still_executes():
    from examples.methods.scenarios.scenarios import scenarios, M, DATE, JAN_FEB
    @method("example.legacy_series", version="1.0.0", interpretation="descriptive")
    async def legacy_series(ctx, *, metric: Measure) -> TimeSeries:
        data = await ctx.aggregate(measures={"metric": metric}, time_granularity="month")
        return TimeSeries.from_dataset(data, require_non_empty=True)
    session = await MethodSession.fixture(next(s for s in scenarios() if s.name == "trend").provider())
    session.register(legacy_series)
    trial = await session.run(legacy_series, metric=M, scope=Scope(JAN_FEB, DATE))
    assert trial.result.primary.type == "time_series"
    assert trial.result.primary.data["time_key"] == "time"
    assert trial.result.primary.data["granularity"] == "month"
    session.close()
