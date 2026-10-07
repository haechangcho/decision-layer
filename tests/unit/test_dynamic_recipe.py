"""Reusable selection rules change with evidence, never with remembered literals."""
import pytest

from decision_layer.core.models import CallerInfo, MethodParameterPolicy, ParamSpec, PlanStep, Recipe, Result, SelectionOutput
from decision_layer.core.errors import ProviderAccessDenied
from decision_layer.methods import registry
from decision_layer.methods.base import InvalidBinding
from decision_layer.recipes.authoring import RecipeEditError, validate_recipe
from decision_layer.recipes.from_run import RunPromotionError, candidate_from_run, runtime_recipe_from_run
from decision_layer.recipes.loader import RecipeStore
from decision_layer.runs.engine import RunEngine
from decision_layer.runs.expressions import AmbiguousSelection, UnresolvedExpression, resolve
from decision_layer.runs.store import MemoryRunStore
from test_methods import CAT, CREDS, DT, Q3, RR, SELLER, FakeProvider, ctx


@pytest.fixture
def provider(cube_meta):
    return FakeProvider(cube_meta)


def source(step_id, project="path"):
    return {"source": "step", "step_id": step_id, "output": "ranked_groups", "select": "first", "project": project}


def procedure():
    return Recipe(name="highest-group", version="1.0.0", description="Compare the leading group's rate",
                  semantic_scope={"primary_metric": RR}, mode="pipeline", steps=[
        PlanStep(id="groups", method="query.drilldown", bindings={"metric": RR, "dimensions": [CAT, SELLER]}, params={"top_n": 1}),
        PlanStep(id="members", method="query.drilldown", bindings={"metric": RR, "dimensions": [CAT, SELLER]}, params={"drill_path": source("groups")}),
        PlanStep(id="comparison", method="query.peer_comparison", bindings={"metric": RR},
                 params={"subject": source("members", "condition"), "peers": source("members", "parents")})])


async def execute(provider, tmp_path, recipe=None):
    store = RecipeStore(tmp_path, "cube", "local")
    recipe = recipe or procedure()
    if not store.list():
        store.save(recipe, None)
    engine = RunEngine(provider, store, MemoryRunStore())
    return await engine.start(CREDS, CallerInfo(subject="analyst"), recipe=recipe.name, question="Find the leading group",
                              scope={"date_range": list(Q3)})


async def test_same_recipe_reselects_department_and_member_and_preserves_global_population(provider, tmp_path):
    first = await execute(provider, tmp_path)
    assert first.status == "completed"
    assert first.steps[1].step.params["drill_path"] == [{"member": CAT, "value": "A"}]
    assert first.steps[2].step.params["subject"] == [{"member": SELLER, "value": "S1"}]
    assert first.steps[2].step.params["peers"] == [{"member": CAT, "value": "A"}]
    assert first.plan.scope["filters"] == []
    assert first.steps[1].requested_step.params["drill_path"] == source("groups")
    assert first.steps[2].input_resolutions[0]["resolved"] == [{"member": SELLER, "value": "S1"}]
    assert first.plan.steps[1].params["drill_path"] == source("groups")
    counts = {}
    for row in provider.orders:
        if row[CAT] == "B" and Q3[0] <= row[DT] <= Q3[1]:
            key = row[SELLER]
            counts[key] = counts.get(key, 0) + 1
            row["returned"] = counts[key] <= (225 if key == "S6" else 175)
    second = await execute(provider, tmp_path)
    assert second.status == "completed"
    assert second.steps[1].step.params["drill_path"] == [{"member": CAT, "value": "B"}]
    assert second.steps[2].step.params["subject"] == [{"member": SELLER, "value": "S6"}]
    assert second.steps[2].step.params["peers"] == [{"member": CAT, "value": "B"}]
    assert second.steps[2].result.primary.data["rows"][1]["metric"] == 70
    assert second.steps[2].result.primary.data["rows"][2]["metric"] < 70
    assert first.steps[2].step.params["subject"][0]["value"] == "S1"


async def test_editor_defaults_execute_through_the_canonical_engine(provider, tmp_path):
    from decision_layer.recipes.configuration import configure_step
    authored = procedure()
    authored.steps[1].params = {}
    authored.steps[2].params = {}
    for index in range(3):
        authored = configure_step(authored, index)
    run = await execute(provider, tmp_path, authored)
    assert run.status == "completed"
    assert run.steps[2].step.params["subject"] == [{"member": SELLER, "value": "S1"}]
    assert run.steps[2].step.params["peers"] == [{"member": CAT, "value": "A"}]
    assert run.steps[2].requested_step.params["subject"]["source"] == "step"


