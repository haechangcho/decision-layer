"""`$` expressions in Recipe steps.

    $scope.primary_metric | $scope.related_metrics | $scope.preferred_dimensions
    $steps.<step id>.<path>        e.g. $steps.by_category.primary.data.next_candidates.0.drill_path

Paths walk the earlier step's Result as JSON (dict keys, list indexes). A path
that doesn't exist fails the step instead of silently running with nothing.
"""
from __future__ import annotations

from typing import Any
from pydantic import ValidationError

from ..core.errors import DecisionLayerError
from ..core.models import Recipe, Result, RuntimeInputSource, StepSelectionSource
from ..i18n import _


class UnresolvedExpression(DecisionLayerError):
    code = "UNRESOLVED_EXPRESSION"
    http_status = 422


class AmbiguousSelection(UnresolvedExpression):
    code = "SELECTION_NEEDS_INPUT"


def resolve(value: Any, recipe: Recipe | None, results: dict[str, Result],
            inputs: dict[str, Any] | None = None, evidence: list[dict[str, Any]] | None = None,
            field: str = "") -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return _lookup(value, recipe, results)
    if isinstance(value, list):
        return [resolve(v, recipe, results, inputs, evidence, f"{field}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, dict):
        if value.get("source") == "input":
            try:
                ref = RuntimeInputSource.model_validate(value)
            except ValidationError as e:
                raise UnresolvedExpression(_("Invalid runtime input reference."), field=field) from e
            if recipe is None or ref.name not in recipe.inputs or ref.name not in (inputs or {}):
                raise UnresolvedExpression(_("A declared runtime input is missing."), field=field, input=ref.name)
            resolved = inputs[ref.name]
        elif value.get("source") == "step":
            try:
                ref = StepSelectionSource.model_validate(value)
            except ValidationError as e:
                raise UnresolvedExpression(_("Invalid previous-step selection reference."), field=field) from e
            result = results.get(ref.step_id)
            output = result.selections.get(ref.output) if result and result.status == "success" else None
            if output is None or not output.complete or not output.candidates:
                raise UnresolvedExpression(_("The earlier step has no complete eligible selection."), field=field,
                                           step_id=ref.step_id, output=ref.output)
            candidate = output.candidates[0]
            if len(output.candidates) > 1 and candidate.score == output.candidates[1].score:
                raise AmbiguousSelection(_("The leading groups are tied. Choose an explicit group before continuing."),
                                         field=field, step_id=ref.step_id,
                                         candidates=[item.model_dump(mode="json") for item in output.candidates if item.score == candidate.score])
            path = [condition.model_dump(mode="json") for condition in candidate.path]
            resolved = path if ref.project == "path" else path[-1:] if ref.project == "condition" else path[:-1]
        else:
            return {k: resolve(v, recipe, results, inputs, evidence, f"{field}.{k}") for k, v in value.items()}
        if evidence is not None:
            entry = {"field": field, "source": value, "resolved": resolved}
            if value.get("source") == "step":
                entry["selection"] = {"rank_by": output.rank_by, "direction": output.direction,
                                      "score": candidate.score, "eligible_groups": len(output.candidates),
                                      "complete": output.complete, "method": result.provenance.method}
            evidence.append(entry)
        return resolved
    return value


def is_dynamic(value: Any) -> bool:
    if isinstance(value, str):
        return value.startswith("$")
    if isinstance(value, dict):
        return value.get("source") == "step" or value.get("source") == "input" or any(is_dynamic(v) for v in value.values())
    return isinstance(value, list) and any(is_dynamic(v) for v in value)


def _lookup(expr: str, recipe: Recipe | None, results: dict[str, Result]) -> Any:
    head, *path = expr[1:].split(".")
    if head == "scope":
        if recipe is None:
            raise UnresolvedExpression(_("{expr}: there is no scope outside a Recipe", expr=expr))
        node: Any = recipe.semantic_scope.model_dump(mode="json")
    elif head == "steps" and path:
        step_id, *path = path
        if step_id not in results:
            raise UnresolvedExpression(_("{expr}: no result from earlier step '{step_id}'", expr=expr, step_id=step_id), available=sorted(results))
        node = results[step_id].model_dump(mode="json")
    else:
        raise UnresolvedExpression(_("{expr}: expected $scope.… or $steps.<id>.…", expr=expr))
    for key in path:
        try:
            node = node[int(key)] if isinstance(node, list) else node[key]
        except (KeyError, IndexError, ValueError, TypeError):
            raise UnresolvedExpression(_("{expr}: '{key}' not found", expr=expr, key=key)) from None
    return node
