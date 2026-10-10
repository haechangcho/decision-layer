"""Deterministic authoring defaults, shared by every product surface."""
from ..core.models import ParamSpec, Recipe, SemanticCatalog
from ..methods.base import registry


def configure_step(recipe: Recipe, index: int, reset: list[str] | None = None, *, catalog: SemanticCatalog | None = None) -> Recipe:
    if index < 0 or index >= len(recipe.steps):
        raise ValueError("Step index is outside the Recipe")
    result = recipe.model_copy(deep=True)
    step = result.steps[index]
    manifest = registry.get(step.method).manifest
    for name in reset or []:
        if name not in manifest.parameters:
            raise ValueError(f"Unknown parameter: {name}")
        policy = result.method_parameters.get(step.method)
        if policy and name in policy.fixed:
            raise ValueError(f"Fixed parameter cannot be reset: {name}")
        step.params.pop(name, None)
    for name, role in manifest.roles.items():
        if name not in step.bindings and role.default_binding:
            if role.default_binding == "unit_count":
                metric_ref = step.bindings.get("metric")
                if metric_ref == "$scope.primary_metric":
                    metric_ref = result.semantic_scope.primary_metric
                metric = catalog.get(metric_ref) if catalog and isinstance(metric_ref, str) else None
                if metric and metric.metric_kind == "average" and metric.entity:
                    candidates = [obj for obj in catalog.objects if obj.public and obj.kind == "measure"
                                  and obj.metric_kind == "count" and obj.count_measure == obj.ref
                                  and obj.entity == metric.entity]
                    if len(candidates) == 1:
                        step.bindings[name] = candidates[0].ref
                continue
            value = getattr(result.semantic_scope, role.default_binding)
            if value:
                step.bindings[name] = f"$scope.{role.default_binding}"
    prior = next((item for item in reversed(result.steps[:index])
                  if item.id and "ranked_groups" in registry.get(item.method).manifest.selection_outputs), None)
    # Parent-population defaults depend on another parameter, not manifest order.
    parameters = sorted(manifest.parameters.items(), key=lambda item: bool(item[1].source_policy and item[1].source_policy.default == "parameter_parents"))
    fixed = result.method_parameters.get(step.method)
    for name, spec in parameters:
        if name in step.params or (fixed and name in fixed.fixed) or not spec.source_policy:
            continue
        policy = spec.source_policy
        source = None
        if policy.default == "previous_result" and prior:
            source = {"source": "step", "step_id": prior.id, "output": "ranked_groups", "select": "first", "project": policy.project}
        elif policy.default == "parameter_parents":
            parent = step.params.get(policy.parameter)
            if isinstance(parent, dict) and parent.get("source") == "step":
                source = {**parent, "project": "parents"}
        if source:
            step.params[name] = source
        elif policy.default == "runtime_input" or (spec.required and policy.default != "literal"):
            if "input" not in policy.allowed:
                raise ValueError(f"{name}: no permitted default source is available")
            key = f"{step.id or f'step_{index + 1}'}_{name}"
            existing = result.inputs.get(key)
            if existing and existing.type != spec.type:
                raise ValueError(f"Runtime input type conflict: {key}")
            result.inputs.setdefault(key, ParamSpec(type=spec.type, required=True, label=spec.label, meaning=spec.meaning, description=spec.description))
            step.params[name] = {"source": "input", "name": key}
    return result
