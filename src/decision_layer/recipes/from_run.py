"""Build an editable Recipe candidate from selected, recorded Run steps."""
from __future__ import annotations

from pydantic import BaseModel

from ..core.errors import DecisionLayerError
from ..core.models import PlanStep, Recipe, Run, SemanticScope
from ..i18n import _
from .authoring import validate_recipe


class RunPromotionError(DecisionLayerError):
    code = "RUN_PROMOTION_INVALID"
    http_status = 422


class RecipeCandidate(BaseModel):
    recipe: Recipe
    source_run_id: str
    selected_steps: list[int]
    review_notes: list[str]


def candidate_from_run(run: Run, indices: list[int]) -> RecipeCandidate:
    if run.preview:
        raise RunPromotionError(_("A preview cannot be promoted. Save or run the analysis first."))
    if not indices or indices != sorted(set(indices)) or any(i < 0 or i >= len(run.steps) for i in indices):
        raise RunPromotionError(_("Select existing Run steps in execution order."))
    if len(indices) > 12:
        raise RunPromotionError(_("Select at most 12 steps for a Recipe."))

    selected = [run.steps[i] for i in indices]
    if any(record.result.status != "success" for record in selected):
        raise RunPromotionError(_("Only successful Run steps can become a Recipe draft."))
    metrics = [record.step.bindings.get("metric") for record in selected]
    if not isinstance(metrics[0], str) or not metrics[0].startswith("cube://"):
        raise RunPromotionError(_("The first selected step needs a governed metric."))
    primary = metrics[0]
    related = list(dict.fromkeys(value for value in metrics[1:] if isinstance(value, str) and value.startswith("cube://") and value != primary))
    steps: list[PlanStep] = []
    review_notes = [_("The Run's period and shared filters were not copied. Choose them when executing the Recipe.")]
    for index, record in enumerate(selected):
        params = {name: value for name, value in record.step.params.items()
                  if record.parameter_sources.get(name) not in ("method_default", None)
                  and name not in ("current", "comparison")}
        if params.get("drill_path"):
            review_notes.append(_("Step {step} has a fixed drill path from the Run. Review it before publishing.", step=index + 1))
        steps.append(PlanStep(id=f"step_{index + 1}", method=record.step.method,
                              bindings=record.step.bindings, params=params))
    recipe = Recipe(name=f"analysis-{run.id[-8:]}", version="1.0.0", status="draft",
                    description=run.plan.question or _("Analysis from Run {run_id}", run_id=run.id),
                    origin_runs=[run.id],
                    semantic_scope=SemanticScope(primary_metric=primary, related_metrics=related),
                    mode="pipeline", steps=steps)
    validate_recipe(recipe)
    return RecipeCandidate(recipe=recipe, source_run_id=run.id, selected_steps=indices, review_notes=review_notes)
