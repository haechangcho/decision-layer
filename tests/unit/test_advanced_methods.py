"""Fail-closed data, process limits and canonical HTTP/Recipe execution."""
import asyncio
from dataclasses import replace
import importlib.util
import time
import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.core.models import PlanStep, Recipe, SemanticScope
from decision_layer.core.periods import ExecutionPolicy
from decision_layer.dev import MethodSession
from decision_layer.methods import Refused, Scope, register_builtins
from decision_layer.methods.context import ExecutionContext
from decision_layer.semantic.credentials import AnonymousServiceCredentials
from decision_layer.settings import Settings
from tests.support.methods.cases import scenarios, M, BEFORE, BASELINE, UNIT, DATE, FEB
from tests.support.methods.functions import group_metric

HAS_STATS = importlib.util.find_spec("pandas") is not None and importlib.util.find_spec("statsmodels") is not None


def _slow(seconds):
    time.sleep(seconds)
    return {"value": 1}


def _answer():
    return {"value": 7}


async def _persist():
    pass


async def test_server_compute_terminates_and_local_compute_stays_in_process():
    provider = scenarios()[0].provider()
    ctx = ExecutionContext(provider, AnonymousServiceCredentials(), provider.catalog,
        execution_policy=ExecutionPolicy(deadline_seconds=.05), persist_attempts=_persist)
    start = time.monotonic()
    with pytest.raises(Refused, match="deadline"):
        await ctx.compute(_slow, 20)
    assert time.monotonic() - start < 3
    local = ExecutionContext(provider, AnonymousServiceCredentials(), provider.catalog)
    assert await local.compute(_answer) == {"value": 7}


async def test_server_compute_result_is_returned():
    provider = scenarios()[0].provider()
    ctx = ExecutionContext(provider, AnonymousServiceCredentials(), provider.catalog,
        execution_policy=ExecutionPolicy(deadline_seconds=10), persist_attempts=_persist)
    assert (await ctx.compute(_answer))["value"] == 7


@pytest.mark.skipif(not HAS_STATS, reason="Install stats extra")
@pytest.mark.parametrize("problem", ["duplicate", "missing", "singular"])
async def test_regression_bad_observations_refuse(problem):
    scenario = next(item for item in scenarios() if item.name == "ols")
    query = scenario.queries[0]
    rows = [list(row) for row in query.rows]
    if problem == "duplicate":
        rows[1][-1] = rows[0][-1]
    elif problem == "missing":
        rows[0][0] = None
    else:
        for row in rows:
            row[2] = row[1]
    scenario.queries = [replace(query, rows=rows)]
    session = await MethodSession.fixture(scenario.provider())
    register_builtins(session.registry)
    trial = await session.run(scenario.method, **scenario.arguments)
    assert trial.result.status == "refused" and trial.result.provides == []


@pytest.mark.skipif(not HAS_STATS, reason="Install stats extra")
async def test_per_unit_measure_covariate_is_query_measure_not_dimension():
    scenario = next(item for item in scenarios() if item.name == "ols")
    query = scenario.queries[0]
    scenario.arguments["measures"]["features"] = [BEFORE]
    scenario.arguments.pop("dimensions")
    # Independent expectation: outcome and baseline are measures, not group keys.
    scenario.queries = [replace(query, spec=query.spec.model_copy(update={"measures": [M, BEFORE], "dimensions": []}),
                               rows=[[row[0], row[2], row[-1]] for row in query.rows])]
    provider = scenario.provider()
    session = await MethodSession.fixture(provider)
    register_builtins(session.registry)
    trial = await session.run(scenario.method, **scenario.arguments)
    assert trial.result.status == "success"
    provider.assert_consumed()


@pytest.mark.skipif(not HAS_STATS, reason="Install stats extra")
@pytest.mark.parametrize("problem", ["duplicate", "missing_period", "changing_group", "overlap"])
async def test_panel_bad_observations_refuse(problem):
    scenario = next(item for item in scenarios() if item.name == "did")
    query = scenario.queries[0]
    rows = [list(row) for row in query.rows]
    if problem == "duplicate":
        rows.append(rows[0])
    elif problem == "missing_period":
        rows.pop()
    elif problem == "changing_group":
        rows[2][1] = 0
    else:
        scenario.arguments.setdefault("params", {})["windows"] = [FEB, FEB]
    scenario.queries = [replace(query, rows=rows)]
    provider = scenario.provider()
    session = await MethodSession.fixture(provider)
    register_builtins(session.registry)
    trial = await session.run(scenario.method, **scenario.arguments)
    assert trial.result.status == "refused" and not trial.result.provides
    if problem == "overlap":
        assert not provider.calls


