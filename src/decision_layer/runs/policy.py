"""Pure Recipe parameter and logical-query budget rules."""
from typing import Any, Literal
from ..core.models import Run
from ..core.periods import ExecutionPolicy
from ..methods import InvalidBinding
from ..i18n import _

DEFAULT_MAX_QUERIES = 30

def parameter_values(run: Run, method: str, params: dict[str, Any],
                            origin: Literal["recipe", "request"]) -> tuple[dict[str, Any], set[str]]:
    policy = run.recipe_snapshot.method_parameters.get(method) if run.recipe_snapshot else None
    if policy is None:
        return params, set()
    if origin == "request" and policy.runtime_allowed is not None:
        forbidden = set(params) - set(policy.runtime_allowed) - set(policy.fixed)
        if forbidden:
            raise InvalidBinding(_("Parameters not selectable at runtime: {names}", names=sorted(forbidden)),
                                 allowed=policy.runtime_allowed)
    for name, value in policy.fixed.items():
        if name in params and params[name] != value:
            raise InvalidBinding(_("{name} is fixed by this Recipe", name=name), parameter=name)
    return {**params, **policy.fixed}, set(policy.fixed)

def remaining_queries(run: Run, policy: ExecutionPolicy) -> int:
    budget = run.recipe_snapshot.limits.max_queries if run.recipe_snapshot else DEFAULT_MAX_QUERIES
    legacy = len(run.validation_queries) + sum(len(s.result.provenance.queries) for s in run.steps)
    used = (run.query_attempt_baseline or 0) + len(run.query_attempts)
    return min(budget, policy.max_queries) - max(used, legacy)
