"""Build an editable Recipe candidate from selected, recorded Run steps."""
from __future__ import annotations

from pydantic import BaseModel

from ..core.errors import DecisionLayerError
from ..core.ids import is_semantic_ref
from ..core.models import ParamSpec, PlanStep, Recipe, Run, RunDefaults, SemanticScope, Result
from ..i18n import _
from .authoring import validate_recipe
from ..methods import registry
from ..runs.expressions import is_dynamic


class RunPromotionError(DecisionLayerError):
    code = "RUN_PROMOTION_INVALID"
    http_status = 422


class RecipeCandidate(BaseModel):
    recipe: Recipe
    source_run_id: str
    selected_steps: list[int]
    review_notes: list[str]


def reusable_result(result: Result) -> bool:
    # A completed calculation rejected by validators is still a reusable procedure.
    # Refusals without an analytical output (contracts, budgets, missing data) are not.
    return result.status == "success" or (
        result.status == "refused" and result.primary is not None
        and any(item.status == "fail" for item in result.validation)
    )


def candidate_from_run(run: Run, indices: list[int]) -> RecipeCandidate:
    if run.preview:
        raise RunPromotionError(_("A preview cannot be promoted. Save or run the analysis first."))
    if not indices or indices != sorted(set(indices)) or any(i < 0 or i >= len(run.steps) for i in indices):
        raise RunPromotionError(_("Select existing Run steps in execution order."))
    if len(indices) > 12:
        raise RunPromotionError(_("Select at most 12 steps for a Recipe."))

    selected = [run.steps[i] for i in indices]
    if any(not reusable_result(record.result) for record in selected):
        raise RunPromotionError(_("Only calculated Run steps can become a Recipe. Steps awaiting input or refused before an analytical output need editing."))
    metrics = [record.step.bindings.get("metric") for record in selected]
    if not is_semantic_ref(metrics[0]):
        raise RunPromotionError(_("The first selected step needs a governed metric."))
    primary = metrics[0]
    related = list(dict.fromkeys(value for value in metrics[1:] if is_semantic_ref(value) and value != primary))
    steps: list[PlanStep] = []
    review_notes = []
    for index, record in enumerate(selected):
        if record.result.status == "refused":
            review_notes.append(f"{record.step.id or index + 1}: the calculation did not pass validation in this Run. Its settings and validation thresholds are preserved; saving does not endorse the result or add a fallback branch.")
        original = record.requested_step
        if original is None and run.recipe_snapshot and record.step.id:
            original = next((step for step in run.recipe_snapshot.steps if step.id == record.step.id), None)
        original = original or record.step
        params = {**record.step.params, **original.params}
        manifest = registry.get(record.step.method).manifest
        for name, spec in manifest.parameters.items():
            value = params.get(name)
            if spec.type == "drill_path" and value and not is_dynamic(value):
                review_notes.append(f"{original.id or index + 1}.{name}: fixed group values require review; the original selection rule is not recorded.")
            if spec.type == "date_range" and value and not is_dynamic(value):
                review_notes.append(f"{original.id or index + 1}.{name}: this fixed period will be reused on every execution.")
        steps.append(PlanStep(id=original.id or f"step_{index + 1}", method=record.step.method,
                              method_version=record.method.rpartition("@")[2] or None,
                              purpose=original.purpose,
                              purpose_context=original.purpose_context or ("procedure" if run.recipe_snapshot and not run.recipe_snapshot.origin_runs else "source_run"),
                              bindings=original.bindings, params=params))
    if run.plan.scope.get("date_range") or run.plan.scope.get("filters"):
        review_notes.append("Run period and shared filters are execution context, not automatically fixed Recipe rules. Review the scope before publishing.")
    recipe = Recipe(name=f"analysis-{run.id[-8:].lower()}", version="1.0.0", status="draft",
                    description=run.plan.question or _("Analysis from Run {run_id}", run_id=run.id),
                    origin_runs=[run.id],
                    semantic_scope=SemanticScope(primary_metric=primary, related_metrics=related,
                                                 preferred_dimensions=run.recipe_snapshot.semantic_scope.preferred_dimensions if run.recipe_snapshot else [],
                                                 required_filters=run.recipe_snapshot.semantic_scope.required_filters if run.recipe_snapshot else []),
                    default_scope=run.recipe_snapshot.default_scope.model_copy(deep=True) if run.recipe_snapshot and run.recipe_snapshot.default_scope else RunDefaults(time_dimension=run.plan.scope.get("time_dimension")),
                    inputs=run.recipe_snapshot.inputs if run.recipe_snapshot else {},
                    method_parameters={name: policy for name, policy in (run.recipe_snapshot.method_parameters.items() if run.recipe_snapshot else [])
                                       if name in {step.method for step in steps}},
                    validators=run.recipe_snapshot.validators if run.recipe_snapshot else [],
                    mode="pipeline", steps=steps)
    recipe.limits.max_queries = max(recipe.limits.max_queries, sum(len(record.result.provenance.queries) for record in selected))
    try:
        validate_recipe(recipe)
    except DecisionLayerError as e:
        raise RunPromotionError("Include the earlier steps required by the selected procedure.", cause=e.message, **e.details) from e
    return RecipeCandidate(recipe=recipe, source_run_id=run.id, selected_steps=indices, review_notes=review_notes)


