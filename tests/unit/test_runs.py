"""Recipe engine and run storage, on the in-memory provider from test_methods."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.core.models import PlanStep
from decision_layer.methods.base import InvalidBinding
from decision_layer.recipes.loader import RecipeStore, UnknownRecipe
from decision_layer.runs.engine import MethodNotAllowed, RunBusy, RunClosed, RunEngine, RunLimitExceeded
from decision_layer.runs.store import MemoryRunStore, SqliteRunStore, UnknownRun
from decision_layer.settings import Settings
from decision_layer.core.models import CallerInfo, RunningJob
from test_methods import AMOUNT, CAT, COUNT, CREDS, Q3, RR, FakeProvider

REPO_RECIPES = Path(__file__).parents[1] / "fixtures" / "recipes"
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


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
async def test_run_delete_is_owner_only_and_rejects_active_jobs(provider, tmp_path, backend):
    store = MemoryRunStore() if backend == "memory" else SqliteRunStore(str(tmp_path / "runs.db"))
    e = engine(provider, store, recipes_dir=tmp_path)
    run = await e.start(CREDS, ME, recipe=None, question="Which segment changed?", scope=SCOPE)
    run.shared_with = ["bob"]
    await store.save(run)
    with pytest.raises(UnknownRun):
        await e.delete(CallerInfo(subject="bob"), run.id)
    run.running = RunningJob(kind="step", method="query.trend")
    await store.save(run)
    with pytest.raises(RunBusy):
        await e.delete(ME, run.id)
    run.running = None
    await store.save(run)
    await e.delete(ME, run.id)
    with pytest.raises(UnknownRun):
        await store.get(run.id)
    assert await e.list(ME) == []


def test_delete_run_endpoint_preserves_registered_recipe(provider, tmp_path):
    settings = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="test-secret-at-least-32-characters",
                        cube_service_groups=("ecommerce",), database_url="memory", recipes_dir=str(tmp_path),
                        allow_service_credentials=True)
    client = TestClient(create_app(settings, provider))
    run = client.post("/runs", json={"question": "Inspect change", "scope": SCOPE}).json()
    result = client.post(f"/runs/{run['id']}/steps", json={"method": "query.trend", "bindings": {"metric": RR}})
    assert result.status_code == 200
    assert client.post(f"/runs/{run['id']}:complete", json={"summary": "Done"}).status_code == 200
    assert client.post(f"/runs/{run['id']}/recipe").status_code == 200
    response = client.delete(f"/runs/{run['id']}")
    assert response.status_code == 204
    assert client.get(f"/runs/{run['id']}").status_code == 404
    assert client.get("/runs").json() == []
    assert len(client.get("/recipes").json()) == 1
    assert client.delete(f"/runs/{run['id']}").status_code == 404


def test_one_click_registration_replays_settings_and_is_idempotent(provider, tmp_path):
    settings = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="test-secret-at-least-32-characters",
                        cube_service_groups=("ecommerce",), database_url="memory", recipes_dir=str(tmp_path),
                        allow_service_credentials=True)
    client = TestClient(create_app(settings, provider))
    scope = {**SCOPE, "time_dimension": "cube://local/ecom_order/order_dt",
             "filters": [{"member": CAT, "operator": "equals", "values": ["A"]}]}
    source = client.post("/runs", json={"question": "Which groups are highest?", "scope": scope}).json()
    endpoint = f"/runs/{source['id']}/recipe"
    assert client.post(endpoint).status_code == 422
    result = client.post(f"/runs/{source['id']}/steps", json={"method": "query.drilldown", "purpose": "Inspect groups",
        "bindings": {"metric": RR, "dimensions": [CAT]}, "params": {"top_n": 5, "min_count": 10}})
    assert result.json()["status"] == "success", result.json()
    source = client.post(f"/runs/{source['id']}:complete", json={"summary": "Reviewed"}).json()
    response = client.post(endpoint)
    assert response.status_code == 200, response.json()
    recipe = response.json()
    assert recipe["status"] == "published"
    assert recipe["steps"][0]["params"] == source["steps"][0]["step"]["params"]
    assert recipe["steps"][0]["purpose"] == "Inspect groups"
    assert recipe["steps"][0]["method_version"] == "2.0.0"
    assert recipe["semantic_scope"]["required_filters"] == scope["filters"]
    assert client.post(endpoint).json() == recipe
    assert len(client.get("/recipes").json()) == 1
    replay = client.post("/runs", json={"recipe": recipe["name"]}).json()
    assert replay["status"] == "completed", replay
    assert replay["plan"]["scope"] == scope
    assert replay["steps"][0]["result"]["primary"] == source["steps"][0]["result"]["primary"]
    assert replay["steps"][0]["result"]["provenance"]["queries"][0]["native_query"] == source["steps"][0]["result"]["provenance"]["queries"][0]["native_query"]
    cleared = client.post("/runs", json={"recipe": recipe["name"], "scope": {"date_range": None}}).json()
    assert cleared["plan"]["scope"]["date_range"] is None
    recipe["version"] = "1.0.1"
    recipe["steps"][0]["method_version"] = "0.0.0"
    assert client.put(f"/recipes/{recipe['name']}", json={"recipe": recipe, "base_version": "1.0.0"}).status_code == 200
    blocked = client.post("/runs", json={"recipe": recipe["name"]}).json()
    assert blocked["status"] == "failed"
    assert blocked["steps"][0]["result"]["provenance"]["queries"] == []
    assert client.delete(f"/recipes/{recipe['name']}?base_version=1.0.0").status_code == 409
    assert client.delete(f"/recipes/{recipe['name']}?base_version=1.0.1").status_code == 204
    assert client.get("/recipes").json() == []
    assert client.get(f"/runs/{source['id']}").json() == source
    assert client.get(f"/runs/{replay['id']}").json()["recipe_snapshot"]["version"] == "1.0.0"
    assert client.post("/runs", json={"recipe": recipe["name"]}).status_code == 404


async def test_pipeline_feeds_earlier_results_forward(provider, tmp_path):
    e = engine(provider, SqliteRunStore(str(tmp_path / "runs.db")))
    run = await e.start(CREDS, ME, recipe="return-rate-drilldown", question="반품률 높은 곳", scope=SCOPE)
    assert run.status == "completed" and len(run.steps) == 2
    assert run.plan.recipe == "recipe://return-rate-drilldown@1.0.0" and run.recipe_snapshot.name == "return-rate-drilldown"
    second = run.steps[1]
    assert second.step.params["drill_path"] == [{"member": CAT, "value": "A"}]   # resolved from step 1
    assert second.parameter_sources["drill_path"] == "recipe"
    assert second.parameter_sources["top_n"] == "method_default"
    assert second.step.params["top_n"] == 10
    assert second.result.primary.data["rows"][0]["value"] == "S1"
    stored = await e.store.get(run.id)                                          # round-trips through sqlite
    assert stored.model_dump() == run.model_dump()
    assert [r.id for r in await e.store.list(recipe="recipe://return-rate")] == [run.id]


async def test_unsaved_recipe_preview_uses_the_same_pipeline_and_preserves_evidence(provider):
    e = engine(provider)
    recipe = e.recipes.get("return-rate-drilldown")
    preview = await e.preview(CREDS, ME, recipe, 1, SCOPE)
    assert preview.preview and preview.status == "completed" and len(preview.steps) == 2
    assert preview.plan.recipe is None and preview.recipe_snapshot == recipe
    assert preview.steps[1].result.provenance.queries
    assert preview.steps[1].step.params["drill_path"] == [{"member": CAT, "value": "A"}]
    assert (await e.store.get(preview.id)).model_dump() == preview.model_dump()


async def test_preview_rejects_an_unconfigured_step(provider):
    e = engine(provider)
    recipe = e.recipes.get("return-rate-drilldown")
    from decision_layer.runs.engine import PreviewStepInvalid
    with pytest.raises(PreviewStepInvalid):
        await e.preview(CREDS, ME, recipe, 2, SCOPE)


async def test_investigation_is_enforced(provider):
    e = engine(provider)
    run = await e.start(CREDS, ME, recipe="return-rate-investigation", question="왜?", scope=SCOPE)
    assert run.status == "open" and not run.steps
    assert {x.validator for x in run.validation} == {"complete_period", "freshness"}

    _, result = await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR}))
    assert result.status == "success" and result.run_id == run.id
    recorded = (await e.store.get(run.id)).steps[0]
    assert recorded.step.params["granularity"] == "month"
    assert recorded.parameter_sources["granularity"] == "method_default"
    with pytest.raises(MethodNotAllowed):
        await e.step(CREDS, ME, run.id, PlanStep(method="query.unknown", bindings={"metric": RR}))
    with pytest.raises(InvalidBinding):                                          # not in the recipe's metric scope
        await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": AMOUNT}))

    done = await e.complete(ME, run.id, "카테고리 A의 판매자 S1이 원인 후보")
    assert done.status == "completed" and done.summary and len(done.steps) == 1
    with pytest.raises(RunClosed):
        await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR}))


async def test_adhoc_explicit_parameter_source(provider):
    e = engine(provider)
    run, result = await e.adhoc(CREDS, ME, PlanStep(method="query.trend", bindings={"metric": RR},
                                                 params={"granularity": "week"}), SCOPE)
    assert result.status == "success"
    assert run.steps[0].step.params["granularity"] == "week"
    assert run.steps[0].parameter_sources["granularity"] == "request"
    assert run.steps[0].parameter_sources["vs_previous"] == "method_default"


async def test_recipe_free_question_keeps_multiple_methods_in_one_run(provider, tmp_path):
    e = engine(provider, SqliteRunStore(str(tmp_path / "runs.db")), recipes_dir=tmp_path / "empty")
    assert e.recipes.list() == []
    run = await e.start(CREDS, ME, recipe=None, question="반품률이 어떻게 변했고 어느 범주가 높은가?", scope=SCOPE,
                        origin="mcp")
    assert run.status == "open" and run.recipe_snapshot is None
    await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", purpose="기간별 반품률을 확인", bindings={"metric": RR}))
    await e.step(CREDS, ME, run.id, PlanStep(method="query.drilldown", bindings={"metric": RR, "dimensions": [CAT]}))
    done = await e.complete(ME, run.id, "두 분석 단계의 결과를 확인함")
    stored = await e.store.get(run.id)
    assert done.status == "completed" and stored.origin == "mcp"
    assert stored.plan.question == "반품률이 어떻게 변했고 어느 범주가 높은가?"
    assert [record.step.method for record in stored.steps] == ["query.trend", "query.drilldown"]
    assert stored.steps[0].step.purpose == "기간별 반품률을 확인"
    assert all(record.result.provenance.queries for record in stored.steps)


async def test_recipe_fixed_parameters_apply_to_steps_and_reject_runtime_overrides(provider, tmp_path):
    e = engine(provider, recipes_dir=write_recipe(tmp_path, """
