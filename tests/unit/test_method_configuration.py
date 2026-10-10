import pytest
from pydantic import ValidationError

from decision_layer.core.models import InputSourcePolicy, MethodManifest, ParamSpec, PlanStep, Recipe
from decision_layer.methods import registry
from decision_layer.recipes.configuration import configure_step


def recipe(*methods):
    return Recipe(name="test", version="1.0.0", description="Test", mode="pipeline",
                  semantic_scope={"primary_metric": "cube://local/orders/value"},
                  steps=[PlanStep(id=f"step_{i+1}", method=name) for i, name in enumerate(methods)])


def test_defaults_connect_steps_without_remembering_values():
    original = recipe("query.drilldown", "query.drilldown", "query.peer_comparison")
    configured = original
    for index in range(3):
        configured = configure_step(configured, index)
    assert original.steps[0].bindings == {}
    assert configured.steps[0].bindings["metric"] == "$scope.primary_metric"
    assert configured.steps[0].params == {}
    assert configured.steps[1].params["drill_path"]["step_id"] == "step_1"
    assert configured.steps[2].params["subject"]["project"] == "condition"
    assert configured.steps[2].params["peers"]["project"] == "parents"
    assert configured.steps[2].params["peers"]["step_id"] == "step_2"


def test_missing_prior_target_becomes_required_input_without_default():
    configured = configure_step(recipe("query.peer_comparison"), 0)
    assert configured.steps[0].params["subject"] == {"source": "input", "name": "step_1_subject"}
    assert configured.inputs["step_1_subject"].required
    assert configured.inputs["step_1_subject"].default is None
    assert configured.inputs["step_1_subject"].label == "Who to compare"
    assert "peers" not in configured.steps[0].params


def test_explicit_settings_and_policies_are_not_changed():
    original = recipe("query.drilldown", "query.peer_comparison")
    original.steps[1].params = {"subject": [{"member": "cube://local/orders/store", "value": 12}], "min_count": 50}
    assert configure_step(original, 1).steps[1].params == original.steps[1].params
    data = original.model_dump()
    data["method_parameters"] = {"query.peer_comparison": {"fixed": {"subject": []}}}
    original = Recipe.model_validate(data)
    with pytest.raises(ValueError, match="Fixed parameter"):
        configure_step(original, 1, ["subject"])


def test_contract_rejects_invalid_default_and_semantic_type():
    manifest = registry.get("query.drilldown").manifest.model_dump()
    manifest["parameters"]["drill_path"]["source_policy"]["allowed"] = ["literal"]
    with pytest.raises(ValidationError, match="default source"):
        MethodManifest.model_validate(manifest)
    manifest = registry.get("query.drilldown").manifest.model_dump()
    manifest["parameters"]["top_n"]["semantic_kind"] = "dimension"
    with pytest.raises(ValidationError, match="semantic inputs"):
        MethodManifest.model_validate(manifest)


@pytest.mark.parametrize("patch", [{"type": "ref_list"}, {"semantic_role": "metric"}, {"semantic_kind": "measure"}])
def test_editor_parameter_requires_matching_scalar_semantic_input(patch):
    manifest = registry.get("query.drilldown").manifest.model_dump()
    manifest["parameters"]["next_dimension"].update(patch)
    with pytest.raises(ValidationError, match="editor_parameter"):
        MethodManifest.model_validate(manifest)


def test_editor_metadata_preserves_execution_defaults():
    drilldown = registry.get("query.drilldown").manifest
    assert drilldown.roles["dimensions"].editor_parameter == "next_dimension"
    assert drilldown.parameters["rank_by"].ui_group == "hidden"
    assert drilldown.parameters["rank_by"].default == "value"
    assert registry.get("query.trend").manifest.requires_period
    assert not drilldown.requires_period


def test_custom_method_uses_contract_not_parameter_names(monkeypatch):
    from decision_layer.methods.base import Method
    class Custom(Method):
        async def run(self, ctx, bindings, params):
            raise NotImplementedError

        manifest = registry.get("query.peer_comparison").manifest.model_copy(update={
            "name": "example.new_method", "parameters": {
                "chosen_group": ParamSpec(type="drill_path", required=True, label="Chosen group", source_policy=InputSourcePolicy(
                    allowed=["literal", "step", "input"], default="previous_result", project="condition"))}})
    monkeypatch.setitem(registry._methods, "example.new_method", Custom())
    configured = configure_step(recipe("query.drilldown", "example.new_method"), 1)
    assert configured.steps[1].params["chosen_group"]["step_id"] == "step_1"


