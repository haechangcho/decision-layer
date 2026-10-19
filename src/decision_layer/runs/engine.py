"""Run engine: executes Recipes and enforces investigation sessions (ADR-021).

- pipeline Recipe: all steps run on start; `$steps.<id>…` feeds earlier results
  into later steps. A step that needs input or is refused stops the pipeline and
  leaves the run open, so the caller can continue with explicit steps.
- investigation Recipe: the MCP client (an LLM) proposes one step at a time; the
  server enforces the Recipe's allowed Methods, its metric scope, the step limit
  and the query budget. The client never gets more power than the Recipe grants.
- ad-hoc Method calls are stored as single-step runs, so every result has a run id.

Runs belong to the caller who started them (ADR-029). Other callers can't see
or continue them; the owner can share one read-only. A shared run is only
shown to a viewer whose own catalog includes every semantic object it used.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Literal

from ..core.errors import DecisionLayerError
from ..core.ids import new_id, recipe_ref
from ..core.models import (
    AnalysisGoal,
    AnalysisPlan,
    CallerInfo,
    ExecutionAuthor,
    Filter,
    PlanStep,
    Recipe,
    RecipeInvocation,
    RecipeReview,
    RecipeSelection,
    Result,
    Run,
    RunConclusion,
    RunRetryLink,
    RunningJob,
    ValidationResult,
)
from ..core.periods import ExecutionPolicy, PeriodChoice, resolve_scope
from ..methods import registry as default_registry
from ..methods import InvalidBinding, MethodRegistry
from ..methods.context import ExecutionContext, NeedsInput, Refused
from ..recipes.loader import RecipeStore
from ..semantic.provider import Credentials, SemanticProvider
from ..validation import builtin as v
from .jobs import JobRunner
from .policy import remaining_queries
from .store import RunStore
from ..i18n import _

from .errors import (
    RunClosed,
    RunLimitExceeded,
    RunBusy,
    MethodNotAllowed,
    PreviewStepInvalid,
    AnalysisContractError,
    ExecutionDeadlineExceeded,
)
from .policy import DEFAULT_MAX_STEPS, DEFAULT_MAX_QUERIES, enforce_step
from .access import _owns, _shared_with, owned_run, visible_run
from .context import create_context
from .steps import _record, execute_step


class RunEngine:
    def __init__(
        self,
        provider: SemanticProvider,
        recipes: RecipeStore,
        store: RunStore,
        registry: MethodRegistry = default_registry,
        jobs: JobRunner | None = None,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        self.provider, self.recipes, self.store, self.registry = (
            provider,
            recipes,
            store,
            registry,
        )
        self.jobs = jobs or JobRunner()
        self.policy = policy or ExecutionPolicy()
        self._scope_locks: dict[str, asyncio.Lock] = {}

    def _prepare_scope(self, run: Run, scope: dict[str, Any]) -> None:
        defaults = (
            run.recipe_snapshot.default_scope.model_dump(mode="json")
            if run.recipe_snapshot and run.recipe_snapshot.default_scope
            else None
        )
        try:
            run.plan.scope, run.scope_resolution = resolve_scope(
                scope, defaults, self.policy
            )
        except ValueError as exc:
            raise InvalidBinding(str(exc)) from exc
        run.execution_policy = self.policy

    async def _pause(
        self, creds: Credentials, run: Run, pending: dict[str, Any]
    ) -> bool:
        choice = PeriodChoice.model_validate(run.plan.scope["period"])
        issue = self.policy.issue(choice)
        allow_all = self.policy.allow_all
        if run.recipe_snapshot and pending["kind"] in ("pipeline", "preview"):
            last_step = pending.get("step_index", len(run.recipe_snapshot.steps) - 1)
            steps = run.recipe_snapshot.steps[: last_step + 1]
        elif pending.get("step"):
            steps = [PlanStep.model_validate(pending["step"])]
        else:
            steps = []
        for step in steps:
            manifest = self.registry.get(step.method, step.method_version).manifest
            fixed = (
                run.recipe_snapshot.method_parameters.get(step.method)
                if run.recipe_snapshot
                else None
            )
            params = {**step.params, **(fixed.fixed if fixed else {})}
            if manifest.requires_period or any(
                spec.meaning == "period"
                and spec.type == "boolean"
                and params.get(name, spec.default) is True
                for name, spec in manifest.parameters.items()
            ):
                allow_all = False
                if choice.mode == "all":
                    issue = _(
                        "This analysis needs a date range. Choose its start and end dates."
                    )
        field, candidates = "period", []
        if not issue and choice.mode == "range":
            first = steps[0] if steps else None
            metric = first.bindings.get("metric") if first else None
            if metric == "$scope.primary_metric" or not metric:
                metric = (
                    run.recipe_snapshot.semantic_scope.primary_metric
                    if run.recipe_snapshot
                    else None
                )
            if isinstance(metric, str) and not metric.startswith("$"):
                ctx = await self._context(creds, run)
                try:
                    dimension = ctx.time_dimension_for(metric)
                    run.plan.scope["time_dimension"] = dimension
                except NeedsInput as exc:
                    issue, field, candidates = (
                        exc.question,
                        "time_dimension",
                        exc.details["candidates"],
                    )
                except Refused as exc:
                    issue, field = exc.message, "time_dimension"
        if not issue:
            run.needs_input = None
            run.pending_execution = None
            return False
        if field == "time_dimension":
            reason = "TIME_DIMENSION_REQUIRED"
        elif choice.mode == "unresolved":
            reason = "PERIOD_UNRESOLVED"
        elif choice.mode == "all":
            reason = (
                "RANGE_REQUIRED" if self.policy.allow_all else "ALL_PERIODS_DISABLED"
            )
        else:
            reason = "PERIOD_TOO_LONG"
        run.needs_input = {
            "field": field,
            "reason_code": reason,
            "question": _(issue),
            "candidates": candidates,
            "policy_revision": self.policy.revision,
            "allow_all": allow_all,
            "max_period_days": self.policy.max_period_days,
        }
        if run.pending_execution is not None and run.pending_execution != pending:
            run.scope_revision += 1
        run.pending_execution = pending
        run.running = None
        return True

    async def set_scope(
        self,
        creds: Credentials,
        caller: CallerInfo,
        run_id: str,
        scope: dict[str, Any],
        base_revision: int,
        wait: float | None = None,
    ) -> Run:
        async with self._scope_locks.setdefault(run_id, asyncio.Lock()):
            run = await self._owned(run_id, caller)
            if (
                run.running
                or run.steps
                or run.validation_queries
                or run.query_attempts
                or run.status != "open"
            ):
                raise RunBusy(
                    _(
                        "Start a new Run to change the period after execution has started."
                    )
                )
            if run.scope_revision != base_revision:
                raise RunBusy(
                    _(
                        "The analysis conditions have changed. Reload the Run before continuing."
                    )
                )
            if not run.pending_execution:
                raise InvalidBinding("This Run has no pending period request.")
            pending = run.pending_execution
            # Filters, inputs and provider context cannot be replaced by a period update.
            if set(scope) - {"period", "date_range", "time_dimension"}:
                raise InvalidBinding("Only period and time dimension may change here.")
            merged = {
                k: v
                for k, v in run.plan.scope.items()
                if k not in ("period", "date_range")
            }
            self._prepare_scope(run, {**merged, **scope})
            run.scope_revision += 1
            if await self._pause(creds, run, pending):
                await self.store.save(run)
                return run
            run.pending_execution = None
            run.error = None
            kind = pending["kind"]
            if kind == "investigation":
                await self.store.save(run)
                return run
            run.running = RunningJob(
                kind=kind, method=pending.get("step", {}).get("method")
            )
            await self.store.save(run)

            async def resume(current: Run):
                if kind == "pipeline":
                    current.validation = await self._recipe_validators(creds, current)
                    await self._pipeline(creds, current)
                elif kind == "preview":
                    await self._preview_steps(creds, current, pending["step_index"])
                else:
                    await self._execute(
                        creds,
                        current,
                        PlanStep.model_validate(pending["step"]),
                        author=ExecutionAuthor.model_validate(pending["author"])
                        if pending.get("author")
                        else None,
                    )
                    if kind == "adhoc":
                        current.status, current.finished_at = "completed", _now()
                        current.ensure_conclusion()

            await self._run_job(run_id, resume, wait)
            return await self.store.get(run_id)

    # ── lifecycle ─────────────────────────────────────────────────────────
    # Execution entry points take `wait`: seconds to wait for the background job (None = until done).
    # They return the run as stored; `run.running` is still set when the job outlived the wait.
    async def start(
        self,
        creds: Credentials,
        caller: CallerInfo,
        *,
        recipe: str | None,
        question: str | None,
        scope: dict[str, Any],
        wait: float | None = None,
        origin: Literal["python", "api", "web", "mcp"] = "python",
        author: ExecutionAuthor | None = None,
        goals: list[AnalysisGoal] | None = None,
        recipe_selection: RecipeSelection | None = None,
        interactive: bool = False,
        recipe_review: list[RecipeReview] | None = None,
        retry_of: RunRetryLink | None = None,
        guide: str | None = None,
    ) -> Run:
        if origin == "mcp" and not (question and question.strip()):
            raise AnalysisContractError(
                _("Start the analysis with the original user question."),
                next_tool="start_analysis",
            )
        guidance = []
        if guide:
            from ..methods.skills import SkillMethod

            selected = self.registry.get(guide)
            if not isinstance(selected, SkillMethod):
                raise InvalidBinding("guide must name a registered Skill Method")
            guidance = [selected.guide.model_copy(deep=True)]
        rec = self.recipes.get(recipe) if recipe else None
        goals = goals or []
        if origin == "mcp" and not goals:
            raise AnalysisContractError(
                "Record the requested answers as goals before execution.",
                next_tool="start_analysis",
            )
        if len({goal.id for goal in goals}) != len(goals):
            raise InvalidBinding("Goal IDs must be unique.")
        if goals:
            await self.provider.resolve(
                sorted({ref for goal in goals for ref in goal.semantic_refs}), creds
            )
        if recipe_selection and not rec:
            raise InvalidBinding("A Recipe selection requires a Recipe.")
        if rec and origin == "mcp" and not recipe_selection:
            raise AnalysisContractError(
                "Record why this Recipe fits and which goals it covers.",
                next_tool="start_run",
            )
        if rec:
            from ..recipes.routing import compatibility, semantic_refs

            await self.provider.resolve(
                sorted(semantic_refs(rec.model_dump(mode="json"))), creds
            )
            selected_ids = (
                recipe_selection.goal_ids
                if recipe_selection
                else [goal.id for goal in goals]
            )
            if goals and not selected_ids:
                raise InvalidBinding("Select at least one goal for this Recipe.")
            if set(selected_ids) - {goal.id for goal in goals}:
                raise InvalidBinding("Recipe selection references an unknown goal.")
            check = compatibility(
                rec,
                [goal for goal in goals if goal.id in selected_ids],
                scope.get("inputs") or {},
                registry=self.registry,
            )
            if check["conflicts"]:
                raise InvalidBinding(
                    "This Recipe cannot cover the selected goals.",
                    conflicts=check["conflicts"],
                )
        if rec:
            scope = {
                **scope,
                "inputs": self.registry.input_values(
                    rec.inputs, scope.get("inputs") or {}
                ),
            }
        reviews, candidates = list(recipe_review or []), []
        if origin == "mcp" or reviews:
            from ..recipes.routing import search_recipes, reuse_contract

            candidates = (
                await search_recipes(
                    self.recipes,
                    self.provider,
                    creds,
                    question or "",
                    goals,
                    scope.get("inputs") or {},
                    5,
                )
            )["candidates"]
            by_ref = {item.recipe: item for item in reviews}
            if len(by_ref) != len(reviews):
                raise InvalidBinding("Review each Recipe version only once.")
            selected_ref = recipe_ref(rec.name, rec.version) if rec else None
            visible_refs = {item["recipe"] for item in candidates} | (
                {selected_ref} if selected_ref else set()
            )
            if set(by_ref) - visible_refs:
                raise InvalidBinding(
                    "Recipe reviews must reference current visible candidates."
                )
            if any(
                item.decision == "selected" and item.recipe != selected_ref
                for item in reviews
            ):
                raise InvalidBinding(
                    "The selected review must match the executed Recipe."
                )
            if rec and recipe_selection:
                if (
                    selected_ref in by_ref
                    and by_ref[selected_ref].decision != "selected"
                ):
                    raise InvalidBinding(
                        "An executed Recipe cannot be recorded as skipped."
                    )
                reviews = [item for item in reviews if item.recipe != selected_ref]
                reviews.append(
                    RecipeReview(
                        recipe=selected_ref,
                        decision="selected",
                        reason=recipe_selection.reason,
                    )
                )
                if selected_ref not in {item["recipe"] for item in candidates}:
                    candidates = candidates + [
                        {
                            "recipe": selected_ref,
                            "name": rec.name,
                            "objective": rec.routing.objective,
                            "reuse": reuse_contract(rec, registry=self.registry),
                        }
                    ]
            if not rec:
                missing = [item for item in candidates if item["recipe"] not in by_ref]
                if missing:
                    raise AnalysisContractError(
                        "Review the available Recipe candidates before starting a new procedure. Record a concrete skip reason; a historical date in source_question is not a fixed execution period.",
                        next_tool="find_recipes",
                        candidates=missing,
                    )
        filters = [
            *(rec.semantic_scope.required_filters if rec else []),
            *(Filter.model_validate(f) for f in scope.get("filters") or []),
        ]
        run = Run(
            id=new_id("run"),
            caller=caller,
            origin=origin,
            author=author,
            retry_of=retry_of,
            plan=AnalysisPlan(
                question=question,
                recipe=recipe_ref(rec.name, rec.version) if rec else None,
                scope={
                    **scope,
                    "filters": [f.model_dump(mode="json") for f in filters],
                },
                resolved=_resolved(rec),
            ),
            recipe_snapshot=rec,
            method_guides=guidance,
            goals=goals,
            recipe_selection=recipe_selection,
            interactive=interactive,
            recipe_review=reviews,
            recipe_candidates=candidates,
            recipe_invocation=RecipeInvocation(
                recipe=recipe_ref(rec.name, rec.version), goal_ids=selected_ids
            )
            if rec
            else None,
        )
        self._prepare_scope(run, run.plan.scope)
        if await self._pause(
            creds,
            run,
            {"kind": "pipeline" if rec and rec.mode == "pipeline" else "investigation"},
        ):
            await self.store.save(run)
            return run
        if rec and rec.mode != "pipeline":
            run.validation = await self._recipe_validators(creds, run)
        if not (rec and rec.mode == "pipeline"):
            await self.store.save(run)
            return run
        run.running = RunningJob(kind="pipeline")
        await self.store.save(run)

        async def pipeline(current):
            current.validation = await self._recipe_validators(creds, current)
            await self._pipeline(creds, current)

        await self._run_job(run.id, pipeline, wait)
        return await self.store.get(run.id)

    async def use_recipe(
        self,
        creds: Credentials,
        caller: CallerInfo,
        run_id: str,
        recipe: str,
        selection: RecipeSelection,
        inputs: dict[str, Any],
        wait: float | None = None,
    ) -> Run:
        """Attach one pipeline to an open exploration without changing earlier query scope."""
        async with self._scope_locks.setdefault(run_id, asyncio.Lock()):
            run = await self._owned(run_id, caller)
            if run.status != "open" or run.running or run.recipe_snapshot:
                raise RunBusy("This Run cannot start another Recipe.")
            rec = self.recipes.get(recipe)
            if rec.mode != "pipeline":
                raise InvalidBinding(
                    "Only a pipeline Recipe can be attached to an existing exploration."
                )
            from ..recipes.routing import compatibility, semantic_refs

            await self.provider.resolve(
                sorted(semantic_refs(rec.model_dump(mode="json"))), creds
            )
            if not selection.goal_ids or set(selection.goal_ids) - {
                goal.id for goal in run.goals
            }:
                raise InvalidBinding("Select recorded goals for the Recipe.")
            check = compatibility(
                rec,
                [goal for goal in run.goals if goal.id in selection.goal_ids],
                inputs,
                registry=self.registry,
            )
            if check["conflicts"]:
                raise InvalidBinding(
                    "This Recipe cannot cover the selected goals.",
                    conflicts=check["conflicts"],
                )
            values = self.registry.input_values(rec.inputs, inputs)
            previous_filters = [
                Filter.model_validate(item)
                for item in run.plan.scope.get("filters", [])
            ]
            if run.query_attempts and any(
                item not in previous_filters
                for item in rec.semantic_scope.required_filters
            ):
                raise InvalidBinding(
                    "This Recipe requires different shared filters. Start a new Run."
                )
            run.recipe_snapshot = rec.model_copy(deep=True)
            run.recipe_selection = selection
            run.plan.recipe = recipe_ref(rec.name, rec.version)
            run.recipe_review.append(
                RecipeReview(
                    recipe=run.plan.recipe, decision="selected", reason=selection.reason
                )
            )
            if run.plan.recipe not in {
                item.get("recipe") for item in run.recipe_candidates
            }:
                from ..recipes.routing import reuse_contract

                run.recipe_candidates.append(
                    {
                        "recipe": run.plan.recipe,
                        "name": rec.name,
                        "objective": rec.routing.objective,
                        "reuse": reuse_contract(rec, registry=self.registry),
                    }
                )
            run.plan.resolved.update(_resolved(rec))
            run.plan.scope["inputs"] = values
            run.plan.scope["filters"] = [
                item.model_dump(mode="json")
                for item in previous_filters
                + [
                    item
                    for item in rec.semantic_scope.required_filters
                    if item not in previous_filters
                ]
            ]
            run.recipe_invocation = RecipeInvocation(
                recipe=run.plan.recipe,
                goal_ids=selection.goal_ids,
                step_id_map={
                    step.id
                    or f"step_{index + 1}": f"recipe_1_{step.id or f'step_{index + 1}'}"
                    for index, step in enumerate(rec.steps)
                },
            )
            run.interactive = True
            if await self._pause(creds, run, {"kind": "pipeline"}):
                await self.store.save(run)
                return run
            run.running, run.error = RunningJob(kind="pipeline"), None
            await self.store.save(run)

            async def pipeline(current):
                current.validation.extend(await self._recipe_validators(creds, current))
                await self._pipeline(creds, current)

            await self._run_job(run.id, pipeline, wait)
            return await self.store.get(run.id)

    async def preview(
        self,
        creds: Credentials,
        caller: CallerInfo,
        recipe: Recipe,
        step_index: int,
        scope: dict[str, Any],
        wait: float | None = None,
        origin: Literal["python", "api", "web", "mcp"] = "python",
    ) -> Run:
        if (
            recipe.mode != "pipeline"
            or step_index < 0
            or step_index >= len(recipe.steps)
        ):
            raise PreviewStepInvalid(
                _("Choose an existing pipeline step to preview"), step_index=step_index
            )
        scope = {
            **scope,
            "inputs": self.registry.input_values(
                recipe.inputs, scope.get("inputs") or {}
            ),
        }
        filters = [
            *recipe.semantic_scope.required_filters,
            *(Filter.model_validate(value) for value in scope.get("filters") or []),
        ]
        run = Run(
            id=new_id("run"),
            caller=caller,
            origin=origin,
            preview=True,
            recipe_snapshot=recipe,
            plan=AnalysisPlan(
                scope={
                    **scope,
                    "filters": [f.model_dump(mode="json") for f in filters],
                },
                resolved=_resolved(recipe),
            ),
            running=RunningJob(kind="preview", method=recipe.steps[step_index].method),
        )
        self._prepare_scope(run, run.plan.scope)
        if await self._pause(creds, run, {"kind": "preview", "step_index": step_index}):
            await self.store.save(run)
            return run
        await self.store.save(run)
        await self._run_job(
            run.id,
            lambda current: self._preview_steps(creds, current, step_index),
            wait,
        )
        return await self.store.get(run.id)

    async def step(
        self,
        creds: Credentials,
        caller: CallerInfo,
        run_id: str,
        step: PlanStep,
        wait: float | None = None,
        author: ExecutionAuthor | None = None,
        input_maps: dict | None = None,
    ) -> tuple[Run, Result | None]:
        async with self._scope_locks.setdefault(run_id, asyncio.Lock()):
            return await self._step(
                creds, caller, run_id, step, wait, author, input_maps
            )

    async def _step(self, creds, caller, run_id, step, wait, author, input_maps=None):
        run = await self._owned(run_id, caller)
        if run.active_skill_step:
            raise RunBusy(
                "Finish the active Skill step before starting another step.",
                step_id=run.active_skill_step,
            )
        if input_maps:
            self._enforce(run, step, check_budget=False, check_step_limit=False)
            from ..methods.invocation import invocation_inputs

            step = step.model_copy(
                update={
                    "bindings": invocation_inputs(
                        self.registry.get(step.method, step.method_version).manifest,
                        bindings=step.bindings,
                        **input_maps,
                    )
                }
            )
        if step.id:
            for record in run.steps:
                if record.step.id == step.id:
                    if (
                        record.requested_step or record.step
                    ).model_dump() == step.model_dump():
                        return run, record.result
                    raise InvalidBinding(
                        "This step ID already has a different request.", step_id=step.id
                    )
            if run.active_step and run.active_step.id == step.id:
                if run.active_step.model_dump() == step.model_dump():
                    return run, None
                raise InvalidBinding(
                    "This step ID is executing a different request.", step_id=step.id
                )
        if run.status != "open":
            raise RunClosed(
                _("The run is already {status}", status=run.status), run_id=run_id
            )
        if run.running:
            raise RunBusy(
                _(
                    "The previous step is still running. Request the next step when it has finished"
                ),
                run_id=run_id,
            )
        if run.origin == "mcp" and not (step.purpose and step.purpose.strip()):
            raise AnalysisContractError(
                _(
                    "Each analysis step needs a purpose explaining how it answers the question."
                ),
                run_id=run_id,
                next_tool="run_step",
            )
        if set(step.goal_ids) - {goal.id for goal in run.goals}:
            raise InvalidBinding("The step references an unknown goal.")
        if run.origin == "mcp" and run.goals and not step.goal_ids:
            raise AnalysisContractError(
                "Link this step to at least one requested goal.", next_tool="run_step"
            )
        if step.exploration and run.recipe_snapshot:
            if (
                not self.policy.allow_recipe_extension
                or not run.recipe_invocation
                or not run.recipe_invocation.completed
            ):
                raise MethodNotAllowed(
                    "Finish the Recipe successfully before adding exploration steps."
                )
        step = step.model_copy(update={"id": step.id or f"step_{len(run.steps) + 1}"})
        if any(record.step.id == step.id for record in run.steps):
            raise InvalidBinding(
                "This step ID is already recorded. Inspect the existing result before continuing.",
                run_id=run_id,
                step_id=step.id,
            )
        self._enforce(run, step)
        self.registry.plannable(step.method, step.method_version)
        if "period" not in run.plan.scope:
            self._prepare_scope(run, run.plan.scope)
        if await self._pause(
            creds,
            run,
            {
                "kind": "step",
                "step": step.model_dump(mode="json"),
                "author": author.model_dump(mode="json") if author else None,
            },
        ):
            await self.store.save(run)
            return run, Result(
                status="needs_input",
                run_id=run.id,
                needs_input={
                    **run.needs_input,
                    "scope_revision": run.scope_revision,
                    "next_tool": "set_run_scope",
                },
            )
        run.running, run.error = RunningJob(kind="step", method=step.method), None
        run.active_step = step.model_copy(deep=True)
        await self.store.save(run)
        _done, result = await self._run_job(
            run_id, lambda r: self._execute(creds, r, step, author=author), wait
        )
        return await self.store.get(run_id), result

    async def skill_query(
        self, creds, caller, run_id, step_id, req, author=None, wait=None
    ):
        from .skills import active, query

        async with self._scope_locks.setdefault(run_id, asyncio.Lock()):
            run = await self._owned(run_id, caller)
            active(run, step_id)
            if run.running:
                raise RunBusy("A query is already running.")
            run.running, run.error = (
                RunningJob(kind="step", method=run.steps[-1].step.method),
                None,
            )
            await self.store.save(run)
            _done, value = await self._run_job(
                run.id,
                lambda current: query(self, creds, current, step_id, req, author),
                wait,
            )
            return await self.store.get(run.id), value

    async def finish_skill(
        self, creds, caller, run_id, step_id, req, author=None, wait=None
    ):
        from .skills import finish

        async with self._scope_locks.setdefault(run_id, asyncio.Lock()):
            run = await self._owned(run_id, caller)
            if run.running:
                raise RunBusy("Wait for the active query to finish.")
            finish(self, run, step_id, req, author)
            await self.store.save(run)
            if (
                req.status == "completed"
                and run.recipe_snapshot
                and run.recipe_snapshot.mode == "pipeline"
            ):
                run.running = RunningJob(kind="pipeline")
                await self.store.save(run)
                await self._run_job(
                    run.id, lambda current: self._pipeline(creds, current), wait
                )
            return await self.store.get(run.id)

    async def complete(
        self,
        caller: CallerInfo,
        run_id: str,
        summary: str | None = None,
        conclusion: RunConclusion | None = None,
        author: ExecutionAuthor | None = None,
    ) -> Run:
        async with self._scope_locks.setdefault(run_id, asyncio.Lock()):
            return await self._complete(caller, run_id, summary, conclusion, author)

    async def _complete(self, caller, run_id, summary, conclusion, author):
        run = await self._owned(run_id, caller)
        if run.active_skill_step:
            raise RunBusy(
                "Finish or refuse the active Skill step before completing the Run."
            )
        attaching = (
            run.status == "completed"
            and not run.summary
            and run.conclusion is not None
            and run.conclusion.source == "execution"
            and conclusion is not None
        )
        if run.status != "open" and not attaching:
            raise RunClosed(
                _("The run is already {status}", status=run.status), run_id=run_id
            )
        if run.running:
            raise RunBusy(
                "Wait for the running step before completing the analysis",
                run_id=run_id,
            )
        unavailable_without_query = bool(
            run.goals
            and conclusion
            and conclusion.goal_outcomes
            and not run.steps
            and not run.query_attempts
            and all(
                outcome.status in ("unsupported", "blocked")
                for outcome in conclusion.goal_outcomes
            )
        )
        if run.needs_input and not unavailable_without_query:
            raise InvalidBinding(
                "Resolve the pending analysis period before completing the Run."
            )
        unsupported_only = bool(
            run.goals and conclusion and conclusion.goal_outcomes and not run.steps
        )
        if run.origin == "mcp" and (
            not run.steps
            and not unsupported_only
            or conclusion is None
            or not conclusion.answer.strip()
            or run.steps
            and not conclusion.findings
            or any(
                not finding.text.strip() or not finding.step_indices
                for finding in conclusion.findings
            )
        ):
            raise AnalysisContractError(
                _(
                    "Complete the analysis with an answer and findings linked to recorded steps."
                ),
                run_id=run_id,
                next_tool="complete_run",
            )
        if conclusion and any(
            i < 0 or i >= len(run.steps)
            for finding in conclusion.findings
            for i in finding.step_indices
        ):
            raise InvalidBinding(
                "Conclusion evidence must reference recorded step indices"
            )
        if run.goals:
            from .goals import validate_outcomes

            validate_outcomes(run, conclusion)
        if unavailable_without_query:
            run.needs_input, run.pending_execution = None, None
        run.conclusion = (
            conclusion.model_copy(update={"source": "caller"}) if conclusion else None
        )
        run.conclusion_author = author
        if conclusion and summary is None:
            summary = conclusion.answer
        run.status, run.summary = "completed", summary
        if not attaching:
            run.finished_at = _now()
        run.ensure_conclusion()
        await self.store.save(run)
        return run

    async def adhoc(
        self,
        creds: Credentials,
        caller: CallerInfo,
        step: PlanStep,
        scope: dict[str, Any],
        wait: float | None = None,
        origin: Literal["python", "api", "web", "mcp"] = "python",
        question: str | None = None,
        author: ExecutionAuthor | None = None,
        preview: bool = False,
    ) -> tuple[Run, Result | None]:
        if origin == "mcp":
            raise AnalysisContractError(
                _(
                    "MCP analysis methods must execute inside an existing Run. Start with start_analysis, then use run_step."
                ),
                next_tool="start_analysis",
            )
        self.registry.plannable(
            step.method, step.method_version
        )  # unknown names fail before anything is stored
        run = Run(
            id=new_id("run"),
            caller=caller,
            origin=origin,
            author=author,
            preview=preview,
            plan=AnalysisPlan(question=question, scope=scope),
            running=RunningJob(kind="adhoc", method=step.method),
        )
        self._prepare_scope(run, scope)
        if await self._pause(
            creds,
            run,
            {
                "kind": "adhoc",
                "step": step.model_dump(mode="json"),
                "author": author.model_dump(mode="json") if author else None,
            },
        ):
            await self.store.save(run)
            return run, Result(
                status="needs_input",
                run_id=run.id,
                needs_input={**run.needs_input, "scope_revision": run.scope_revision},
            )
        await self.store.save(run)

        async def body(r: Run) -> Result:
            result = await self._execute(creds, r, step, author=author)
            if not r.active_skill_step:
                r.status, r.finished_at = "completed", _now()
                r.ensure_conclusion()
            return result

        _done, result = await self._run_job(run.id, body, wait)
        return await self.store.get(run.id), result

    async def recover(self) -> int:
        """Jobs don't survive a restart: mark runs left running as interrupted (called at startup)."""
        runs = await self.store.running()
        for run in runs:
            run.error = {
                "code": "INTERRUPTED",
                "message": _(
                    "The server restarted and interrupted this run. Please request it again"
                ),
            }
            if run.running.kind != "step":
                run.status, run.finished_at = "failed", _now()
            run.running = None
            run.active_step = None
            for record in run.steps:
                if record.skill:
                    for query in record.skill.queries:
                        if query.status == "running":
                            query.status = "interrupted"
                            query.error = {
                                "code": "INTERRUPTED",
                                "message": "Server restarted during this Skill query; use a new query ID to retry.",
                            }
                            query.finished_at = _now()
            for attempt in run.query_attempts:
                if attempt.status == "running":
                    attempt.status, attempt.error_code = "interrupted", "INTERRUPTED"
            await self.store.save(run)
        return len(runs)

    # ── access ────────────────────────────────────────────────────────────
    async def get(self, creds: Credentials, caller: CallerInfo, run_id: str) -> Run:
        return await visible_run(self.store, self.provider, creds, caller, run_id)

    async def list(
        self, caller: CallerInfo, limit: int = 50, recipe: str | None = None
    ) -> list[Run]:
        return await self.store.list(limit, recipe, subject=caller.subject)

    async def share(self, caller: CallerInfo, run_id: str, subjects: list[str]) -> Run:
        run = await self._owned(run_id, caller)
        run.shared_with = sorted(set(subjects))
        await self.store.save(run)
        return run

    async def delete(self, caller: CallerInfo, run_id: str) -> None:
        run = await self._owned(run_id, caller)
        if run.running:
            raise RunBusy(
                _("Wait for the current analysis to finish before deleting its run"),
                run_id=run_id,
            )
        await self.store.delete(run_id)

    async def _owned(self, run_id: str, caller: CallerInfo) -> Run:
        return await owned_run(self.store, run_id, caller)

    # ── jobs ──────────────────────────────────────────────────────────────
    async def _run_job(self, run_id: str, body, wait: float | None):
        """Run body(run) in the background; (finished, value). A job error surfaces here when it
        finishes within the wait, and is always recorded on the run (run.error)."""

        async def job():
            run = await self.store.get(run_id)
            try:
                async with asyncio.timeout(self.policy.deadline_seconds):
                    return await body(run)
            except Exception as e:
                known = isinstance(e, DecisionLayerError)
                run.error = {
                    "code": e.code
                    if known
                    else "EXECUTION_TIMEOUT"
                    if isinstance(e, TimeoutError)
                    else "INTERNAL_ERROR",
                    "message": e.message
                    if known
                    else _(
                        "Execution timed out. The provider query may still be running; narrow the period before retrying."
                    )
                    if isinstance(e, TimeoutError)
                    else _("An internal error occurred while running"),
                    "details": e.details if known else {},
                }
                if run.running and run.running.kind != "step":
                    run.status, run.finished_at = "failed", _now()
                if isinstance(e, TimeoutError):
                    raise ExecutionDeadlineExceeded(run.error["message"]) from e
                raise
            finally:
                run.running = None
                run.active_step = None
                await self.store.save(run)

        return await self.jobs.settle(self.jobs.submit(job), wait)

    # ── internals ─────────────────────────────────────────────────────────
    async def _pipeline(self, creds: Credentials, run: Run) -> None:
        for index, saved_step in enumerate(run.recipe_snapshot.steps):
            step = saved_step
            aliases = run.recipe_invocation.step_id_map if run.recipe_invocation else {}
            if aliases:
                step = saved_step.model_copy(
                    update={
                        "id": aliases[saved_step.id or f"step_{index + 1}"],
                        "bindings": _recipe_aliases(saved_step.bindings, aliases),
                        "params": _recipe_aliases(saved_step.params, aliases),
                    }
                )
            if run.skill_preview_limit is not None and index > run.skill_preview_limit:
                run.status, run.finished_at = "completed", _now()
                run.ensure_conclusion()
                return
            recorded = next(
                (r for r in run.steps if r.step.id == (step.id or f"step_{index + 1}")),
                None,
            )
            if recorded:
                if recorded.result.status == "success":
                    continue
                return
            try:
                result = await self._execute(creds, run, step, origin="recipe")
            except (
                DecisionLayerError
            ) as e:  # a Recipe that can't run as written is a failed run, recorded
                run.steps.append(
                    _record(step, Result(status="failed", warnings=[e.message]), _now())
                )
                run.status, run.finished_at = "failed", _now()
                break
            if result.status != "success":
                break  # needs_input / refused: stays open, the caller continues with explicit steps
        else:
            if run.recipe_invocation:
                run.recipe_invocation.completed = True
            if run.origin != "mcp" and not run.interactive:
                run.status, run.finished_at = "completed", _now()
        run.ensure_conclusion()

    async def _preview_steps(
        self, creds: Credentials, run: Run, step_index: int
    ) -> None:
        run.validation = await self._recipe_validators(creds, run)
        if any(
            self.registry.get(
                step.method, step.method_version
            ).manifest.agent_executable
            for step in run.recipe_snapshot.steps[: step_index + 1]
        ):
            run.skill_preview_limit = step_index
            await self._pipeline(creds, run)
            return
        for step in run.recipe_snapshot.steps[: step_index + 1]:
            result = await self._execute(creds, run, step, origin="recipe")
            if result.status != "success":
                break
        run.status, run.finished_at = "completed", _now()
        run.ensure_conclusion()

    def _enforce(
        self,
        run: Run,
        step: PlanStep,
        *,
        check_budget: bool = True,
        check_step_limit: bool = True,
    ) -> None:
        enforce_step(
            self.registry,
            self.policy,
            run,
            step,
            check_budget=check_budget,
            check_step_limit=check_step_limit,
        )

    async def _execute(
        self,
        creds: Credentials,
        run: Run,
        step: PlanStep,
        origin: Literal["recipe", "request"] = "request",
        author: ExecutionAuthor | None = None,
    ) -> Result:
        return await execute_step(
            self.registry, self.policy, self._context, creds, run, step, origin, author
        )

    async def _context(self, creds: Credentials, run: Run) -> ExecutionContext:
        return await create_context(self.provider, self.store, self.policy, creds, run)

    async def _recipe_validators(
        self, creds: Credentials, run: Run
    ) -> list[ValidationResult]:
        rec, out = run.recipe_snapshot, []
        date_range = (
            tuple(run.plan.scope["date_range"])
            if run.plan.scope.get("date_range")
            else None
        )
        for ref in rec.validators:
            if ref.name == "complete_period":
                out.append(v.complete_period(date_range))
            elif ref.name == "freshness":
                ctx = await self._context(creds, run)
                try:
                    out.append(
                        await v.freshness(
                            ctx,
                            rec.semantic_scope.primary_metric,
                            date_range,
                            **(
                                {"tolerance_days": ref.params["tolerance_days"]}
                                if "tolerance_days" in ref.params
                                else {}
                            ),
                        )
                    )
                finally:
                    run.validation_queries.extend(ctx.queries)
            else:
                out.append(
                    ValidationResult(
                        validator=ref.name,
                        status="warning",
                        code="UNKNOWN_VALIDATOR",
                        message=_("Skipped unknown validator '{name}'", name=ref.name),
                    )
                )
        return out


def _resolved(rec: Recipe | None) -> dict[str, str]:
    return {"primary_metric": rec.semantic_scope.primary_metric} if rec else {}


def _recipe_aliases(value, aliases):
    if isinstance(value, str) and value.startswith("$steps."):
        parts = value.split(".")
        parts[1] = aliases.get(parts[1], parts[1])
        return ".".join(parts)
    if isinstance(value, list):
        return [_recipe_aliases(item, aliases) for item in value]
    if isinstance(value, dict):
        mapped = {key: _recipe_aliases(item, aliases) for key, item in value.items()}
        if mapped.get("source") == "step":
            mapped["step_id"] = aliases.get(mapped["step_id"], mapped["step_id"])
        return mapped
    return value


def _now() -> datetime:
    return datetime.now(timezone.utc)
