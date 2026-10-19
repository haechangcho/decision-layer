import pytest

from decision_layer.core.models import DatasetSpec, TimeScope, ValidationResult
from decision_layer.dev import MethodSession
from decision_layer.methods import InputTable, InvalidBinding, Scope, calculation
from decision_layer.testing import FixtureProvider, QueryFixture
from examples.methods.first_method.fixtures import METRIC, DIMENSION, DATE, DATES, fixture_provider
from examples.methods.authoring.native_calculation import rank_values, registered_method, fixture_session


async def test_native_pandas_function_matches_direct_call_and_retains_ties():
    import pandas as pd
    frame = pd.DataFrame({"value": [30, 20, 20], "group": ["A", "B", "C"]})
    expected = rank_values(frame)
    assert expected["rank"].tolist() == [1, 2, 2]
    session = await fixture_session()
    result = (await session.run("workshop.native_rank", metric=METRIC, group=DIMENSION,
                               scope=Scope(DATES, DATE))).result
    assert result.primary.data == expected.to_dict(orient="records")
    assert result.interpretation == "association"
    assert all(item.status == "pass" for item in result.validation)
    assert result.provenance.queries
    assert '"value":"metric"' in result.provenance.runtime["calculation.input_mapping"]
    assert "completeness" in result.warnings[-1]


@pytest.mark.parametrize("rows,code", [
    ([], "MINIMUM_ROWS"), ([[None, "A"]], "COMPLETE_COLUMNS"),
    ([[float("nan"), "A"]], "FINITE_MEASURES"),
    ([[3, "A"], [2, "A"]], "UNIQUE_GRAIN"),
])
async def test_invalid_observations_never_reach_the_calculation(rows, code):
    def must_not_run(data):
        raise AssertionError("Invalid data reached calculation")
    spec = DatasetSpec(grain="aggregate", measures=[METRIC], dimensions=[DIMENSION],
                       time=TimeScope(dimension=DATE, date_range=DATES), limit_rows=50001)
    provider = FixtureProvider(fixture_provider().catalog, [QueryFixture(spec, rows)])
    session = await MethodSession.fixture(provider)
    method = calculation(must_not_run, name="example.checked", version="1.0.0",
                         table=InputTable(measures={"value": "metric"}, dimensions={"group": "group"}))
    session.register(method)
    result = (await session.run(method, metric=METRIC, group=DIMENSION, scope=Scope(DATES, DATE))).result
    assert result.status == "refused" and result.primary is None
    assert any(item.code == code and item.status == "fail" for item in result.validation)


async def test_options_and_semantic_roles_are_checked_before_query():
    session = await fixture_session()
    with pytest.raises(InvalidBinding):
        await session.run("workshop.native_rank", metric=METRIC, group=DIMENSION,
                          descending="yes", scope=Scope(DATES, DATE))
    assert session.provider.calls == []


async def test_explicit_validator_failure_preserves_evidence_and_skips_function():
    def reject(data):
        return ValidationResult(validator="test.review@1", code="UNSUPPORTED_SAMPLE", status="fail",
                                message="This sample does not support the requested calculation.")
    def must_not_run(data):
        raise AssertionError("Failed validator was ignored")
    session = await fixture_session()
    method = calculation(must_not_run, name="example.reviewed", version="1.0.0",
                         table=InputTable(measures={"value": "metric"}, dimensions={"group": "group"}),
                         validators=[reject])
    session.register(method)
    result = (await session.run(method, metric=METRIC, group=DIMENSION, scope=Scope(DATES, DATE))).result
    assert result.status == "refused" and result.primary is None
    assert result.validation[-1].code == "UNSUPPORTED_SAMPLE"
    assert len(result.provenance.queries) == 1


async def test_native_function_runs_through_bounded_server_worker():
    import time
    from decision_layer.methods.context import ExecutionContext
    from decision_layer.core.periods import ExecutionPolicy
    from decision_layer.methods.calculation import _evaluate
    from decision_layer.semantic.credentials import AnonymousServiceCredentials
    async def persist():
        pass
    ctx = ExecutionContext(fixture_provider(), AnonymousServiceCredentials(), fixture_provider().catalog,
                           execution_policy=ExecutionPolicy(), persist_attempts=persist)
    method = registered_method()
    # Top-level native function, input rows, ordinary options and adapters are
    # pickleable; no provider or credentials are passed to the calculation.
    ctx._started = time.monotonic()
    output = await ctx.compute(_evaluate, rank_values,
        [{"value": 3, "group": "A"}, {"value": 3, "group": "B"}], {"descending": True},
        method.table, (), method.output, None)
    assert [row["rank"] for row in output.primary.data] == [1, 1]
