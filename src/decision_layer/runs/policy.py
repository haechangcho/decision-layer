"""Pure Recipe parameter and logical-query budget rules."""

from typing import Any, Literal
from ..core.models import Run, PlanStep
from ..core.periods import ExecutionPolicy
from ..methods import InvalidBinding
from ..i18n import _

from .errors import MethodNotAllowed, RunLimitExceeded

DEFAULT_MAX_STEPS = 12
DEFAULT_MAX_QUERIES = 30


def parameter_values(
    run: Run, method: str, params: dict[str, Any], origin: Literal["recipe", "request"]
) -> tuple[dict[str, Any], set[str]]:
    policy = (
        run.recipe_snapshot.method_parameters.get(method)
        if run.recipe_snapshot
        else None
    )
    if policy is None:
        return params, set()
    if origin == "request" and policy.runtime_allowed is not None:
        forbidden = set(params) - set(policy.runtime_allowed) - set(policy.fixed)
        if forbidden:
            raise InvalidBinding(
                _(
                    "Parameters not selectable at runtime: {names}",
                    names=sorted(forbidden),
                ),
                allowed=policy.runtime_allowed,
            )
    for name, value in policy.fixed.items():
        if name in params and params[name] != value:
            raise InvalidBinding(
                _("{name} is fixed by this Recipe", name=name), parameter=name
            )
    return {**params, **policy.fixed}, set(policy.fixed)


def remaining_queries(run: Run, policy: ExecutionPolicy) -> int:
    budget = (
        run.recipe_snapshot.limits.max_queries
        if run.recipe_snapshot
        else DEFAULT_MAX_QUERIES
    )
    legacy = len(run.validation_queries) + sum(
        len(s.result.provenance.queries) for s in run.steps
    )
    used = (run.query_attempt_baseline or 0) + len(run.query_attempts)
    return min(budget, policy.max_queries) - max(used, legacy)


def enforce_step(
    registry,
    policy: ExecutionPolicy,
    run: Run,
    step: PlanStep,
    *,
    check_budget=True,
    check_step_limit=True,
):
    rec = run.recipe_snapshot
    max_steps = rec.limits.max_steps if rec else DEFAULT_MAX_STEPS
    if check_step_limit and len(run.steps) >= max_steps:
        raise RunLimitExceeded(
            _(
                "This run reached its step limit ({limit}). Finish it with complete_run",
                limit=max_steps,
            )
        )
    if check_budget and remaining_queries(run, policy) <= 0:
        raise RunLimitExceeded(
            _("This run has used its query budget. Finish it with complete_run")
        )
    if rec is None:
        return
    allowed = (
        rec.allowed_methods
        if rec.mode == "investigation"
        else sorted({s.method for s in rec.steps})
    )
    if step.method not in allowed and not step.exploration:
        raise MethodNotAllowed(
            _(
                "Recipe '{recipe}' does not allow method {method}",
                recipe=rec.name,
                method=step.method,
            ),
            allowed=allowed,
        )
    in_scope = {rec.semantic_scope.primary_metric, *rec.semantic_scope.related_metrics}
    method = registry.get(step.method, step.method_version)
    for role, spec in method.manifest.roles.items():
        if spec.kind != "measure":
            continue
        value = step.bindings.get(role)
        for ref in value if isinstance(value, list) else [value] if value else []:
            if ref not in in_scope:
                if isinstance(ref, str) and ref.startswith("$"):
                    continue
                raise InvalidBinding(
                    _(
                        "'{ref}' is outside the metric scope of recipe '{recipe}'",
                        ref=ref,
                        recipe=rec.name,
                    ),
                    in_scope=sorted(in_scope),
                )
