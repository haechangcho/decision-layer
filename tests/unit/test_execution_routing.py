"""Routing and completion contracts using known semantic answers, without an LLM."""
import asyncio
import json
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from decision_layer.api.app import create_app
from decision_layer.core.models import AnalysisGoal, GoalOutcome, PlanStep, Recipe, RecipeReview, RecipeSelection, Run, RunConclusion, RunFinding
from decision_layer.core.periods import ExecutionPolicy
from decision_layer.methods import InvalidBinding
from decision_layer.recipes.loader import RecipeStore
from decision_layer.recipes.routing import search_recipes
from decision_layer.runs.engine import MethodNotAllowed, RunEngine, RunLimitExceeded
from decision_layer.runs.proposals import method_proposal
from decision_layer.runs.store import MemoryRunStore, SqliteRunStore
from decision_layer.service import MethodProposalRequest
from decision_layer.settings import Settings
from tests.support.semantic import AMOUNT, CAT, COUNT, CREDS, DT, Q3, RR, FakeProvider
from tests.support.runs import ME, SCOPE


@pytest.fixture
def setup(cube_meta, tmp_path):
    provider = FakeProvider(cube_meta)
    store = RecipeStore(tmp_path / "recipes", "cube", "local")
    return RunEngine(provider, store, MemoryRunStore()), provider


def goal(name="lookup", capability="metric_lookup", metric=AMOUNT, interpretation="descriptive"):
    return AnalysisGoal(id=name, description="Answer the requested part", semantic_refs=[metric],
                        required_capabilities=[capability], interpretation=interpretation)


def lookup(**extra):
    return PlanStep(id="lookup", method="query.aggregate", purpose="Inspect governed sales",
                    bindings={"metric": AMOUNT, "dimensions": [CAT]}, **extra)


def recipe(name="lookup-procedure", metric=AMOUNT, method="query.aggregate", **extra):
    return Recipe(name=name, version="1.0.0", description="Sales by department",
        routing={"objective": "Inspect sales by department"}, semantic_scope={"primary_metric": metric},
        mode="pipeline", steps=[PlanStep(id="first", method=method, bindings={"metric": metric})], **extra)


async def test_lookup_records_scope_and_can_be_promoted(setup):
    engine, provider = setup
    run = await engine.start(CREDS, ME, recipe=None, question="Sales by department?", scope=SCOPE, goals=[goal()])
    run, result = await engine.step(CREDS, ME, run.id, lookup(goal_ids=["lookup"]))
    assert result.status == "success" and result.provides == ["metric_lookup"]
    assert result.interpretation == "descriptive" and not result.selections
    assert result.primary.data[0][CAT] == "B"
    assert result.primary.data[0][AMOUNT] == 10000000
    assert result.artifacts[0].data["population_complete"] is False
    assert run.query_attempts[0].spec.time.date_range == Q3
    assert run.query_attempts[0].status == "success"
    done = await engine.complete(ME, run.id, conclusion=RunConclusion(answer="Department B is highest.",
        findings=[RunFinding(text="Recorded sales", step_indices=[0])],
        goal_outcomes=[GoalOutcome(goal_id="lookup", status="supported", step_indices=[0])]))
    from decision_layer.recipes.from_run import runtime_recipe_from_run
    converted = runtime_recipe_from_run(done)
    assert converted.steps[0].method == "query.aggregate"
    assert not converted.steps[0].goal_ids and not converted.steps[0].exploration


async def test_omitted_period_never_queries(setup):
    engine, provider = setup
    run = await engine.start(CREDS, ME, recipe=None, question="Sales?", scope={})
    run, result = await engine.step(CREDS, ME, run.id, lookup())
    assert result.status == "needs_input" and provider.calls == 0 and not run.query_attempts


async def test_legacy_queries_and_new_failed_attempts_share_budget(setup, monkeypatch):
    engine, provider = setup
    engine.policy = ExecutionPolicy(max_queries=2)
    run = await engine.start(CREDS, ME, recipe=None, question="Sales?", scope=SCOPE)
    run, _ = await engine.step(CREDS, ME, run.id, lookup())
    run.query_attempts = []
    run.query_attempt_baseline = None
    await engine.store.save(run)
    async def fail(*args, **kwargs):
        raise RuntimeError("provider offline")
    monkeypatch.setattr(provider, "execute", fail)
    with pytest.raises(RuntimeError):
        await engine.step(CREDS, ME, run.id, lookup().model_copy(update={"id": "retry"}))
    with pytest.raises(RunLimitExceeded):
        await engine.step(CREDS, ME, run.id, lookup().model_copy(update={"id": "retry"}))


