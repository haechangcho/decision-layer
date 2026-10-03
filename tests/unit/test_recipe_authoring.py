from pathlib import Path

import pytest

from decision_layer.core.models import Recipe
from decision_layer.recipes.authoring import RecipeConflict, RecipeEditError
from decision_layer.recipes.loader import RecipeStore, UnknownRecipe, parse_recipe
from decision_layer.methods import registry
from decision_layer.methods.base import InvalidBinding


def recipe():
    return Recipe.model_validate({
        "name": "orders-test", "version": "1.0.0", "description": "Test recipe",
        "semantic_scope": {"primary_metric": "cube://local/ecom_order/return_rate"},
        "mode": "pipeline", "steps": [{"id": "trend", "method": "query.trend",
            "bindings": {"metric": "$scope.primary_metric"}, "params": {"granularity": "month"}}],
    })


def test_recipe_save_creates_an_immutable_yaml_version_and_reloads(tmp_path: Path):
    store = RecipeStore(tmp_path, "cube", "local")
    first = store.save(recipe(), None)
    assert store.get("orders-test") == first
    second = first.model_copy(update={"version": "1.0.1", "description": "Changed"})
    store.save(second, "1.0.0")
    assert store.get("orders-test").version == "1.0.1"
    with pytest.raises(RecipeConflict):
        store.save(second, "1.0.0")
    loaded = RecipeStore(tmp_path, "cube", "local").get("orders-test")
    assert loaded.version == "1.0.1" and loaded.description == "Changed"


def test_draft_is_not_listed_or_executable_until_published(tmp_path: Path):
    store = RecipeStore(tmp_path, "cube", "local")
    draft = recipe().model_copy(update={"status": "draft"})
    store.save(draft, None)
    assert store.list() == []
    assert store.get("orders-test", include_drafts=True).version == "1.0.0"
    with pytest.raises(UnknownRecipe, match="Unknown recipe"):
        store.get("orders-test")
    with pytest.raises(UnknownRecipe, match="has no version"):
        store.get("orders-test@1.0.0")

    published = store.publish("orders-test", "1.0.0")
    assert published.version == "1.0.1" and published.status == "published"
    assert store.list() == [published]
    assert store.get("orders-test") == published
    assert RecipeStore(tmp_path, "cube", "local").get("orders-test") == published
    with pytest.raises(RecipeConflict):
        store.publish("orders-test", "1.0.0")

    next_draft = published.model_copy(update={"version": "1.0.2", "status": "draft"})
    store.save(next_draft, "1.0.1")
    assert store.get("orders-test").version == "1.0.1"
    assert store.get("orders-test", include_drafts=True).version == "1.0.2"


def test_recipe_validation_rejects_unknown_methods_and_forward_step_refs():
    store = RecipeStore(None, "cube", "local")
    invalid_method = recipe().model_copy(update={"steps": [recipe().steps[0].model_copy(update={"method": "query.nope"})]})
    with pytest.raises(RecipeEditError):
        store.save(invalid_method, None)
    forward = recipe().model_copy(update={"steps": [recipe().steps[0].model_copy(update={"params": {"drill_path": "$steps.later.primary.data.path"}})]})
    with pytest.raises(RecipeEditError):
        store.save(forward, None)


def test_recipe_save_is_disabled_without_a_configured_directory():
    with pytest.raises(RecipeEditError, match="DL_RECIPES_DIR"):
        RecipeStore(None, "cube", "local").save(recipe(), None)


@pytest.mark.parametrize("method,params", [
    ("query.drilldown", {"top_n": 0}),
    ("query.drilldown", {"min_count": -1}),
    ("query.drilldown", {"top_n": "10"}),
    ("query.drilldown", {"top_n": None}),
    ("query.trend", {"vs_previous": "false"}),
    ("query.trend", {"current": ["2026-10-02", "2026-10-01"]}),
    ("causal.cem", {"min_target_retention": 1.5}),
])
def test_manifest_parameters_reject_invalid_types_and_bounds(method, params):
    with pytest.raises(InvalidBinding):
        registry.resolve_params(method, params)


def test_recipe_parameter_policy_is_validated_before_save(tmp_path: Path):
    base = recipe().model_dump()
    base["method_parameters"] = {"query.trend": {"fixed": {"granularity": "week"},
                                                     "runtime_allowed": ["vs_previous"]}}
    with pytest.raises(RecipeEditError, match="conflicts") as error:
        RecipeStore(tmp_path, "cube", "local").save(Recipe.model_validate(base), None)
    assert error.value.details["field"] == "steps[0].params.granularity"

    base["steps"][0]["params"] = {"granularity": "week"}
    saved = RecipeStore(tmp_path, "cube", "local").save(Recipe.model_validate(base), None)
    assert saved.method_parameters["query.trend"].fixed == {"granularity": "week"}

    base["method_parameters"]["query.trend"]["fixed"] = {"granularity": "year"}
    with pytest.raises(RecipeEditError):
        RecipeStore(tmp_path, "cube", "local").save(Recipe.model_validate(base), None)
