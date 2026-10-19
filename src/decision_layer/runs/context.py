"""Build the scoped query context and persist attempts before provider execution."""

from __future__ import annotations
from ..core.models import Filter, Run
from ..methods.context import ExecutionContext, Scope
from .policy import remaining_queries


async def create_context(provider, store, policy, creds, run: Run) -> ExecutionContext:
    if run.query_attempt_baseline is None:
        legacy = len(run.validation_queries) + sum(
            len(s.result.provenance.queries) for s in run.steps
        )
        run.query_attempt_baseline = max(0, legacy - len(run.query_attempts))
    scope = run.plan.scope
    catalog = await provider.discover(creds)
    allowed = None
    if run.recipe_snapshot:
        allowed = {
            run.recipe_snapshot.semantic_scope.primary_metric,
            *run.recipe_snapshot.semantic_scope.related_metrics,
        }
        for ref in list(allowed):
            obj = catalog.get(ref)
            if obj:
                allowed.update(obj.ratio_parts or [])
                if obj.count_measure:
                    allowed.add(obj.count_measure)

    async def persist():
        await store.save(run)

    return ExecutionContext(
        provider=provider,
        credentials=creds,
        catalog=catalog,
        scope=Scope(
            tuple(scope["date_range"]) if scope.get("date_range") else None,
            scope.get("time_dimension"),
            [Filter.model_validate(f) for f in scope.get("filters") or []],
        ),
        max_queries=min(remaining_queries(run, policy), policy.max_queries),
        execution_policy=policy,
        attempts=run.query_attempts,
        persist_attempts=persist,
        allowed_measures=allowed,
    )
