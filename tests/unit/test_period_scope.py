from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from decision_layer.core.models import CallerInfo, PlanStep, Recipe, RunDefaults
from decision_layer.core.periods import ExecutionPolicy, PeriodChoice, resolve_scope
from decision_layer.methods.base import InvalidBinding
from decision_layer.methods.context import ExecutionContext, Refused, Scope
from decision_layer.recipes.loader import RecipeStore
from decision_layer.runs.engine import ExecutionDeadlineExceeded, RunBusy, RunEngine
from decision_layer.runs.store import MemoryRunStore, UnknownRun
from decision_layer.service import ScopeIn
from test_methods import CAT, CREDS, DT, Q3, RR, FakeProvider

ME = CallerInfo(subject="period-owner")
DATES = {"date_range": list(Q3), "time_dimension": DT}
STEP = PlanStep(id="by_category", method="query.drilldown", purpose="Find the leading category", bindings={"metric": RR, "dimensions": [CAT]})


@pytest.fixture
def setup(cube_meta, tmp_path):
    provider = FakeProvider(cube_meta)
    provider.execute = AsyncMock(wraps=provider.execute)
    engine = RunEngine(provider, RecipeStore(tmp_path, "cube", "local"), MemoryRunStore())
    return engine, provider


@pytest.mark.parametrize("scope", [{}, {"date_range": None}, {"period": {"mode": "unresolved"}}])
def test_missing_is_not_all(scope):
    resolved, provenance = resolve_scope(scope, {}, ExecutionPolicy())
    assert resolved["period"]["mode"] == "unresolved"
    assert provenance["source"] == "unspecified"


@pytest.mark.parametrize("dates", [["2026-02-30", "2026-03-01"], ["2026-09-30", "2026-07-01"], ["20260701", "2026-09-30"]])
def test_invalid_dates_rejected(dates):
    with pytest.raises(ValidationError):
        ScopeIn(date_range=dates)


def test_conflicts_rejected_and_null_does_not_clear_recipe_default():
    with pytest.raises(ValidationError):
        ScopeIn(date_range=Q3, period=PeriodChoice(mode="all"))
    scope, provenance = resolve_scope({"date_range": None}, DATES, ExecutionPolicy())
    assert scope["date_range"] == list(Q3)
    assert provenance["source"] == "recipe_default"


def test_relative_period_uses_timezone_and_execution_clock():
    request = {"period": {"mode": "relative", "preset": "last_complete_month", "timezone": "Asia/Seoul"}}
    before, _ = resolve_scope(request, {}, ExecutionPolicy(), datetime(2026, 9, 30, 14, tzinfo=timezone.utc))
    after, _ = resolve_scope(request, {}, ExecutionPolicy(), datetime(2026, 9, 30, 16, tzinfo=timezone.utc))
    assert before["date_range"] == ["2026-08-01", "2026-08-31"]
    assert after["date_range"] == ["2026-09-01", "2026-09-30"]
    _, provenance = resolve_scope(request, {}, ExecutionPolicy())
    assert provenance["requested"]["mode"] == "relative"
    assert provenance["source_trust"] == "caller_reported"


async def test_pending_step_has_no_query_or_result_and_resumes_once(setup):
    engine, provider = setup
    from decision_layer.core.models import AnalysisGoal
    run = await engine.start(CREDS, ME, recipe=None, question="Which category?", scope={}, origin="mcp", goals=[AnalysisGoal(id="answer", description="Leading category")])
    step = STEP.model_copy(update={"goal_ids": ["answer"]})
    assert run.needs_input and not run.steps
    run, result = await engine.step(CREDS, ME, run.id, step)
    assert result.status == "needs_input" and not run.steps and not run.plan.steps
    provider.execute.assert_not_awaited()
    resumed = await engine.set_scope(CREDS, ME, run.id, DATES, run.scope_revision)
    assert resumed.id == run.id and resumed.scope_revision == run.scope_revision + 1
    assert not resumed.needs_input and len(resumed.steps) == 1
    assert resumed.steps[0].result.status == "success"
    count = provider.execute.await_count
    with pytest.raises(RunBusy):
        await engine.set_scope(CREDS, ME, run.id, DATES, 0)
    assert provider.execute.await_count == count