async def test_unknown_analysis_design_refuses_before_dataset_request():
    scenario = next(item for item in scenarios() if item.name == "did")
    scenario.method = "stats.did"  # Legacy contract remains fail-closed.
    scenario.arguments["params"] = {"design": {"note": "Unverified comparison"}}
    provider = scenario.provider()
    session = await MethodSession.fixture(provider)
    register_builtins(session.registry)
    trial = await session.run(scenario.method, **scenario.arguments)
    assert trial.result.status == "refused" and not provider.calls


@pytest.mark.skipif(not HAS_STATS, reason="Install stats extra")
async def test_boolean_native_panel_groups_work():
    scenario = next(item for item in scenarios() if item.name == "did")
    query = scenario.queries[0]
    scenario.queries = [replace(query, rows=[[value, bool(treated), unit, date] for value, treated, unit, date in query.rows])]
    provider = scenario.provider()
    session = await MethodSession.fixture(provider)
    register_builtins(session.registry)
    trial = await session.run(scenario.method, **scenario.arguments)
    assert trial.result.status == "success" and trial.result.primary.data["value"] == 3
    provider.assert_consumed()


def test_rest_input_maps_normalize_to_recorded_canonical_bindings(monkeypatch):
    from decision_layer.methods import registry
    monkeypatch.setitem(registry._methods, group_metric.manifest.name, group_metric)
    scenario = next(item for item in scenarios() if item.name == "by_group")
    provider = scenario.provider()
    settings = Settings(cube_api_url="http://fixture", cube_api_secret="fixture", database_url="memory", allow_service_credentials=True)
    with TestClient(create_app(settings, provider)) as client:
        response = client.post("/methods/example.group_metric:run", json={
            "measures": scenario.arguments["measures"], "dimensions": scenario.arguments["dimensions"],
            "params": {"limit": 3}, "scope": {"date_range": list(FEB), "time_dimension": DATE}})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "success"
        run = client.get("/runs/" + result["run_id"]).json()
        assert run["steps"][0]["step"]["bindings"] == {"metric": M, "group": scenario.arguments["dimensions"]["group"]}
        assert len(run["query_attempts"]) == 1
    provider.assert_consumed()


async def test_authored_recipe_preview_uses_the_same_query_and_result():
    scenario = next(item for item in scenarios() if item.name == "by_group")
    provider = scenario.provider()
    session = await MethodSession.fixture(provider)
    session.register(group_metric)
    recipe = Recipe(name="authored-test", version="1.0.0", description="Authored contract", mode="pipeline",
        semantic_scope=SemanticScope(primary_metric=M),
        steps=[PlanStep(method=group_metric.manifest.name, bindings={"metric": M, "group": scenario.arguments["dimensions"]["group"]}, params={"limit": 3})])
    try:
        run = await session.preview(recipe, step_index=0, scope={"date_range": list(FEB), "time_dimension": DATE})
        assert run.steps[0].result.status == "success"
        assert [row["metric"] for row in run.steps[0].result.primary.data] == [30, 20, 10]
        assert run.preview and len(run.query_attempts) == 1
    finally:
        session.close()
    provider.assert_consumed()


@pytest.mark.skipif(not HAS_STATS, reason="Install stats extra")
def test_high_cardinality_covariates_refuse_before_encoding():
    import pandas as pd
    from decision_layer.methods.statistics import fit_ols
    frame = pd.DataFrame({"unit": [str(i) for i in range(150)], "outcome": list(range(150)),
                          "category": [f"category-{i}" for i in range(150)]})
    with pytest.raises(Refused, match="matrix bound"):
        fit_ols(frame, ["category"])


async def test_materialization_width_refuses_before_query():
    from decision_layer.methods import Measure, Table, method
    @method("example.too_wide", version="1.0.0", interpretation="descriptive")
    async def too_wide(ctx, *, outcome: Measure) -> Table:
        data = await ctx.aggregate(measures={f"alias_{i}": outcome for i in range(101)})
        return Table.from_dataset(data)
    provider = scenarios()[0].provider()
    session = await MethodSession.fixture(provider)
    session.register(too_wide)
    trial = await session.run(too_wide, measures={"outcome": M}, scope=Scope(FEB, DATE))
    assert trial.result.status == "refused" and not provider.calls


def _credential_environment():
    import os
    return {"provider": os.environ.get("CUBE_API_SECRET"), "database": os.environ.get("DL_DATABASE_URL"),
            "token": os.environ.get("CUSTOM_ACCESS_TOKEN")}


