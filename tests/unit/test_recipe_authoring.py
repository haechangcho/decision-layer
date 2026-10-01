from pathlib import Path

import pytest

from decision_layer.core.models import Recipe
from decision_layer.recipes.authoring import RecipeConflict, RecipeEditError
from decision_layer.recipes.loader import RecipeStore, parse_recipe


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
