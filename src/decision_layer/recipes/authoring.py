"""Versioned Recipe authoring, shared by API clients rather than owned by the Web."""
from __future__ import annotations

import re
from typing import Any

from ..core.errors import DecisionLayerError
from ..core.models import Recipe, SemanticScope
from ..methods import registry
from ..methods.base import InvalidBinding


class RecipeEditError(DecisionLayerError):
    code = "INVALID_RECIPE_EDIT"
    http_status = 422


class RecipeConflict(DecisionLayerError):
    code = "RECIPE_VERSION_CONFLICT"
    http_status = 409


def _invalid(message: str, field: str) -> RecipeEditError:
    return RecipeEditError(message, field=field)


def validate_recipe(recipe: Recipe) -> None:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}", recipe.name):
        raise _invalid("Recipe name must contain only letters, numbers, underscores or hyphens.", "name")
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", recipe.version):
        raise _invalid("Recipe version must be major.minor.patch.", "version")
    if recipe.limits.max_steps < max(1, len(recipe.steps)) or recipe.limits.max_queries < 1:
        raise _invalid("The step/query budget must cover the configured steps.", "limits")
    if recipe.mode == "investigation" and recipe.steps:
        raise _invalid("Investigation Recipes declare allowed methods, not automatic steps.", "steps")
    previous: set[str] = set()

    def expressions(value: Any, field: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                expressions(child, f"{field}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                expressions(child, f"{field}[{index}]")
        elif isinstance(value, str) and value.startswith("$"):
            parts = value.split(".")
            if parts[0] == "$scope" and len(parts) > 1 and parts[1] in SemanticScope.model_fields:
                return
            if parts[0] == "$steps" and len(parts) > 2 and parts[1] in previous:
                return
            raise _invalid(f"Unresolved or forward reference: {value}", field)

    for method in recipe.allowed_methods:
        try:
            registry.get(method)
        except InvalidBinding as e:
            raise _invalid(e.message, "allowed_methods") from e
    for i, step in enumerate(recipe.steps):
        try:
            manifest = registry.get(step.method).manifest
        except InvalidBinding as e:
            raise _invalid(e.message, f"steps[{i}].method") from e
        if step.id and (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", step.id) or step.id in previous):
            raise _invalid("Use a unique step ID without dots.", f"steps[{i}].id")
        if set(step.bindings) - set(manifest.roles) or set(step.params) - set(manifest.parameters):
            unknown = (set(step.bindings) - set(manifest.roles)) | (set(step.params) - set(manifest.parameters))
            key = sorted(unknown)[0]
            section = "bindings" if key in step.bindings else "params"
            raise _invalid(f"Unknown Method input or parameter: {key}.", f"steps[{i}].{section}.{key}")
        for key, role in manifest.roles.items():
            if role.required and not step.bindings.get(key):
                raise _invalid(f"{key} is required.", f"steps[{i}].bindings.{key}")
        for key, param in manifest.parameters.items():
            value = step.params.get(key, param.default)
            if param.required and value is None:
                raise _invalid(f"{key} is required.", f"steps[{i}].params.{key}")
            if isinstance(value, str) and value.startswith("$"):
                continue
            if value is not None and param.type == "enum" and value not in (param.enum or []):
                raise _invalid(f"Invalid value for {key}.", f"steps[{i}].params.{key}")
        expressions(step.bindings, f"steps[{i}].bindings")
        expressions(step.params, f"steps[{i}].params")
        if step.id:
            previous.add(step.id)
