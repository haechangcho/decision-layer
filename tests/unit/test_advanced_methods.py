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
from decision_layer.methods import Refused, Scope
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