name: governed-trend
version: 1.0.0
description: Governed trend
semantic_scope: {primary_metric: ecom_order.return_rate}
mode: investigation
allowed_methods: [query.trend]
method_parameters:
  query.trend:
    fixed: {granularity: week}
    runtime_allowed: [vs_previous]
"""))
    run = await e.start(CREDS, ME, recipe="governed-trend", question=None, scope=SCOPE)
    with pytest.raises(InvalidBinding, match="fixed"):
        await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR},
                                                params={"granularity": "month"}))
    with pytest.raises(InvalidBinding, match="runtime"):
        await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR},
                                                params={"comparison": ["2026-01-01", "2026-03-31"]}))
    _, result = await e.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR},
                                                         params={"vs_previous": True}))
    assert result.status == "success"
    recorded = (await e.store.get(run.id)).steps[0]
    assert recorded.step.params["granularity"] == "week"
    assert recorded.parameter_sources["granularity"] == "recipe_fixed"
    assert recorded.parameter_sources["vs_previous"] == "request"


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
    run = c.post("/runs", json={"recipe": "return-rate-investigation", "question": "왜?", "scope": SCOPE},
                 headers={"X-Decision-Layer-Client": "web"}).json()
    assert run["origin"] == "web"
    step = c.post(f"/runs/{run['id']}/steps", json={"method": "query.trend", "bindings": {"metric": RR}}).json()
    assert step["status"] == "success" and step["run_id"] == run["id"]
    r = c.post(f"/runs/{run['id']}/steps", json={"method": "query.unknown", "bindings": {"metric": RR}})
    assert r.status_code == 403 and r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert c.post(f"/runs/{run['id']}:complete", json={"summary": "끝"}).json()["status"] == "completed"
    adhoc = c.post("/methods/query.trend:run", json={"bindings": {"metric": RR}, "scope": SCOPE}).json()
    assert adhoc["run_id"] and len(c.get("/runs").json()) == 2
    adhoc_step = c.get(f"/runs/{adhoc['run_id']}").json()["steps"][0]
    assert adhoc_step["step"]["method"] == "query.trend"
    assert adhoc_step["step"]["params"]["granularity"] == "month"
    assert adhoc_step["parameter_sources"]["granularity"] == "method_default"
    assert c.get(f"/runs/{adhoc['run_id']}").json()["origin"] == "api"
    mcp = c.post("/methods/query.trend:run", json={"question": "Why did returns change?", "bindings": {"metric": RR}, "scope": SCOPE},
                 headers={"X-Decision-Layer-Client": "mcp"}).json()
    assert c.get(f"/runs/{mcp['run_id']}").json()["origin"] == "mcp"
    assert c.get(f"/runs/{mcp['run_id']}").json()["plan"]["question"] == "Why did returns change?"
    candidate = c.get(f"/runs/{adhoc['run_id']}/recipe-candidate", params={"indices": 0})
    assert candidate.status_code == 200, candidate.json()
    assert candidate.json()["recipe"]["status"] == "draft"
    assert candidate.json()["recipe"]["origin_runs"] == [adhoc["run_id"]]
    assert candidate.json()["recipe"]["steps"][0]["params"]["granularity"] == "month"
    assert c.get(f"/runs/{adhoc['run_id']}/recipe-candidate", params={"indices": 1}).status_code == 422


def test_api_enforces_recipe_parameter_policy(provider, tmp_path):
    recipes_dir = write_recipe(tmp_path, """