async def test_mcp_recipe_requires_selection_reason(setup):
    engine, _ = setup
    engine.recipes.save(recipe(), base_version=None)
    from decision_layer.runs.engine import AnalysisContractError
    with pytest.raises(AnalysisContractError):
        await engine.start(CREDS, ME, recipe="lookup-procedure", question="Sales?", scope=SCOPE,
                           origin="mcp", goals=[goal()])
async def test_unrelated_metric_cannot_supply_a_goals_capability(setup):
    engine, _ = setup
    run = await engine.start(CREDS, ME, recipe=None, question="Sales breakdown?", scope=SCOPE,
                             goals=[goal(capability="group_breakdown")])
    run, _ = await engine.step(CREDS, ME, run.id, lookup(goal_ids=["lookup"]))
    run, _ = await engine.step(CREDS, ME, run.id, PlanStep(method="query.drilldown",
        bindings={"metric": COUNT, "dimensions": [CAT]}, params={}, goal_ids=["lookup"]))
    with pytest.raises(InvalidBinding):
        await engine.complete(ME, run.id, conclusion=RunConclusion(answer="Unsupported combination",
            goal_outcomes=[GoalOutcome(goal_id="lookup", status="supported", step_indices=[0, 1])]))


async def test_historical_question_is_not_a_runtime_period_constraint(setup):
    engine, provider = setup
    rec = recipe().model_copy(update={"description": "Inspect 2001 first-half sales",
        "origin_runs": ["original"], "routing": recipe().routing.model_copy(update={"objective": ""})})
    engine.recipes.save(rec, None)
    candidates = await search_recipes(engine.recipes, provider, CREDS, "Inspect second-half sales", [goal()], {}, 5)
    candidate = candidates["candidates"][0]
    assert candidate["objective"] == ""
    assert candidate["source_question"] == rec.description
    assert candidate["reuse"]["period"] == {"binding": "runtime", "default": None, "fixed_method_periods": []}
    assert candidate["reuse"]["procedure"][0]["method"] == "query.aggregate"
    assert engine.recipes.get(rec.name).description == rec.description
    run = await engine.start(CREDS, ME, recipe=rec.name, question="Inspect second-half sales",
        scope={"date_range": ["2001-07-01", "2001-12-31"]}, origin="mcp", goals=[goal()],
        recipe_selection=RecipeSelection(reason="Same procedure with a different runtime period", goal_ids=["lookup"]))
    assert run.query_attempts[0].spec.time.date_range == ("2001-07-01", "2001-12-31")
    assert run.recipe_review[0].decision == "selected"


async def test_mcp_cannot_silently_skip_current_candidates(setup):
    from decision_layer.runs.engine import AnalysisContractError
    engine, provider = setup
    engine.recipes.save(recipe(), None)
    with pytest.raises(AnalysisContractError) as caught:
        await engine.start(CREDS, ME, recipe=None, question="Sales?", scope=SCOPE, origin="mcp", goals=[goal()])
    candidate = caught.value.details["candidates"][0]
    assert candidate["reuse"]["period"]["binding"] == "runtime"
    assert provider.calls == 0 and not await engine.list(ME)
    run = await engine.start(CREDS, ME, recipe=None, question="Sales?", scope=SCOPE, origin="mcp", goals=[goal()],
        recipe_review=[RecipeReview(recipe=candidate["recipe"], decision="skipped",
            reason="The question requires a different grouping order")])
    restored = await engine.store.get(run.id)
    assert restored.recipe_review[0].reason == "The question requires a different grouping order"
    assert restored.recipe_candidates[0]["recipe"] == candidate["recipe"]


