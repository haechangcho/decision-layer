"""Structural Recipe compatibility; text relevance remains caller judgement."""
import re

from ..core.ids import is_semantic_ref, recipe_ref
from ..core.models import AnalysisGoal, Recipe
from ..methods.base import InvalidBinding, registry
from ..runs.expressions import is_dynamic


def reuse_contract(recipe: Recipe) -> dict:
    procedure, fixed_periods = [], []
    for step in recipe.steps:
        manifest = registry.get(step.method).manifest
        policy = recipe.method_parameters.get(step.method)
        params = {**step.params, **(policy.fixed if policy else {})}
        for name, spec in manifest.parameters.items():
            value = params.get(name)
            if spec.type == "date_range" and value and not is_dynamic(value):
                fixed_periods.append({"step_id": step.id, "parameter": name, "value": value})
        procedure.append({"id": step.id, "method": step.method, "label": manifest.label,
            "bindings": step.bindings, "settings": params,
            "purpose": step.purpose if step.purpose_context == "procedure" or not recipe.origin_runs else None,
            "source_purpose": step.purpose if step.purpose_context == "source_run" or
                (recipe.origin_runs and step.purpose_context is None) else None})
    return {"period": {"binding": "runtime", "default": recipe.default_scope.model_dump(mode="json")
                       if recipe.default_scope else None, "fixed_method_periods": fixed_periods},
            "required_filters": [item.model_dump(mode="json") for item in recipe.semantic_scope.required_filters],
            "procedure": procedure, "allowed_methods": recipe.allowed_methods}


def semantic_refs(value):
    if isinstance(value, str):
        return {value} if is_semantic_ref(value) else set()
    if isinstance(value, dict):
        return set().union(*(semantic_refs(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(semantic_refs(item) for item in value))
    return set()


def compatibility(recipe: Recipe, goals: list[AnalysisGoal], inputs: dict) -> dict:
    methods = [registry.get(name).manifest for name in
               (recipe.allowed_methods if recipe.mode == "investigation" else {step.method for step in recipe.steps})]
    if recipe.mode == "pipeline":
        provided = set()
        for step in recipe.steps:
            method = registry.get(step.method).manifest
            policy = recipe.method_parameters.get(step.method)
            params = {**{name: spec.default for name, spec in method.parameters.items()}, **step.params,
                      **(policy.fixed if policy else {})}
            provided.update(method.result_capabilities(params))
    else:
        provided = set().union(*(set(manifest.provides) for manifest in methods))
    available_refs = semantic_refs(recipe.model_dump(mode="json"))
    measures = {recipe.semantic_scope.primary_metric, *recipe.semantic_scope.related_metrics}
    conflicts, covered = [], []
    for goal in goals:
        # Metric scope and explicit dimensions must match; text similarity cannot override them.
        if not set(goal.semantic_refs) <= available_refs or not set(goal.required_capabilities) <= provided:
            conflicts.append({"goal_id": goal.id, "code": "RECIPE_SCOPE_MISMATCH"})
        elif goal.interpretation != "descriptive" and not any(m.interpretation == goal.interpretation for m in methods):
            conflicts.append({"goal_id": goal.id, "code": "INTERPRETATION_MISMATCH"})
        else:
            covered.append(goal.id)
    missing = [name for name, spec in recipe.inputs.items()
               if spec.required and spec.default is None and inputs.get(name) is None]
    if not missing:
        try:
            registry.input_values(recipe.inputs, inputs)
        except InvalidBinding:
            conflicts.append({"code": "INVALID_RUNTIME_INPUT"})
    return {"recipe": recipe_ref(recipe.name, recipe.version), "covered_goal_ids": covered,
            "conflicts": conflicts, "missing_inputs": missing,
            "compatibility": "conflict" if conflicts else "candidate" if goals else "unknown",
            "provided_capabilities": sorted(provided), "metrics": sorted(measures),
            "semantic_meaning_verified": False}


async def search_recipes(store, provider, credentials, question, goals, inputs, limit):
    catalog = await provider.discover(credentials)
    visible = {obj.ref for obj in catalog.objects if obj.public}
    requested = {ref for goal in goals for ref in goal.semantic_refs}
    if not requested <= visible:
        raise InvalidBinding("Some requested semantic objects are unavailable.")
    tokens = set(re.findall(r"\w+", question.casefold()))
    candidates = []
    for recipe in store.list():
        if not semantic_refs(recipe.model_dump(mode="json")) <= visible:
            continue
        check = compatibility(recipe, goals, inputs)
        if goals and not check["covered_goal_ids"]:
            continue
        text = " ".join([recipe.name, recipe.description, recipe.routing.objective, *recipe.routing.use_for])
        overlap = len(tokens & set(re.findall(r"\w+", text.casefold())))
        if not goals and not overlap:
            continue
        candidates.append((len(check["covered_goal_ids"]), overlap, {**check,
            "name": recipe.name, "version": recipe.version,
            "objective": recipe.routing.objective or ("" if recipe.origin_runs else recipe.description),
            "source_question": recipe.source_question or (recipe.description if recipe.origin_runs else None),
            "reuse": reuse_contract(recipe),
            "use_for": recipe.routing.use_for, "do_not_use_for": recipe.routing.do_not_use_for,
            "objective_source": "authored" if recipe.routing.objective or not recipe.origin_runs else "unspecified",
            "input_schema": {key: spec.model_dump(mode="json") for key, spec in recipe.inputs.items()}}))
    candidates.sort(key=lambda item: (-item[0], -item[1], item[2]["name"]))
    return {"candidates": [item[2] for item in candidates[:limit]],
            "guidance": "Compare the executable reuse.procedure and objective with the question. source_question and source_purpose are historical context, not fixed dates or filters. A runtime period may change unless fixed_method_periods constrain a step. An unspecified objective is not a reason by itself to skip a compatible procedure. Candidates do not prove natural-language relevance; never force an unrelated Recipe. When starting without a Recipe, record a skipped recipe_review with a concrete reason for each returned candidate. Partial candidates only cover the listed goals."}