def test_matching_groups_are_basic_and_linked_to_alternative_roles():
    manifest = registry.get("causal.cem").manifest
    assert manifest.roles["treatment"].exclusive_group == manifest.roles["treatment_measure"].exclusive_group
    for name in ("target", "comparison"):
        assert manifest.parameters[name].ui_group == "basic"
        assert manifest.parameters[name].semantic_role == "treatment"
    assert manifest.parameters["min_target_retention"].default == 0.5


@pytest.mark.parametrize("candidates,expected", [(1, "cube://local/orders/rows"), (0, None), (2, None)])
def test_unit_count_defaults_only_when_native_same_unit_count_is_unique(candidates, expected):
    from decision_layer.core.models import SemanticCatalog, SemanticObject
    average = "cube://local/orders/average"
    entity = "cube://local/orders/id"
    objects = [SemanticObject(ref=average, kind="measure", data_type="number", title="Average", metric_kind="average", entity=entity),
               SemanticObject(ref="cube://local/elsewhere/rows", kind="measure", data_type="number", title="Count elsewhere", metric_kind="count", entity="cube://local/elsewhere/id", count_measure="cube://local/elsewhere/rows"),
               SemanticObject(ref="cube://local/orders/distinct", kind="measure", data_type="number", title="Distinct", metric_kind="count", entity=entity)]
    for i in range(candidates):
        reference = "cube://local/orders/rows" if i == 0 else "cube://local/orders/filtered_rows"
        objects.append(SemanticObject(ref=reference, kind="measure", data_type="number", title="Rows", metric_kind="count", entity=entity, count_measure=reference))
    catalog = SemanticCatalog(provider="cube", instance="local", objects=objects)
    original = recipe("causal.cem")
    original.semantic_scope.primary_metric = average
    configured = configure_step(original, 0, catalog=catalog)
    assert configured.steps[0].bindings.get("sample_count") == expected
    original.steps[0].bindings["sample_count"] = "cube://local/orders/explicit"
    assert configure_step(original, 0, catalog=catalog).steps[0].bindings["sample_count"] == "cube://local/orders/explicit"
    assert "sample_count" not in configure_step(recipe("causal.cem"), 0, catalog=catalog).steps[0].bindings


@pytest.mark.parametrize("group", [{}, {"gte": 10, "lt": 5}, {"gte": float("inf")}, {"values": []}, {"values": [None]}, {"values": ["A"], "exclude": ["B"]}])
def test_group_definition_validation_rejects_invalid_ranges_and_values(group):
    from decision_layer.methods.base import InvalidBinding
    with pytest.raises(InvalidBinding):
        registry.resolve_params("causal.cem", {"target": group})


@pytest.mark.parametrize("group", [["A"], {"values": [True]}, {"exclude": ["A"]}, {"gte": 10}, {"gte": 0, "lt": 10}])
def test_group_definition_validation_preserves_typed_settings(group):
    assert registry.resolve_params("causal.cem", {"target": group})["target"] == group


def test_alternative_role_contract_and_recipe_validation():
    from decision_layer.recipes.authoring import RecipeEditError, validate_recipe
    manifest = registry.get("causal.cem").manifest.model_dump()
    manifest["roles"]["treatment_measure"]["exclusive_group"] = None
    with pytest.raises(ValidationError, match="exclusive_group"):
        MethodManifest.model_validate(manifest)
    original = recipe("causal.cem")
    original.steps[0].bindings = {"metric": "$scope.primary_metric", "conditions": ["cube://local/orders/channel"]}
    with pytest.raises(RecipeEditError, match="exactly one"):
        validate_recipe(original)
    original.steps[0].bindings["treatment"] = "cube://local/orders/targeted"
    validate_recipe(original)
    original.steps[0].bindings["treatment_measure"] = "cube://local/orders/value"
    with pytest.raises(RecipeEditError, match="exactly one"):
        validate_recipe(original)


def test_configuration_api_shares_defaults_and_requires_identity(cube_meta):
    from test_api import client
    document = {"recipe": recipe("query.drilldown", "query.peer_comparison").model_dump(), "step_index": 1}
    assert client(cube_meta).post("/recipes:configure-step", json=document).status_code == 401
    response = client(cube_meta, secret="s").post("/recipes:configure-step", json=document)
    assert response.status_code == 200, response.json()
    assert response.json()["steps"][1]["params"]["subject"]["step_id"] == "step_1"
    document["step_index"] = 5
    assert client(cube_meta, secret="s").post("/recipes:configure-step", json=document).status_code == 422