async def test_all_is_explicit_and_policy_is_server_owned(setup):
    engine, provider = setup
    run = await engine.start(CREDS, ME, recipe=None, question="All categories", scope={"period": {"mode": "all"}})
    assert run.needs_input
    provider.execute.assert_not_awaited()
    with pytest.raises(ValidationError):
        PeriodChoice(mode="all", confirmed=True)
    engine.policy = ExecutionPolicy(allow_all=True)
    all_run = await engine.start(CREDS, ME, recipe=None, question="All categories", scope={"period": {"mode": "all"}})
    all_run, result = await engine.step(CREDS, ME, all_run.id, STEP)
    assert result.status == "success"
    assert all_run.plan.scope["period"]["mode"] == "all"
    assert all_run.execution_policy.allow_all


async def test_scope_update_owner_revision_and_immutable_filters(setup):
    engine, _ = setup
    run = await engine.start(CREDS, ME, recipe=None, question="Inspect", scope={})
    with pytest.raises(UnknownRun):
        await engine.set_scope(CREDS, CallerInfo(subject="other"), run.id, DATES, 0)
    with pytest.raises(RunBusy):
        await engine.set_scope(CREDS, ME, run.id, DATES, 9)
    with pytest.raises(InvalidBinding):
        await engine.set_scope(CREDS, ME, run.id, {**DATES, "filters": []}, 0)


async def test_limits_and_freshness_are_checked_before_query(setup):
    engine, provider = setup
    engine.policy = ExecutionPolicy(max_period_days=20)
    recipe = Recipe(name="period-check", version="1.0.0", description="Inspect", mode="pipeline",
                    semantic_scope={"primary_metric": RR}, steps=[STEP], validators=[{"name": "freshness"}])
    run = await engine.preview(CREDS, ME, recipe, 0, DATES)
    assert run.needs_input and not run.steps and not run.validation
    provider.execute.assert_not_awaited()


async def test_recipe_relative_default_and_preview_resume(setup):
    engine, provider = setup
    recipe = Recipe(name="period-check", version="1.0.0", description="Inspect", mode="pipeline",
                    semantic_scope={"primary_metric": RR}, steps=[STEP])
    run = await engine.preview(CREDS, ME, recipe, 0, {})
    assert run.preview and run.needs_input
    resumed = await engine.set_scope(CREDS, ME, run.id, DATES, 0)
    assert resumed.status == "completed" and resumed.steps[0].result.status == "success"
    recipe.default_scope = RunDefaults(period=PeriodChoice(mode="relative", preset="last_n_days", days=7), time_dimension=DT)
    run = await engine.preview(CREDS, ME, recipe, 0, {})
    assert run.scope_resolution["source"] == "recipe_default"
    assert run.scope_resolution["requested"]["mode"] == "relative"


async def test_dataset_boundary_rejects_unbounded_and_oversized_method_query(setup):
    engine, provider = setup
    from decision_layer.core.models import DatasetSpec, TimeScope
    ctx = ExecutionContext(provider, CREDS, provider.catalog, Scope(Q3, DT), execution_policy=engine.policy)
    with pytest.raises(Refused):
        await ctx.dataset(DatasetSpec(grain="aggregate", measures=[RR]))
    with pytest.raises(Refused):
        await ctx.dataset(DatasetSpec(grain="aggregate", measures=[RR], time=TimeScope(dimension=DT, date_range=("2020-01-01", "2026-12-31"))))
    provider.execute.assert_not_awaited()