async def test_promotion_preserves_rules_and_dependency_closure(provider, tmp_path):
    run = await execute(provider, tmp_path)
    candidate = candidate_from_run(run, [0, 1, 2])
    assert candidate.recipe.steps[1].params["drill_path"] == source("groups")
    assert candidate.recipe.steps[2].params["subject"] == source("members", "condition")
    assert candidate.recipe.default_scope.date_range is None
    assert candidate.recipe.steps[0].purpose_context == "procedure"
    assert candidate.recipe.semantic_scope.required_filters == []
    with pytest.raises(RunPromotionError, match="Include the earlier steps"):
        candidate_from_run(run, [1, 2])
    # Old pipeline records can recover rules from their immutable snapshot.
    for record in run.steps:
        record.requested_step = None
    assert candidate_from_run(run, [0, 1, 2]).recipe.steps[1].params["drill_path"] == source("groups")


async def test_promotion_marks_original_intent_without_rewriting_it(provider, tmp_path):
    run = await execute(provider, tmp_path)
    run.recipe_snapshot = None
    run.plan.recipe = None
    run.steps[0].requested_step.purpose = "Compare sales in July through September"
    candidate = candidate_from_run(run, [0, 1, 2])
    assert candidate.recipe.steps[0].purpose == "Compare sales in July through September"
    assert candidate.recipe.steps[0].purpose_context == "source_run"
    assert candidate.recipe.default_scope.date_range is None
    run.steps[0].requested_step.purpose_context = "procedure"
    assert candidate_from_run(run, [0, 1, 2]).recipe.steps[0].purpose_context == "procedure"


async def test_default_registration_builds_runtime_rules_without_copying_winner_values(provider, tmp_path):
    run = await execute(provider, tmp_path)
    run.recipe_snapshot = None
    for record in run.steps:
        record.requested_step = record.step.model_copy(deep=True)
    original = run.model_dump()
    recipe = runtime_recipe_from_run(run)
    assert recipe.steps[1].params["drill_path"] == source("groups")
    assert recipe.steps[2].params["subject"] == source("members", "condition")
    assert recipe.steps[2].params["peers"] == source("members", "parents")
    assert recipe.semantic_scope.required_filters == []
    assert run.model_dump() == original
    recipe.status = "published"
    replay = await execute(provider, tmp_path / "promoted", recipe)
    assert replay.steps[2].step.params["subject"] == [{"member": SELLER, "value": "S1"}]
    # Native declared query dimensions also support historical ordinary drilldowns.
    for record in run.steps:
        record.result.selections = {}
    assert runtime_recipe_from_run(run).steps[2].params["subject"] == source("members", "condition")


async def test_unconnected_target_becomes_required_runtime_input_without_literal_default(provider, tmp_path):
    run = await execute(provider, tmp_path)
    run.recipe_snapshot = None
    run.steps = [run.steps[2]]
    run.steps[0].requested_step = run.steps[0].step.model_copy(deep=True)
    recipe = runtime_recipe_from_run(run)
    assert recipe.steps[0].params["subject"] == {"source": "input", "name": "comparison_subject"}
    assert recipe.inputs["comparison_subject"].required
    assert recipe.inputs["comparison_subject"].default is None
    assert recipe.inputs["comparison_peers"].default is None


async def test_default_registration_preserves_explicit_fixed_method_policy(provider, tmp_path):
    recipe = procedure()
    fixed = {"subject": [{"member": SELLER, "value": "S1"}], "peers": [{"member": CAT, "value": "A"}]}
    recipe.method_parameters = {"query.peer_comparison": MethodParameterPolicy(fixed=fixed)}
    recipe.steps[2].params = fixed
    run = await execute(provider, tmp_path, recipe)
    promoted = runtime_recipe_from_run(run)
    assert promoted.steps[2].params["subject"] == fixed["subject"]
    assert promoted.steps[2].params["peers"] == fixed["peers"]


async def test_display_limit_does_not_limit_eligible_selection_and_terminal_groups_export(provider):
    result = await registry.run("query.drilldown", ctx(provider), {"metric": RR, "dimensions": [CAT]}, {"top_n": 1})
    output = result.selections["ranked_groups"]
    assert output.complete and len(output.candidates) == 2
    assert len(result.primary.data["rows"]) == 1
    assert result.primary.data["next_candidates"] == []
    assert resolve(source("first", "condition"), None, {"first": result}) == [{"member": CAT, "value": "A"}]


def result(scores, complete=True):
    return Result(status="success", selections={"ranked_groups": SelectionOutput(complete=complete, rank_by="metric", direction="desc",
        candidates=[{"path": [{"member": CAT, "value": str(i)}], "score": score} for i, score in enumerate(scores)])})


