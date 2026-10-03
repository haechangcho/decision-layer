import pytest

from decision_layer.core.models import Run
from decision_layer.recipes.from_run import RunPromotionError, candidate_from_run


METRIC = "cube://local/ecom_order/return_rate"
DIMENSION = "cube://local/ecom_order/channel"


def run():
    def step(method, bindings, params, sources):
        return {"step": {"method": method, "bindings": bindings, "params": params},
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


def test_selected_run_steps_make_a_reviewable_draft_without_scope_or_defaults():
    candidate = candidate_from_run(run(), [0, 1])
    recipe = candidate.recipe
    assert recipe.status == "draft" and recipe.mode == "pipeline"
    assert recipe.semantic_scope.primary_metric == METRIC
    assert recipe.semantic_scope.required_filters == []
    assert recipe.steps[0].params == {}
    assert recipe.steps[1].params == {"top_n": 5, "drill_path": [{"member": DIMENSION, "value": "retail"}]}
    assert len(candidate.review_notes) == 2


def test_preview_and_unsuccessful_steps_cannot_be_promoted():
    current = run()
    with pytest.raises(RunPromotionError):
        candidate_from_run(current.model_copy(update={"preview": True}), [0])
    with pytest.raises(RunPromotionError):
        candidate_from_run(current, [1, 0])
    current.steps[0].result.status = "refused"
    with pytest.raises(RunPromotionError):
        candidate_from_run(current, [0])