async def test_trend_cannot_use_all_even_when_server_allows_it(setup):
    engine, provider = setup
    engine.policy = ExecutionPolicy(allow_all=True)
    run = await engine.start(CREDS, ME, recipe=None, question="Trend", scope={"period": {"mode": "all"}})
    run, result = await engine.step(CREDS, ME, run.id, PlanStep(method="query.trend", bindings={"metric": RR}))
    assert result.status == "needs_input"
    assert run.needs_input["allow_all"] is False
    provider.execute.assert_not_awaited()


async def test_scope_update_does_not_repeat_a_pending_request(setup):
    engine, provider = setup
    run = await engine.start(CREDS, ME, recipe=None, question="Inspect", scope={})
    run, _ = await engine.step(CREDS, ME, run.id, STEP)
    revision = run.scope_revision
    run, _ = await engine.step(CREDS, ME, run.id, STEP)
    assert run.scope_revision == revision
    provider.execute.assert_not_awaited()


def test_scope_rest_and_mcp_contract(setup):
    from fastapi.testclient import TestClient
    from decision_layer.api.app import create_app
    from decision_layer.settings import Settings
    from decision_layer.mcp.server import _compact_run
    _, provider = setup
    settings = Settings(database_url="memory", allow_service_credentials=True, cube_api_secret="a-test-secret-at-least-32-characters", cube_service_groups=("ecommerce",))
    with TestClient(create_app(settings, provider)) as client:
        run = client.post("/runs", json={"question": "Which category?"}).json()
        assert run["needs_input"] and not run["steps"]
        compact = _compact_run(run)
        assert compact["next"]["tool"] == "set_run_scope"
        assert compact["scope_revision"] == 0
        provider.execute.assert_not_awaited()
        updated = client.put(f"/runs/{run['id']}/scope", json={"base_revision": 0, "scope": DATES})
        assert updated.status_code == 200, updated.text
        assert updated.json()["id"] == run["id"]
        assert updated.json()["needs_input"] is None
        assert client.put(f"/runs/{run['id']}/scope", json={"base_revision": 0, "scope": DATES}).status_code == 409
        assert client.post("/runs", json={"scope": {"period": {"mode": "all", "confirmed": True}}}).status_code == 422


async def test_application_deadline_is_recorded_without_claiming_warehouse_cancellation(setup):
    import asyncio
    engine, provider = setup
    engine.policy = ExecutionPolicy(deadline_seconds=0.01)
    original = provider.execute
    async def slow(*args, **kwargs):
        await asyncio.sleep(0.1)
        return await original(*args, **kwargs)
    provider.execute = slow
    with pytest.raises(ExecutionDeadlineExceeded):
        await engine.adhoc(CREDS, ME, STEP, DATES)
    run = (await engine.list(ME))[0]
    assert run.error["code"] == "EXECUTION_TIMEOUT"
    assert not run.running


async def test_validation_queries_share_the_execution_budget(setup):
    engine, provider = setup
    engine.policy = ExecutionPolicy(max_queries=1)
    recipe = Recipe(name="budget-check", version="1.0.0", description="Inspect", mode="pipeline",
                    semantic_scope={"primary_metric": RR}, steps=[STEP], validators=[{"name": "freshness"}])
    run = await engine.preview(CREDS, ME, recipe, 0, DATES)
    assert len(run.validation_queries) == 1
    assert provider.execute.await_count == 1
    assert run.steps[0].result.status == "refused"


async def test_promotion_preserves_declared_rule_not_execution_dates(setup):
    engine, _ = setup
    from decision_layer.recipes.from_run import candidate_from_run
    recipe = Recipe(name="relative-rule", version="1.0.0", description="Inspect", mode="pipeline",
                    semantic_scope={"primary_metric": RR}, steps=[STEP],
                    default_scope=RunDefaults(period=PeriodChoice(mode="relative", preset="last_complete_month"), time_dimension=DT))
    engine.recipes.save(recipe, None)
    run = await engine.start(CREDS, ME, recipe=recipe.name, question="Inspect", scope=DATES)
    candidate = candidate_from_run(run, [0]).recipe
    assert candidate.default_scope.period.mode == "relative"
    assert candidate.default_scope.date_range is None
