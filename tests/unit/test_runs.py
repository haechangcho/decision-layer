"""Recipe engine and run storage, on the in-memory provider from test_methods."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.core.models import PlanStep
from decision_layer.methods.base import InvalidBinding
from decision_layer.recipes.loader import RecipeStore, UnknownRecipe
from decision_layer.runs.engine import MethodNotAllowed, RunClosed, RunEngine, RunLimitExceeded
from decision_layer.runs.store import MemoryRunStore, SqliteRunStore, UnknownRun
from decision_layer.settings import Settings
from decision_layer.core.models import CallerInfo
from test_methods import AMOUNT, CAT, COUNT, CREDS, Q3, RR, FakeProvider

REPO_RECIPES = Path(__file__).parents[2] / "examples" / "ecommerce" / "recipes"
SCOPE = {"date_range": list(Q3)}
ME = CallerInfo(subject="alice")


@pytest.fixture
def provider(cube_meta):
    return FakeProvider(cube_meta)


def engine(provider, store=None, recipes_dir=REPO_RECIPES):
    return RunEngine(provider, RecipeStore(recipes_dir, "cube", "local"), store or MemoryRunStore())


def write_recipe(tmp_path, text):
    (tmp_path / "r.yaml").write_text(text)
    return tmp_path


async def test_pipeline_feeds_earlier_results_forward(provider, tmp_path):
    e = engine(provider, SqliteRunStore(str(tmp_path / "runs.db")))
    run = await e.start(CREDS, ME, recipe="return-rate-drilldown", question="반품률 높은 곳", scope=SCOPE)
    assert run.status == "completed" and len(run.steps) == 2
    assert run.plan.recipe == "recipe://return-rate-drilldown@1.0.0" and run.recipe_snapshot.name == "return-rate-drilldown"
    second = run.steps[1]
    assert second.step.params["drill_path"] == [{"member": CAT, "value": "A"}]   # resolved from step 1
    assert second.result.primary.data["rows"][0]["value"] == "S1"
    stored = await e.store.get(run.id)                                          # round-trips through sqlite
    assert stored.model_dump() == run.model_dump()
    assert [r.id for r in await e.store.list(recipe="recipe://return-rate")] == [run.id]


async def test_investigation_is_enforced(provider):
    e = engine(provider)
    run = await e.start(CREDS, ME, recipe="return-rate-investigation", question="왜?", scope=SCOPE)
    assert run.status == "open" and not run.steps
    assert {x.validator for x in run.validation} == {"complete_period", "freshness"}

    _, result = await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR}))
    assert result.status == "success" and result.run_id == run.id
    with pytest.raises(MethodNotAllowed):
        await e.step(CREDS, ME, run.id, PlanStep(method="query.unknown", bindings={"metric": RR}))
    with pytest.raises(InvalidBinding):                                          # not in the recipe's metric scope
        await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": AMOUNT}))

    done = await e.complete(ME, run.id, "카테고리 A의 판매자 S1이 원인 후보")
    assert done.status == "completed" and done.summary and len(done.steps) == 1
    with pytest.raises(RunClosed):
        await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR}))


async def test_step_and_query_limits(provider, tmp_path):
    e = engine(provider, recipes_dir=write_recipe(tmp_path, """
name: tiny
version: 1.0.0
description: limits
semantic_scope: {primary_metric: ecom_order.return_rate}
mode: investigation
allowed_methods: [query.drilldown, query.trend]
limits: {max_steps: 2, max_queries: 2}
"""))
    run = await e.start(CREDS, ME, recipe="tiny", question=None, scope=SCOPE)
    _, first = await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR}))
    assert first.status == "success"                                             # series + freshness = 2 queries
    with pytest.raises(RunLimitExceeded):                                        # budget used up
        await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR}))


async def test_query_budget_refuses_mid_method(provider, tmp_path):
    e = engine(provider, recipes_dir=write_recipe(tmp_path, """
name: tiny
version: 1.0.0
description: limits
semantic_scope: {primary_metric: ecom_order.return_rate}
mode: investigation
allowed_methods: [query.trend]
limits: {max_queries: 1}
"""))
    run = await e.start(CREDS, ME, recipe="tiny", question=None, scope=SCOPE)
    _, r = await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR}))
    assert r.status == "refused" and "budget" in r.warnings[0]


async def test_broken_pipeline_is_recorded_as_failed(provider, tmp_path):
    # a forward reference to a real earlier step whose result lacks that path:
    # it loads (the step id exists) but fails at run time when the path is resolved.
    e = engine(provider, recipes_dir=write_recipe(tmp_path, """
name: broken
version: 1.0.0
description: bad reference
semantic_scope: {primary_metric: ecom_order.return_rate, preferred_dimensions: [ecom_product.category_nm]}
mode: pipeline
steps:
  - {id: a, method: query.drilldown, bindings: {metric: $scope.primary_metric, dimensions: $scope.preferred_dimensions}}
  - {id: b, method: query.drilldown, bindings: {metric: $scope.primary_metric, dimensions: $scope.preferred_dimensions},
     params: {drill_path: $steps.a.primary.data.no_such_field}}
"""))
    run = await e.start(CREDS, ME, recipe="broken", question=None, scope=SCOPE)
    assert run.status == "failed" and "no_such_field" in run.steps[-1].result.warnings[0]


async def test_unknown_recipe_and_run(provider):
    e = engine(provider)
    with pytest.raises(UnknownRecipe):
        await e.start(CREDS, ME, recipe="nope", question=None, scope=SCOPE)
    with pytest.raises(UnknownRun):
        await e.store.get("run_x")


def test_api_runs(provider):
    s = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="s",
                 cube_service_groups=("ecommerce",), database_url="memory", recipes_dir=str(REPO_RECIPES),
                 allow_service_credentials=True)
    c = TestClient(create_app(s, provider))
    assert {r["name"] for r in c.get("/recipes").json()} >= {"return-rate-investigation", "sales-change-diagnosis"}
    run = c.post("/runs", json={"recipe": "return-rate-investigation", "question": "왜?", "scope": SCOPE}).json()
    step = c.post(f"/runs/{run['id']}/steps", json={"method": "query.trend", "bindings": {"metric": RR}}).json()
    assert step["status"] == "success" and step["run_id"] == run["id"]
    r = c.post(f"/runs/{run['id']}/steps", json={"method": "query.unknown", "bindings": {"metric": RR}})
    assert r.status_code == 403 and r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert c.post(f"/runs/{run['id']}:complete", json={"summary": "끝"}).json()["status"] == "completed"
    adhoc = c.post("/methods/query.trend:run", json={"bindings": {"metric": RR}, "scope": SCOPE}).json()
    assert adhoc["run_id"] and len(c.get("/runs").json()) == 2
    assert c.get(f"/runs/{adhoc['run_id']}").json()["steps"][0]["step"]["method"] == "query.trend"