def test_fixed_method_dates_remain_visible_and_blank_skip_reasons_fail():
    from pydantic import ValidationError
    from decision_layer.recipes.routing import reuse_contract
    rec = recipe(method="query.trend")
    rec.steps[0].params = {"current": ["2001-01-01", "2001-06-30"]}
    assert reuse_contract(rec)["period"]["fixed_method_periods"][0]["value"] == ["2001-01-01", "2001-06-30"]
    with pytest.raises(ValidationError):
        RecipeReview(recipe="recipe://lookup@1.0.0", decision="skipped", reason="   ")


async def test_failed_attempts_consume_budget_and_cannot_change_period(setup, monkeypatch):
    engine, provider = setup
    engine.policy = ExecutionPolicy(max_queries=1)
    async def fail(*args, **kwargs):
        raise RuntimeError("provider offline")
    monkeypatch.setattr(provider, "execute", fail)
    run = await engine.start(CREDS, ME, recipe=None, question="Sales?", scope=SCOPE)
    with pytest.raises(RuntimeError):
        await engine.step(CREDS, ME, run.id, lookup())
    recorded = await engine.store.get(run.id)
    assert recorded.query_attempts[0].status == "failed"
    assert recorded.error["code"] == "INTERNAL_ERROR"
    with pytest.raises(RunLimitExceeded):
        await engine.step(CREDS, ME, run.id, lookup())
    assert len((await engine.store.get(run.id)).query_attempts) == 1


async def test_same_step_request_is_idempotent_but_payload_changes_conflict(setup):
    engine, provider = setup
    run = await engine.start(CREDS, ME, recipe=None, question="Sales?", scope=SCOPE)
    first, repeated = await asyncio.gather(engine.step(CREDS, ME, run.id, lookup()), engine.step(CREDS, ME, run.id, lookup()))
    assert first[1].model_dump() == repeated[1].model_dump()
    assert provider.calls == 1 and len(repeated[0].steps) == 1
    changed = lookup(params={"limit": 2})
    with pytest.raises(InvalidBinding):
        await engine.step(CREDS, ME, run.id, changed)


async def test_query_cannot_hide_out_of_scope_measures_in_parameters(setup):
    engine, provider = setup
    rec = recipe(metric=RR)
    engine.recipes.save(rec, None)
    run = await engine.start(CREDS, ME, recipe=rec.name, question="Rate?", scope=SCOPE, origin="mcp", goals=[goal(metric=RR)],
        recipe_selection=RecipeSelection(reason="Inspect the requested rate", goal_ids=["lookup"]))
    calls = provider.calls
    _, result = await engine.step(CREDS, ME, run.id, PlanStep(id="hidden", method="query.aggregate", purpose="Hidden measure", goal_ids=["lookup"],
        bindings={"metric": RR}, params={"order_by": AMOUNT}))
    assert result.status == "refused"
    assert provider.calls == calls


async def test_candidates_exclude_unrelated_metrics_and_recheck_before_execution(setup):
    engine, provider = setup
    good, wrong = recipe(), recipe(name="wrong-rate", metric=RR)
    engine.recipes.save(good, None)
    engine.recipes.save(wrong, None)
    result = await search_recipes(engine.recipes, provider, CREDS, "Sales by department", [goal()], {}, 5)
    assert [item["name"] for item in result["candidates"]] == [good.name]
    assert result["candidates"][0]["semantic_meaning_verified"] is False
    with pytest.raises(InvalidBinding, match="cannot cover"):
        await engine.start(CREDS, ME, recipe=wrong.name, question="Sales?", scope=SCOPE, goals=[goal()])
    assert provider.calls == 0
    engine.recipes.delete(good.name, "1.0.0")
    from decision_layer.recipes.loader import UnknownRecipe
    with pytest.raises(UnknownRecipe):
        await engine.start(CREDS, ME, recipe=good.name, question="Sales?", scope=SCOPE, goals=[goal()])