@pytest.mark.parametrize("earlier", [result([], True), result([10], False), Result(status="refused"), Result(status="failed")])
def test_unavailable_selection_never_falls_back_to_previous_values(earlier):
    with pytest.raises(UnresolvedExpression):
        resolve(source("groups"), None, {"groups": earlier})


def test_full_precision_ties_and_projection_validation():
    with pytest.raises(AmbiguousSelection):
        resolve(source("groups"), None, {"groups": result([10, 10])})
    assert resolve(source("groups"), None, {"groups": result([1.0000002, 1.0000001])})[0]["value"] == "0"
    with pytest.raises(UnresolvedExpression):
        resolve({**source("groups"), "project": "sql"}, None, {"groups": result([10])})


async def test_truncated_provider_population_refuses_selection(provider, tmp_path, monkeypatch):
    monkeypatch.setattr("decision_layer.methods.query.drilldown.MAX_GROUPS", 2)
    run = await execute(provider, tmp_path)
    assert run.status == "failed" and len(run.steps) == 2
    assert not run.steps[0].result.selections["ranked_groups"].complete
    assert run.steps[1].result.provenance.queries == []


async def test_tie_requires_input_without_executing_next_query(provider, tmp_path):
    for row in provider.orders:
        if row[CAT] == "B" and Q3[0] <= row[DT] <= Q3[1]:
            row["returned"] = True
    run = await execute(provider, tmp_path)
    assert run.status == "open" and len(run.steps) == 3
    assert run.steps[2].result.status == "needs_input"
    assert len(run.steps[2].result.needs_input["candidates"]) == 2
    assert run.steps[2].result.provenance.queries == []


async def test_explicit_fixed_group_stays_fixed_and_is_flagged_for_review(provider, tmp_path):
    recipe = procedure()
    recipe.steps[2].params = {"subject": [{"member": SELLER, "value": "S1"}], "peers": []}
    run = await execute(provider, tmp_path, recipe)
    assert run.steps[2].step.params["subject"] == [{"member": SELLER, "value": "S1"}]
    assert any("fixed group" in note for note in candidate_from_run(run, [0, 1, 2]).review_notes)


async def test_declared_runtime_inputs_are_typed_and_preserved(provider, tmp_path):
    recipe = procedure()
    recipe.inputs = {"subject": ParamSpec(type="drill_path", required=True)}
    recipe.steps[2].params["subject"] = {"source": "input", "name": "subject"}
    validate_recipe(recipe)
    recipes = RecipeStore(tmp_path, "cube", "local")
    recipes.save(recipe, None)
    engine = RunEngine(provider, recipes, MemoryRunStore())
    with pytest.raises(InvalidBinding):
        await engine.start(CREDS, CallerInfo(subject="a"), recipe=recipe.name, question="Test", scope={})
    with pytest.raises(InvalidBinding):
        await engine.start(CREDS, CallerInfo(subject="a"), recipe=recipe.name, question="Test", scope={"inputs": {"subject": "S1"}})
    run = await engine.start(CREDS, CallerInfo(subject="a"), recipe=recipe.name, question="Test",
                             scope={"date_range": list(Q3), "inputs": {"subject": [{"member": SELLER, "value": "S1"}]}})
    assert run.status == "completed"
    assert run.steps[2].input_resolutions[0]["source"]["source"] == "input"
    assert candidate_from_run(run, [0, 1, 2]).recipe.inputs == recipe.inputs


@pytest.mark.parametrize("change", ["forward", "output", "type", "fixed"])
def test_invalid_source_contracts_are_rejected_before_saving(change):
    recipe = procedure()
    if change == "forward":
        recipe.steps[1].params["drill_path"] = source("comparison")
    elif change == "output":
        recipe.steps[1].params["drill_path"]["output"] = "arbitrary_json"
    elif change == "type":
        recipe.steps[1].params["top_n"] = source("groups")
    else:
        recipe.method_parameters = {"query.drilldown": MethodParameterPolicy(fixed={"drill_path": source("groups")})}
    with pytest.raises(RecipeEditError):
        validate_recipe(recipe)


async def test_current_credentials_revalidated_before_downstream_execution(provider, tmp_path):
    engine = RunEngine(provider, RecipeStore(tmp_path, "cube", "local"), MemoryRunStore())
    caller = CallerInfo(subject="analyst")
    run = await engine.start(CREDS, caller, recipe=None, question="Investigate", scope={"date_range": list(Q3)})
    await engine.step(CREDS, caller, run.id, procedure().steps[0])
    calls = provider.calls
    from decision_layer.semantic.credentials import RequestCredentials
    with pytest.raises(ProviderAccessDenied):
        await engine.step(RequestCredentials("bad"), caller, run.id, procedure().steps[1])
    assert provider.calls == calls