name: governed-trend
version: 1.0.0
description: Governed trend
semantic_scope: {primary_metric: ecom_order.return_rate}
mode: investigation
allowed_methods: [query.trend]
method_parameters:
  query.trend:
    fixed: {granularity: week}
    runtime_allowed: [vs_previous]
""")
    settings = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="s",
                        cube_service_groups=("ecommerce",), database_url="memory", recipes_dir=str(recipes_dir),
                        allow_service_credentials=True)
    client = TestClient(create_app(settings, provider))
    run = client.post("/runs", json={"recipe": "governed-trend", "scope": SCOPE}).json()
    bad = client.post(f"/runs/{run['id']}/steps", json={"method": "query.trend", "bindings": {"metric": RR},
                                                      "params": {"granularity": "month"}})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "INVALID_BINDING"
    good = client.post(f"/runs/{run['id']}/steps", json={"method": "query.trend", "bindings": {"metric": RR},
                                                       "params": {"vs_previous": True}})
    assert good.status_code == 200
    stored = client.get(f"/runs/{run['id']}").json()["steps"][0]
    assert stored["step"]["params"]["granularity"] == "week"
    assert stored["parameter_sources"]["granularity"] == "recipe_fixed"


def test_api_previews_an_unsaved_recipe_without_publishing_it(provider):
    settings = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret="s",
                        cube_service_groups=("ecommerce",), database_url="memory", recipes_dir=str(REPO_RECIPES),
                        allow_service_credentials=True)
    client = TestClient(create_app(settings, provider))
    original = RecipeStore(REPO_RECIPES, "cube", "local").get("return-rate-drilldown")
    draft = original.model_copy(update={"name": "preview-only", "description": "Unsaved preview"})
    response = client.post("/recipes:preview", json={"recipe": draft.model_dump(mode="json"),
                                                      "step_index": 1, "scope": SCOPE},
                           headers={"X-Decision-Layer-Client": "web"})
    assert response.status_code == 200
    run = response.json()
    assert run["preview"] and run["recipe_snapshot"]["name"] == "preview-only"
    assert run["origin"] == "web"
    assert len(run["steps"]) == 2 and run["steps"][1]["result"]["provenance"]["queries"]
    assert "preview-only" not in {item["name"] for item in client.get("/recipes").json()}