async def test_partial_candidate_never_claims_causal_coverage(setup):
    engine, provider = setup
    rec = recipe()
    engine.recipes.save(rec, None)
    goals = [goal(), goal("effect", "new_causal_estimator", interpretation="causal_conditional")]
    result = await search_recipes(engine.recipes, provider, CREDS, "Sales and causal effect?", goals, {}, 5)
    candidate = result["candidates"][0]
    assert candidate["covered_goal_ids"] == ["lookup"] and candidate["conflicts"]
    with pytest.raises(InvalidBinding):
        await engine.start(CREDS, ME, recipe=rec.name, question="Both", scope=SCOPE, goals=goals)
    run = await engine.start(CREDS, ME, recipe=rec.name, question="Both", scope=SCOPE, goals=goals,
        origin="mcp", recipe_selection=RecipeSelection(reason="Only supports sales lookup", goal_ids=["lookup"]))
    assert run.recipe_invocation.completed
    with pytest.raises(InvalidBinding, match="required contract"):
        await engine.complete(ME, run.id, conclusion=RunConclusion(answer="Both answered",
            findings=[RunFinding(text="Sales", step_indices=[0])], goal_outcomes=[
                GoalOutcome(goal_id="lookup", status="supported", step_indices=[0]),
                GoalOutcome(goal_id="effect", status="supported", step_indices=[0])]))
    done = await engine.complete(ME, run.id, conclusion=RunConclusion(answer="Sales found; effect unavailable.",
        findings=[RunFinding(text="Sales", step_indices=[0])], goal_outcomes=[
            GoalOutcome(goal_id="lookup", status="supported", step_indices=[0]),
            GoalOutcome(goal_id="effect", status="unsupported", reason="No registered estimator", reason_code="method_missing")]))
    assert done.conclusion.goal_outcomes[1].status == "unsupported"


async def test_recipe_extension_keeps_metric_scope_fixed_policy_and_total_budget(setup):
    engine, provider = setup
    rec = recipe(method_parameters={"query.aggregate": {"fixed": {"limit": 5}}})
    engine.recipes.save(rec, None)
    run = await engine.start(CREDS, ME, recipe=rec.name, question="Sales and trend?", scope=SCOPE, origin="mcp", goals=[goal()],
        recipe_selection=RecipeSelection(reason="Inspect sales before follow-up", goal_ids=["lookup"]))
    assert run.steps[0].invocation_id == "recipe_1"
    with pytest.raises(InvalidBinding, match="fixed"):
        await engine.step(CREDS, ME, run.id, lookup(exploration=True, goal_ids=["lookup"], params={"limit": 10}))
    with pytest.raises(InvalidBinding, match="scope"):
        await engine.step(CREDS, ME, run.id, PlanStep(method="query.trend", purpose="Other metric", exploration=True, goal_ids=["lookup"], bindings={"metric": RR}))
    run, result = await engine.step(CREDS, ME, run.id, PlanStep(id="trend", method="query.trend", purpose="Sales over time", exploration=True, goal_ids=["lookup"], bindings={"metric": AMOUNT}))
    assert result.status == "success" and run.steps[1].invocation_id is None
    assert result.provides == ["time_series"]
    assert len(run.recipe_invocation.step_ids) == 1
    engine.policy = ExecutionPolicy(allow_recipe_extension=False)
    with pytest.raises(MethodNotAllowed):
        await engine.step(CREDS, ME, run.id, lookup(exploration=True, goal_ids=["lookup"]))


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
async def test_unsupported_question_is_stored_and_proposal_copies_only_public_text(setup, tmp_path, backend):
    engine, provider = setup
    if backend == "sqlite":
        engine.store = SqliteRunStore(str(tmp_path / "runs.db"))
    run = await engine.start(CREDS, ME, recipe=None, question="CONFIDENTIAL CUSTOMER QUESTION", scope={},
        origin="mcp", goals=[goal("new_method", "new_estimator")])
    done = await engine.complete(ME, run.id, conclusion=RunConclusion(answer="The requested estimator is unavailable.",
        goal_outcomes=[GoalOutcome(goal_id="new_method", status="unsupported", reason="Missing estimator", reason_code="method_missing")]))
    assert not done.steps and provider.calls == 0
    draft = method_proposal(done, MethodProposalRequest(goal_id="new_method", title="Estimator",
        public_question="Compare public synthetic groups", expected_result="An estimate with validation"), "haechangcho/decision-layer")
    assert not draft["submitted"] and "CONFIDENTIAL" not in json.dumps(draft)
    assert AMOUNT not in json.dumps(draft) and run.id not in json.dumps(draft)
    assert parse_qs(urlparse(draft["url"]).query)["body"] == [draft["body"]]
    persisted = await engine.store.get(run.id)
    assert persisted.conclusion.goal_outcomes[0].reason_code == "method_missing"
    with pytest.raises(InvalidBinding):
        method_proposal(done, MethodProposalRequest(goal_id="unknown", title="x", public_question="x", expected_result="x"), "a/b")


