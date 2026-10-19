"""Resolve and execute one governed step, retaining inputs and result evidence."""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from ..core.models import ExecutionAuthor, PlanStep, Provenance, Result, Run, StepRecord
from .expressions import resolve
from .policy import enforce_step, parameter_values


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _record(
    step: PlanStep,
    result: Result,
    started: datetime,
    parameter_sources: dict[
        str, Literal["method_default", "recipe", "recipe_fixed", "request"]
    ]
    | None = None,
) -> StepRecord:
    return StepRecord(
        step=step,
        method=result.provenance.method or "method://unknown@0.0.0",
        result=result,
        started_at=started,
        finished_at=_now(),
        parameter_sources=parameter_sources or {},
    )


async def execute_step(
    registry,
    policy,
    context,
    creds,
    run: Run,
    step: PlanStep,
    origin: Literal["recipe", "request"] = "request",
    author: ExecutionAuthor | None = None,
) -> Result:
    step = step.model_copy(
        update={
            "id": step.id or f"step_{len(run.steps) + 1}",
            "goal_ids": run.recipe_invocation.goal_ids
            if origin == "recipe" and run.recipe_invocation
            else step.goal_ids,
        }
    )
    requested_step = step.model_copy(deep=True)
    selected_method = registry.get(step.method, step.method_version)
    step = step.model_copy(update={"method_version": selected_method.manifest.version})
    results = {s.step.id: s.result for s in run.steps if s.step.id}
    resolutions: list[dict] = []
    inputs = run.plan.scope.get("inputs", {})
    from .expressions import AmbiguousSelection

    try:
        resolved = step.model_copy(
            update={
                "bindings": resolve(
                    step.bindings,
                    run.recipe_snapshot,
                    results,
                    inputs,
                    resolutions,
                    "bindings",
                ),
                "params": resolve(
                    step.params,
                    run.recipe_snapshot,
                    results,
                    inputs,
                    resolutions,
                    "params",
                ),
            }
        )
    except AmbiguousSelection as e:
        result = Result(
            status="needs_input",
            needs_input={
                "question": e.message,
                "field": e.details["field"],
                "candidates": [
                    {
                        "value": candidate["path"],
                        "label": str(candidate["path"][-1]["value"]),
                    }
                    for candidate in e.details["candidates"]
                ],
            },
            provenance=Provenance(
                method=registry.get(step.method, step.method_version).ref
            ),
        )
        result.run_id = run.id
        result.step_id = step.id
        record = _record(step, result, _now())
        record.requested_step, record.author = requested_step, author
        run.steps.append(record)
        run.plan.steps.append(step.model_copy(deep=True))
        return result
    provided, fixed = parameter_values(run, resolved.method, resolved.params, origin)
    sources = {
        name: "recipe_fixed"
        if name in fixed
        else origin
        if name in provided
        else "method_default"
        for name in registry.get(
            resolved.method, resolved.method_version
        ).manifest.parameters
    }
    resolved = resolved.model_copy(
        update={
            "params": registry.resolve_params(
                resolved.method, provided, version=resolved.method_version
            )
        }
    )
    enforce_step(registry, policy, run, resolved, check_budget=False)
    started = _now()
    ctx = await context(creds, run)
    ctx.step_id = step.id
    method = registry.get(resolved.method, resolved.method_version)
    skill = None
    if method.manifest.implementation == "skill":
        from ..core.models import SkillExecution

        registry.plannable(resolved.method, resolved.method_version)
        refs = registry._check_bindings(method, ctx, resolved.bindings)
        # Validate bound semantic conditions before asking the agent to query.
        from ..methods.common import path_filters

        for key, spec in method.manifest.parameters.items():
            if spec.type == "drill_path":
                path_filters(ctx, resolved.params.get(key) or [])
        skill = SkillExecution(
            guide=method.guide.model_copy(deep=True),
            manifest=method.manifest.model_copy(deep=True),
        )
        run.active_skill_step = step.id
        result = Result(
            status="needs_input",
            interpretation="association",
            needs_input={
                "reason_code": "AGENT_EXECUTION_REQUIRED",
                "next_tool": "run_skill_query",
                "step_id": step.id,
                "guide": skill.guide.model_dump(mode="json"),
                "bindings": resolved.bindings,
                "params": resolved.params,
            },
            provenance=Provenance(method=method.ref, semantic_refs=refs),
        )
    else:
        result = await registry.run(
            resolved.method,
            ctx,
            resolved.bindings,
            resolved.params,
            version=resolved.method_version,
        )
    result.run_id = run.id
    result.step_id = step.id
    record = _record(resolved, result, started, sources)
    record.skill = skill
    record.code = (
        method.source_snapshot.model_copy(deep=True, update={"editor_content": None})
        if getattr(method, "source_snapshot", None)
        else None
    )
    record.requested_step = requested_step
    record.input_resolutions = resolutions
    record.author = author
    if run.recipe_invocation and not step.exploration:
        record.invocation_id = run.recipe_invocation.id
        run.recipe_invocation.step_ids.append(step.id)
    run.steps.append(record)
    run.plan.steps.append(step.model_copy(deep=True))
    return result
