import pytest

from decision_layer.core.models import Run
from decision_layer.recipes.from_run import RunPromotionError, candidate_from_run, runtime_recipe_from_run


METRIC = "cube://local/ecom_order/return_rate"
DIMENSION = "cube://local/ecom_order/channel"


def run():
    def step(method, bindings, params, sources):
        return {"step": {"method": method, "purpose": "Recorded purpose", "bindings": bindings, "params": params},
                "method": f"method://{method}@1.0.0", "result": {"status": "success"},
                "parameter_sources": sources,
                "started_at": "2026-10-01T10:00:00Z", "finished_at": "2026-10-01T10:00:01Z"}

    return Run.model_validate({"id": "run_12345678", "plan": {"scope": {"date_range": ["2026-06-01", "2026-06-30"],
                              "filters": [{"member": DIMENSION, "operator": "equals", "values": ["retail"]}]}},
        "steps": [step("query.trend", {"metric": METRIC}, {"granularity": "month", "current": ["2026-06-01", "2026-06-30"]},
                       {"granularity": "method_default", "current": "request"}),
                  step("query.drilldown", {"metric": METRIC, "dimensions": [DIMENSION]},
                       {"top_n": 5, "min_count": 30, "drill_path": [{"member": DIMENSION, "value": "retail"}]},
                       {"top_n": "request", "min_count": "method_default", "drill_path": "request"})]})


def test_selected_run_steps_preserve_recorded_settings_and_scope():
    source = run()
    candidate = candidate_from_run(source, [0, 1])
    recipe = candidate.recipe
    assert recipe.status == "draft" and recipe.mode == "pipeline"
    assert recipe.semantic_scope.primary_metric == METRIC
    assert recipe.semantic_scope.required_filters == []
    assert recipe.default_scope.date_range is None
    assert candidate.review_notes
    for original, copied in zip(source.steps, recipe.steps):
        assert copied.params == original.step.params
        assert copied.bindings == original.step.bindings
        assert copied.purpose == original.step.purpose
        assert copied.method_version == original.method.rpartition("@")[2]


def test_preview_and_unsuccessful_steps_cannot_be_promoted():
    current = run()
    with pytest.raises(RunPromotionError):
        candidate_from_run(current.model_copy(update={"preview": True}), [0])
    with pytest.raises(RunPromotionError):
        candidate_from_run(current, [1, 0])
    current.steps[0].result.status = "refused"
    with pytest.raises(RunPromotionError):
        candidate_from_run(current, [0])


def test_calculated_validation_refusal_can_be_saved_without_weakening_validation():
    current = run()
    result = current.steps[0].result
    result.status = "refused"
    from decision_layer.core.models import Artifact, ValidationResult
    result.primary = Artifact(type="estimate", title="Comparison", data={"difference": 3})
    result.validation = [ValidationResult(validator="comparability", status="fail",
                                        code="NOT_COMPARABLE", message="Insufficient overlap")]
    candidate = candidate_from_run(current, [0, 1])
    assert len(candidate.recipe.steps) == 2
    assert any("did not pass validation" in note for note in candidate.review_notes)
    assert candidate.recipe.steps[0].params == current.steps[0].step.params
    assert len(runtime_recipe_from_run(current).steps) == 2
    assert result.status == "refused" and result.validation[0].status == "fail"


@pytest.mark.parametrize("status,has_primary,has_failure", [
    ("needs_input", True, True), ("refused", False, True), ("refused", True, False),
])
def test_incomplete_or_unexplained_refusals_still_require_editing(status, has_primary, has_failure):
    from decision_layer.core.models import Artifact, ValidationResult
    current = run()
    result = current.steps[0].result
    result.status = status
    result.primary = Artifact(type="estimate", data={}) if has_primary else None
    result.validation = [ValidationResult(validator="test", status="fail", code="FAIL", message="fail")] if has_failure else []
    with pytest.raises(RunPromotionError):
        candidate_from_run(current, [0])