async def test_statistical_worker_does_not_inherit_server_credential_environment(monkeypatch):
    monkeypatch.setenv("CUBE_API_SECRET", "test-provider-credential")
    monkeypatch.setenv("DL_DATABASE_URL", "memory")
    monkeypatch.setenv("CUSTOM_ACCESS_TOKEN", "test-custom-token")
    provider = scenarios()[0].provider()
    ctx = ExecutionContext(provider, AnonymousServiceCredentials(), provider.catalog,
        execution_policy=ExecutionPolicy(deadline_seconds=10), persist_attempts=_persist)
    result = await ctx.compute(_credential_environment)
    assert {k: result[k] for k in ("provider", "database", "token")} == {
        "provider": None, "database": None, "token": None}
    import os
    assert os.environ["CUBE_API_SECRET"] == "test-provider-credential"


@pytest.mark.parametrize("case,dependency", [("ols", "statsmodels"), ("dowhy", "dowhy"), ("econml", "econml"), ("did", "pandas")])
def test_optional_estimators_execute_and_record_through_canonical_api(case, dependency):
    if not importlib.util.find_spec(dependency):
        pytest.skip("Install analytical extras")
    from tests.support.methods.run import wire
    scenario = next(s for s in scenarios() if s.name == case)
    provider = scenario.provider()
    settings = Settings(cube_api_url="http://fixture", cube_api_secret="fixture", database_url="memory", allow_service_credentials=True)
    with TestClient(create_app(settings, provider)) as client:
        response = client.post(f"/methods/{scenario.method}:run", json=wire(scenario.arguments))
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "success", result
        assert result["interpretation"] == "associational"
        assert dependency in result["provenance"]["runtime"]
        if case == "ols":
            coefficients = [r["coefficient"] for r in result["primary"]["data"] if r["term"] != "const"]
            assert all(abs(actual - expected) < .15 for actual, expected in zip(coefficients, [2, 3]))
        else:
            assert abs(result["primary"]["data"]["value"] - (3 if case == "did" else 2)) < .15
            assert result["primary"]["data"]["causal_claim"] == "not_established"
        recorded = client.get("/runs/" + result["run_id"]).json()
        assert len(recorded["query_attempts"]) == 1
        assert recorded["query_attempts"][0]["status"] == "success"
        assert recorded["steps"][0]["result"] == {k: v for k, v in result.items()}
    provider.assert_consumed()


def test_current_statistical_signatures_do_not_require_design_or_seed():
    from decision_layer.methods.advanced import binary_regression, linear_dml, two_period_contrast
    for method in (binary_regression, linear_dml):
        assert set(method.manifest.roles) == {"outcome", "treatment", "confounders", "unit"}
        assert method.manifest.parameters == {}
        assert method.manifest.interpretation == "associational"
    assert set(two_period_contrast.manifest.parameters) == {"windows", "granularity"}


@pytest.mark.skipif(not HAS_STATS, reason="Install stats extra")
async def test_legacy_panel_contract_still_executes_its_original_version():
    scenario = next(item for item in scenarios() if item.name == "did")
    scenario.method = "stats.did"
    scenario.arguments["params"] = {"design": {
        "note": "Synthetic two-period test; not a real causal identification claim",
        "pre_period": "2026-01", "post_period": "2026-02",
        "parallel_trends": True, "no_anticipation": True,
        "no_interference": True, "independent_units": True,
    }}
    provider = scenario.provider()
    session = await MethodSession.fixture(provider)
    register_builtins(session.registry)
    trial = await session.run(scenario.method, **scenario.arguments)
    assert trial.result.status == "success"
    assert trial.result.primary.data["value"] == 3
    assert trial.result.primary.data["assumptions_status"] == "author_asserted"
    provider.assert_consumed()
    session.close()


@pytest.mark.skipif(not HAS_STATS, reason="Install stats extra")
async def test_two_period_contrast_rejects_three_periods_instead_of_guessing():
    scenario = next(item for item in scenarios() if item.name == "did")
    query = scenario.queries[0]
    extra = [[row[0], row[1], row[2], "2026-04-01"] for row in query.rows if row[-1] == "2026-02-01"]
    scenario.queries = [replace(query, rows=[*query.rows, *extra])]
    session = await MethodSession.fixture(scenario.provider())
    register_builtins(session.registry)
    trial = await session.run(scenario.method, **scenario.arguments)
    assert trial.result.status == "refused"
    assert len(trial.attempts) == 1
    session.close()
