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


def test_configuration_api_shares_defaults_and_requires_identity(cube_meta):
    from test_api import client
    document = {"recipe": recipe("query.drilldown", "query.peer_comparison").model_dump(), "step_index": 1}
    assert client(cube_meta).post("/recipes:configure-step", json=document).status_code == 401
    response = client(cube_meta, secret="s").post("/recipes:configure-step", json=document)
    assert response.status_code == 200, response.json()
    assert response.json()["steps"][1]["params"]["subject"]["step_id"] == "step_1"
    document["step_index"] = 5
    assert client(cube_meta, secret="s").post("/recipes:configure-step", json=document).status_code == 422
