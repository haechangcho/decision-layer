"""`$` expressions in Recipe steps.

    $scope.primary_metric | $scope.related_metrics | $scope.preferred_dimensions
    $steps.<step id>.<path>        e.g. $steps.by_category.primary.data.next_candidates.0.drill_path

Paths walk the earlier step's Result as JSON (dict keys, list indexes). A path
that doesn't exist fails the step instead of silently running with nothing.
"""
from __future__ import annotations

from typing import Any

from ..core.errors import DecisionLayerError
from ..core.models import Recipe, Result
from ..i18n import _


class UnresolvedExpression(DecisionLayerError):
    code = "UNRESOLVED_EXPRESSION"
    http_status = 422


def resolve(value: Any, recipe: Recipe | None, results: dict[str, Result]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return _lookup(value, recipe, results)
    if isinstance(value, list):
        return [resolve(v, recipe, results) for v in value]
    if isinstance(value, dict):
        return {k: resolve(v, recipe, results) for k, v in value.items()}
    return value


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
