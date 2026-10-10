"""Versioned Recipe authoring, shared by API clients rather than owned by the Web."""
from __future__ import annotations
from ..semantic.provider import Credentials, SemanticProvider
from ..core.errors import UnknownSemanticObject
from ..core.ids import is_semantic_ref

import re
from typing import Any

from ..core.errors import DecisionLayerError
from ..core.models import Recipe, SemanticScope, RuntimeInputSource, StepSelectionSource
from ..runs.expressions import is_dynamic
from ..methods import registry
from ..methods import InvalidBinding


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
    previous_outputs: dict[str, list[str]] = {}
    for name, spec in recipe.inputs.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", name) or is_dynamic(spec.default):
            raise _invalid("Runtime inputs need a valid name and a literal default.", f"inputs.{name}")
        try:
            registry.input_values({name: spec}, {}, partial=True)
        except InvalidBinding as e:
            raise _invalid(e.message, f"inputs.{name}") from e

    def expressions(value: Any, field: str) -> None:
        if isinstance(value, dict):
            if value.get("source") == "step":
                try:
                    ref = StepSelectionSource.model_validate(value)
                except ValueError as e:
                    raise _invalid("Invalid previous-step selection reference.", field) from e
                if ref.step_id not in previous or ref.output not in previous_outputs.get(ref.step_id, []):
                    raise _invalid("Selection must reference a declared output of an earlier step.", field)
                return
            if value.get("source") == "input":
                try:
                    ref = RuntimeInputSource.model_validate(value)
                except ValueError as e:
                    raise _invalid("Invalid runtime input reference.", field) from e
                if ref.name not in recipe.inputs:
                    raise _invalid("Runtime input must be declared in the Recipe.", field)
                return
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
    available = set(recipe.allowed_methods if recipe.mode == "investigation" else (step.method for step in recipe.steps))
    for method, policy in recipe.method_parameters.items():
        field = f"method_parameters.{method}"
        if method not in available:
            raise _invalid("Parameter policy refers to a Method outside this Recipe.", field)
        manifest = registry.get(method).manifest
        for name, value in policy.fixed.items():
            if name not in manifest.parameters:
                raise _invalid(f"Unknown Method parameter: {name}.", f"{field}.fixed.{name}")
            if is_dynamic(value):
                raise _invalid("Fixed parameters must be literal values.", f"{field}.fixed.{name}")
            try:
                registry.resolve_params(method, {name: value}, partial=True)
            except InvalidBinding as e:
                raise _invalid(e.message, f"{field}.fixed.{name}") from e
        if policy.runtime_allowed is not None:
            if len(policy.runtime_allowed) != len(set(policy.runtime_allowed)):
                raise _invalid("Runtime parameter names must be unique.", f"{field}.runtime_allowed")
            for name in policy.runtime_allowed:
                if name not in manifest.parameters or name in policy.fixed:
                    raise _invalid(f"Parameter cannot be selected at runtime: {name}.", f"{field}.runtime_allowed")
    for i, step in enumerate(recipe.steps):
        if step.exploration or step.goal_ids:
            raise _invalid("Run goal links and exploration flags do not belong in reusable Recipe steps.", f"steps[{i}]")
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
        groups = {role.exclusive_group for role in manifest.roles.values() if role.exclusive_group}
        for group in groups:
            keys = [key for key, role in manifest.roles.items() if role.exclusive_group == group]
            if sum(bool(step.bindings.get(key)) for key in keys) != 1:
                raise _invalid("Choose exactly one group-splitting semantic field.", f"steps[{i}].bindings.{keys[0]}")
        for key, role in manifest.roles.items():
            if role.required and not step.bindings.get(key):
                raise _invalid(f"{key} is required.", f"steps[{i}].bindings.{key}")
            value = step.bindings.get(key)
            if isinstance(value, dict) and (value.get("source") == "step" or value.get("source") == "input"):
                raise _invalid("Group selection references belong in Method parameters, not semantic bindings.", f"steps[{i}].bindings.{key}")
        for key, param in manifest.parameters.items():
            value = step.params.get(key, param.default)
            if param.source_policy and isinstance(value, dict) and value.get("source") in ("step", "input") and value["source"] not in param.source_policy.allowed:
                raise _invalid("This input source is not allowed by the Method.", f"steps[{i}].params.{key}")
            if param.required and value is None:
                raise _invalid(f"{key} is required.", f"steps[{i}].params.{key}")
            if is_dynamic(value):
                expressions(value, f"steps[{i}].params.{key}")
                if isinstance(value, dict) and value.get("source") == "step" and param.type != "drill_path":
                    raise _invalid("A group selection requires a group-condition input.", f"steps[{i}].params.{key}")
                if isinstance(value, dict) and value.get("source") == "input" and recipe.inputs[value["name"]].type != param.type:
                    raise _invalid("Runtime input type does not match the Method parameter.", f"steps[{i}].params.{key}")
                fixed = recipe.method_parameters.get(step.method)
                if fixed and key in fixed.fixed:
                    raise _invalid("A dynamic input conflicts with a fixed parameter.", f"steps[{i}].params.{key}")
                continue
            if value is not None and param.type == "enum" and value not in (param.enum or []):
                raise _invalid(f"Invalid value for {key}.", f"steps[{i}].params.{key}")
            fixed = recipe.method_parameters.get(step.method)
            if fixed and key in fixed.fixed and key in step.params and step.params[key] != fixed.fixed[key]:
                raise _invalid(f"{key} conflicts with the Recipe's fixed value.", f"steps[{i}].params.{key}")
            if key in step.params and not (isinstance(value, str) and value.startswith("$")):
                try:
                    registry.resolve_params(step.method, {key: value}, partial=True)
                except InvalidBinding as e:
                    raise _invalid(e.message, f"steps[{i}].params.{key}") from e
        expressions(step.bindings, f"steps[{i}].bindings")
        expressions(step.params, f"steps[{i}].params")
        if step.id:
            previous.add(step.id)
            previous_outputs[step.id] = manifest.selection_outputs



async def check_recipe_semantics(recipe: Recipe, provider: SemanticProvider, creds: Credentials) -> None:
    paths: dict[str, str] = {}

    def collect(value, path: str) -> None:
        if is_semantic_ref(value):
            paths.setdefault(value, path)
        elif isinstance(value, dict):
            for key, child in value.items():
                collect(child, f"{path}.{key}" if path else key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                collect(child, f"{path}[{index}]")

    collect(recipe.model_dump(mode="json"), "")
    try:
        await provider.resolve(sorted(paths), creds)
    except UnknownSemanticObject as error:
        if field := paths.get(error.details.get("ref")):
            error.details["field"] = field
        raise