def runtime_recipe_from_run(run: Run) -> Recipe:
    """Construct a new runtime-selection procedure, not a reconstruction of past intent."""
    recipe = candidate_from_run(run, list(range(len(run.steps)))).recipe.model_copy(deep=True)
    paths: dict[str, list[str]] = {}
    for index, step in enumerate(recipe.steps):
        record = run.steps[index]
        manifest = registry.get(step.method).manifest
        policy = recipe.method_parameters.get(step.method)
        for name, spec in manifest.parameters.items():
            value = step.params.get(name)
            if spec.type != "drill_path" or not value or is_dynamic(value) or (policy and name in policy.fixed):
                continue
            members = [condition["member"] for condition in value]
            matches = []
            # Peer conditions follow the subject's branch, not the global Run scope.
            subject = step.params.get("subject")
            if name == "peers" and isinstance(subject, dict) and subject.get("source") == "step":
                origin = subject["step_id"]
                if paths.get(origin, [])[:-1] == members:
                    matches.append((origin, "parents"))
            if not matches:
                for origin, path in paths.items():
                    project = "condition" if name == "subject" else "path"
                    projected = path[-1:] if project == "condition" else path
                    if projected == members:
                        matches.append((origin, project))
            if not matches:
                input_name = f"{step.id}_{name}"
                while input_name in recipe.inputs:
                    input_name += "_runtime"
                recipe.inputs[input_name] = ParamSpec(type=spec.type, required=True,
                    description=f"Select {name} at execution using semantic dimensions: {', '.join(members)}")
                step.params[name] = {"source": "input", "name": input_name}
                continue
            origin, project = matches[-1]
            step.params[name] = {"source": "step", "step_id": origin, "output": "ranked_groups", "select": "first", "project": project}
        if "ranked_groups" not in manifest.selection_outputs:
            continue
        output = record.result.selections.get("ranked_groups")
        if output and output.candidates:
            paths[step.id] = [condition.member for condition in output.candidates[0].path]
        elif step.method == "query.drilldown" and not record.step.params.get("current") and not record.step.params.get("comparison"):
            # Older ordinary drilldowns lack exported results. Their native query
            # contract still declares the path's dimensions; never match winner values.
            used = [condition["member"] for condition in record.step.params.get("drill_path", [])]
            dimensions = record.step.bindings.get("dimensions", [])
            if isinstance(dimensions, str):
                dimensions = [dimensions]
            dimension = record.step.params.get("next_dimension") or next((member for member in dimensions if member not in used), None)
            if is_semantic_ref(dimension):
                paths[step.id] = [*used, dimension]
    validate_recipe(recipe)
    return recipe