async def test_attach_one_recipe_after_lookup_preserves_identities_and_query_scope(setup):
    engine, provider = setup
    rec = recipe()
    engine.recipes.save(rec, None)
    run = await engine.start(CREDS, ME, recipe=None, question="Lookup and reuse", scope=SCOPE,
        origin="mcp", goals=[goal()], recipe_review=[RecipeReview(recipe="recipe://lookup-procedure@1.0.0",
            decision="skipped", reason="Inspect the metric first before attaching the procedure")])
    await engine.step(CREDS, ME, run.id, lookup(goal_ids=["lookup"]))
    run = await engine.use_recipe(CREDS, ME, run.id, rec.name,
        RecipeSelection(reason="Use the registered lookup procedure", goal_ids=["lookup"]), {})
    assert run.status == "open" and len(run.steps) == 2
    assert run.steps[0].invocation_id is None and run.steps[1].invocation_id == "recipe_1"
    assert run.steps[1].step.id == "recipe_1_first"
    assert run.recipe_snapshot.steps[0].id == "first"
    assert all(attempt.spec.time.date_range == Q3 for attempt in run.query_attempts)
    from decision_layer.runs.engine import RunBusy
    with pytest.raises(RunBusy):
        await engine.use_recipe(CREDS, ME, run.id, rec.name, run.recipe_selection, {})


async def test_fixed_trend_cannot_be_a_period_change_candidate(setup):
    engine, provider = setup
    engine.recipes.save(recipe(method="query.trend"), None)
    result = await search_recipes(engine.recipes, provider, CREDS, "Sales change", [goal(capability="period_change")], {}, 5)
    assert result["candidates"] == []


async def test_mcp_requires_goals_and_steps_cannot_skip_goal_links(setup):
    engine, provider = setup
    from decision_layer.runs.engine import AnalysisContractError
    with pytest.raises(AnalysisContractError):
        await engine.start(CREDS, ME, recipe=None, question="Sales?", scope=SCOPE, origin="mcp")
    run = await engine.start(CREDS, ME, recipe=None, question="Sales?", scope=SCOPE, origin="mcp", goals=[goal()])
    with pytest.raises(AnalysisContractError):
        await engine.step(CREDS, ME, run.id, lookup())
    assert provider.calls == 0


async def test_old_sqlite_document_reads_without_rewriting_history(setup, tmp_path):
    engine, provider = setup
    engine.store = SqliteRunStore(str(tmp_path / "old.db"))
    run = await engine.start(CREDS, ME, recipe=None, question="Old question", scope=SCOPE)
    old = run.model_dump(mode="json", exclude={"goals", "recipe_selection", "recipe_invocation", "query_attempts", "active_step", "interactive"})
    raw = json.dumps(old)
    engine.store._db.execute("UPDATE runs SET doc=? WHERE id=?", (raw, run.id))
    engine.store._db.commit()
    restored = await engine.store.get(run.id)
    assert restored.goals == [] and restored.query_attempts == []
    assert engine.store._db.execute("SELECT doc FROM runs WHERE id=?", (run.id,)).fetchone()[0] == raw


def test_preview_rejects_missing_period_and_records_governed_execution(cube_meta, tmp_path):
    provider = FakeProvider(cube_meta)
    app = create_app(Settings(cube_api_secret="test-secret-at-least-32-characters", allow_service_credentials=True,
        database_url="memory", recipes_dir=str(tmp_path)), provider)
    client = TestClient(app)
    spec = {"grain": "aggregate", "measures": [AMOUNT], "dimensions": [CAT]}
    assert client.post("/datasets/preview", json=spec).status_code == 422 and provider.calls == 0
    spec["time"] = {"dimension": DT, "date_range": list(Q3)}
    response = client.post("/datasets/preview", json=spec)
    assert response.status_code == 200, response.json()
    runs = client.get("/runs").json()
    executed = next(run for run in runs if run["steps"])
    assert executed["preview"] and executed["steps"][0]["step"]["method"] == "query.aggregate"
    assert executed["query_attempts"][0]["status"] == "success"
