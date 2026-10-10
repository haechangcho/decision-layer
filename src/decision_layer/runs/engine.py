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

from ..core.errors import DecisionLayerError, ProviderAccessDenied
from ..core.ids import new_id, recipe_ref
from ..core.models import (
    AnalysisGoal, AnalysisPlan, CallerInfo, ExecutionAuthor, Filter, PlanStep, Provenance, Recipe, RecipeInvocation, RecipeReview, RecipeSelection, Result, Run, RunConclusion, RunRetryLink, RunningJob, StepRecord, ValidationResult,
)
from ..core.periods import ExecutionPolicy, PeriodChoice, resolve_scope
from ..methods import registry as default_registry
from ..methods import InvalidBinding, MethodRegistry
from ..methods.context import ExecutionContext, NeedsInput, Refused, Scope
from ..recipes.loader import RecipeStore
from ..semantic.provider import Credentials, SemanticProvider
from ..validation import builtin as v
from .expressions import resolve
from .jobs import JobRunner
from .policy import parameter_values, remaining_queries
from .store import RunStore, UnknownRun
from ..i18n import _

DEFAULT_MAX_STEPS = 12
DEFAULT_MAX_QUERIES = 30


class RunClosed(DecisionLayerError):
    code = "RUN_CLOSED"
    http_status = 409


class RunLimitExceeded(DecisionLayerError):
    code = "RUN_LIMIT_EXCEEDED"
    http_status = 422


class RunBusy(DecisionLayerError):
    code = "RUN_BUSY"
    http_status = 409


class MethodNotAllowed(DecisionLayerError):
    code = "METHOD_NOT_ALLOWED"
    http_status = 403


class PreviewStepInvalid(DecisionLayerError):
    code = "PREVIEW_STEP_INVALID"
    http_status = 422


class AnalysisContractError(DecisionLayerError):
    code = "ANALYSIS_CONTRACT_REQUIRED"
    http_status = 422


class ExecutionDeadlineExceeded(DecisionLayerError):
    code = "EXECUTION_TIMEOUT"
    http_status = 422


class RunEngine:
    def __init__(self, provider: SemanticProvider, recipes: RecipeStore, store: RunStore,
                 registry: MethodRegistry = default_registry, jobs: JobRunner | None = None,
                 policy: ExecutionPolicy | None = None) -> None:
        self.provider, self.recipes, self.store, self.registry = provider, recipes, store, registry
        self.jobs = jobs or JobRunner()
        self.policy = policy or ExecutionPolicy()
        self._scope_locks: dict[str, asyncio.Lock] = {}

    def _prepare_scope(self, run: Run, scope: dict[str, Any]) -> None:
        defaults = run.recipe_snapshot.default_scope.model_dump(mode="json") if run.recipe_snapshot and run.recipe_snapshot.default_scope else None
        try:
            run.plan.scope, run.scope_resolution = resolve_scope(scope, defaults, self.policy)
        except ValueError as exc:
            raise InvalidBinding(str(exc)) from exc
        run.execution_policy = self.policy

    async def _pause(self, creds: Credentials, run: Run, pending: dict[str, Any]) -> bool:
        choice = PeriodChoice.model_validate(run.plan.scope["period"])
        issue = self.policy.issue(choice)
        allow_all = self.policy.allow_all
        steps = run.recipe_snapshot.steps[:pending.get("step_index", len(run.recipe_snapshot.steps) - 1) + 1] if run.recipe_snapshot and pending["kind"] in ("pipeline", "preview") else [PlanStep.model_validate(pending["step"])] if pending.get("step") else []
        for step in steps:
            manifest = self.registry.get(step.method).manifest
            fixed = run.recipe_snapshot.method_parameters.get(step.method) if run.recipe_snapshot else None
            params = {**step.params, **(fixed.fixed if fixed else {})}
            if manifest.requires_period or any(spec.meaning == "period" and spec.type == "boolean" and params.get(name, spec.default) is True for name, spec in manifest.parameters.items()):
                allow_all = False
                if choice.mode == "all":
                    issue = _("This analysis needs a date range. Choose its start and end dates.")
        field, candidates = "period", []
        if not issue and choice.mode == "range":
            first = steps[0] if steps else None
            metric = first.bindings.get("metric") if first else None
            if metric == "$scope.primary_metric" or not metric:
                metric = run.recipe_snapshot.semantic_scope.primary_metric if run.recipe_snapshot else None
            if isinstance(metric, str) and not metric.startswith("$"):
                ctx = await self._context(creds, run)
                try:
                    dimension = ctx.time_dimension_for(metric)
                    run.plan.scope["time_dimension"] = dimension
                except NeedsInput as exc:
                    issue, field, candidates = exc.question, "time_dimension", exc.details["candidates"]
                except Refused as exc:
                    issue, field = exc.message, "time_dimension"
        if not issue:
            run.needs_input = None
            run.pending_execution = None
            return False
        reason = "TIME_DIMENSION_REQUIRED" if field == "time_dimension" else "PERIOD_UNRESOLVED" if choice.mode == "unresolved" else "ALL_PERIODS_DISABLED" if choice.mode == "all" and not self.policy.allow_all else "RANGE_REQUIRED" if choice.mode == "all" else "PERIOD_TOO_LONG"
        run.needs_input = {"field": field, "reason_code": reason, "question": _(issue), "candidates": candidates, "policy_revision": self.policy.revision,
                           "allow_all": allow_all, "max_period_days": self.policy.max_period_days}
        if run.pending_execution is not None and run.pending_execution != pending:
            run.scope_revision += 1
        run.pending_execution = pending
        run.running = None
        return True

    async def set_scope(self, creds: Credentials, caller: CallerInfo, run_id: str, scope: dict[str, Any],
                        base_revision: int, wait: float | None = None) -> Run:
        async with self._scope_locks.setdefault(run_id, asyncio.Lock()):
            run = await self._owned(run_id, caller)
            if run.running or run.steps or run.validation_queries or run.query_attempts or run.status != "open":
                raise RunBusy(_("Start a new Run to change the period after execution has started."))
            if run.scope_revision != base_revision:
                raise RunBusy(_("The analysis conditions have changed. Reload the Run before continuing."))
            if not run.pending_execution:
                raise InvalidBinding("This Run has no pending period request.")
            pending = run.pending_execution
            # Filters, inputs and provider context cannot be replaced by a period update.
            if set(scope) - {"period", "date_range", "time_dimension"}:
                raise InvalidBinding("Only period and time dimension may change here.")
            merged = {k: v for k, v in run.plan.scope.items() if k not in ("period", "date_range")}
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
            run.running = RunningJob(kind=kind, method=pending.get("step", {}).get("method"))
            await self.store.save(run)
            async def resume(current: Run):
                if kind == "pipeline":
                    current.validation = await self._recipe_validators(creds, current)
                    await self._pipeline(creds, current)
                elif kind == "preview":
                    await self._preview_steps(creds, current, pending["step_index"])
                else:
                    await self._execute(creds, current, PlanStep.model_validate(pending["step"]), author=ExecutionAuthor.model_validate(pending["author"]) if pending.get("author") else None)
                    if kind == "adhoc":
                        current.status, current.finished_at = "completed", _now()
                        current.ensure_conclusion()
            await self._run_job(run_id, resume, wait)
            return await self.store.get(run_id)

    # ── lifecycle ─────────────────────────────────────────────────────────
    # Execution entry points take `wait`: seconds to wait for the background job (None = until done).
    # They return the run as stored; `run.running` is still set when the job outlived the wait.
    async def start(self, creds: Credentials, caller: CallerInfo, *, recipe: str | None, question: str | None,
                    scope: dict[str, Any], wait: float | None = None,
                    origin: Literal["python", "api", "web", "mcp"] = "python",
                    author: ExecutionAuthor | None = None, goals: list[AnalysisGoal] | None = None,
                    recipe_selection: RecipeSelection | None = None, interactive: bool = False,
                    recipe_review: list[RecipeReview] | None = None, retry_of: RunRetryLink | None = None) -> Run:
        if origin == "mcp" and not (question and question.strip()):
            raise AnalysisContractError(_("Start the analysis with the original user question."), next_tool="start_analysis")
        rec = self.recipes.get(recipe) if recipe else None
        goals = goals or []
        if origin == "mcp" and not goals:
            raise AnalysisContractError("Record the requested answers as goals before execution.", next_tool="start_analysis")
        if len({goal.id for goal in goals}) != len(goals):
            raise InvalidBinding("Goal IDs must be unique.")
        if goals:
            await self.provider.resolve(sorted({ref for goal in goals for ref in goal.semantic_refs}), creds)
        if recipe_selection and not rec:
            raise InvalidBinding("A Recipe selection requires a Recipe.")
        if rec and origin == "mcp" and not recipe_selection:
            raise AnalysisContractError("Record why this Recipe fits and which goals it covers.", next_tool="start_run")
        if rec:
            from ..recipes.routing import compatibility, semantic_refs
            await self.provider.resolve(sorted(semantic_refs(rec.model_dump(mode="json"))), creds)
            selected_ids = recipe_selection.goal_ids if recipe_selection else [goal.id for goal in goals]
            if goals and not selected_ids:
                raise InvalidBinding("Select at least one goal for this Recipe.")
            if set(selected_ids) - {goal.id for goal in goals}:
                raise InvalidBinding("Recipe selection references an unknown goal.")
            check = compatibility(rec, [goal for goal in goals if goal.id in selected_ids], scope.get("inputs") or {})
            if check["conflicts"]:
                raise InvalidBinding("This Recipe cannot cover the selected goals.", conflicts=check["conflicts"])
        if rec:
            scope = {**scope, "inputs": self.registry.input_values(rec.inputs, scope.get("inputs") or {})}
        reviews, candidates = list(recipe_review or []), []
        if origin == "mcp" or reviews:
            from ..recipes.routing import search_recipes, reuse_contract
            candidates = (await search_recipes(self.recipes, self.provider, creds, question or "", goals,
                                               scope.get("inputs") or {}, 5))["candidates"]
            by_ref = {item.recipe: item for item in reviews}
            if len(by_ref) != len(reviews):
                raise InvalidBinding("Review each Recipe version only once.")
            selected_ref = recipe_ref(rec.name, rec.version) if rec else None
            visible_refs = {item["recipe"] for item in candidates} | ({selected_ref} if selected_ref else set())
            if set(by_ref) - visible_refs:
                raise InvalidBinding("Recipe reviews must reference current visible candidates.")
            if any(item.decision == "selected" and item.recipe != selected_ref for item in reviews):
                raise InvalidBinding("The selected review must match the executed Recipe.")
            if rec and recipe_selection:
                if selected_ref in by_ref and by_ref[selected_ref].decision != "selected":
                    raise InvalidBinding("An executed Recipe cannot be recorded as skipped.")
                reviews = [item for item in reviews if item.recipe != selected_ref]
                reviews.append(RecipeReview(recipe=selected_ref, decision="selected", reason=recipe_selection.reason))
                if selected_ref not in {item["recipe"] for item in candidates}:
                    candidates = candidates + [{"recipe": selected_ref, "name": rec.name,
                        "objective": rec.routing.objective, "reuse": reuse_contract(rec)}]
            if not rec:
                missing = [item for item in candidates if item["recipe"] not in by_ref]
                if missing:
                    raise AnalysisContractError("Review the available Recipe candidates before starting a new procedure. Record a concrete skip reason; a historical date in source_question is not a fixed execution period.",
                                                next_tool="find_recipes", candidates=missing)
        filters = [*(rec.semantic_scope.required_filters if rec else []),
                   *(Filter.model_validate(f) for f in scope.get("filters") or [])]
        run = Run(id=new_id("run"), caller=caller, origin=origin, author=author, retry_of=retry_of,
                  plan=AnalysisPlan(question=question, recipe=recipe_ref(rec.name, rec.version) if rec else None,
                                    scope={**scope, "filters": [f.model_dump(mode="json") for f in filters]},
                                    resolved=_resolved(rec)),
                  recipe_snapshot=rec, goals=goals, recipe_selection=recipe_selection, interactive=interactive,
                  recipe_review=reviews, recipe_candidates=candidates,
                  recipe_invocation=RecipeInvocation(recipe=recipe_ref(rec.name, rec.version),
                      goal_ids=selected_ids) if rec else None)
        self._prepare_scope(run, run.plan.scope)
        if await self._pause(creds, run, {"kind": "pipeline" if rec and rec.mode == "pipeline" else "investigation"}):
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

    async def use_recipe(self, creds: Credentials, caller: CallerInfo, run_id: str, recipe: str,
                         selection: RecipeSelection, inputs: dict[str, Any], wait: float | None = None) -> Run:
        """Attach one pipeline to an open exploration without changing earlier query scope."""
        async with self._scope_locks.setdefault(run_id, asyncio.Lock()):
            run = await self._owned(run_id, caller)
            if run.status != "open" or run.running or run.recipe_snapshot:
                raise RunBusy("This Run cannot start another Recipe.")
            rec = self.recipes.get(recipe)
            if rec.mode != "pipeline":
                raise InvalidBinding("Only a pipeline Recipe can be attached to an existing exploration.")
            from ..recipes.routing import compatibility, semantic_refs
            await self.provider.resolve(sorted(semantic_refs(rec.model_dump(mode="json"))), creds)
            if not selection.goal_ids or set(selection.goal_ids) - {goal.id for goal in run.goals}:
                raise InvalidBinding("Select recorded goals for the Recipe.")
            check = compatibility(rec, [goal for goal in run.goals if goal.id in selection.goal_ids], inputs)
            if check["conflicts"]:
                raise InvalidBinding("This Recipe cannot cover the selected goals.", conflicts=check["conflicts"])
            values = self.registry.input_values(rec.inputs, inputs)
            previous_filters = [Filter.model_validate(item) for item in run.plan.scope.get("filters", [])]
            if run.query_attempts and any(item not in previous_filters for item in rec.semantic_scope.required_filters):
                raise InvalidBinding("This Recipe requires different shared filters. Start a new Run.")
            run.recipe_snapshot = rec.model_copy(deep=True)
            run.recipe_selection = selection
            run.plan.recipe = recipe_ref(rec.name, rec.version)
            run.recipe_review.append(RecipeReview(recipe=run.plan.recipe, decision="selected", reason=selection.reason))
            if run.plan.recipe not in {item.get("recipe") for item in run.recipe_candidates}:
                from ..recipes.routing import reuse_contract
                run.recipe_candidates.append({"recipe": run.plan.recipe, "name": rec.name,
                    "objective": rec.routing.objective, "reuse": reuse_contract(rec)})
            run.plan.resolved.update(_resolved(rec))
            run.plan.scope["inputs"] = values
            run.plan.scope["filters"] = [item.model_dump(mode="json") for item in
                previous_filters + [item for item in rec.semantic_scope.required_filters if item not in previous_filters]]
            run.recipe_invocation = RecipeInvocation(recipe=run.plan.recipe, goal_ids=selection.goal_ids,
                step_id_map={step.id or f"step_{index + 1}": f"recipe_1_{step.id or f'step_{index + 1}'}"
                             for index, step in enumerate(rec.steps)})
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

    async def preview(self, creds: Credentials, caller: CallerInfo, recipe: Recipe, step_index: int,
                      scope: dict[str, Any], wait: float | None = None,
                      origin: Literal["python", "api", "web", "mcp"] = "python") -> Run:
        if recipe.mode != "pipeline" or step_index < 0 or step_index >= len(recipe.steps):
            raise PreviewStepInvalid(_("Choose an existing pipeline step to preview"), step_index=step_index)
        scope = {**scope, "inputs": self.registry.input_values(recipe.inputs, scope.get("inputs") or {})}
        filters = [*recipe.semantic_scope.required_filters,
                   *(Filter.model_validate(value) for value in scope.get("filters") or [])]
        run = Run(id=new_id("run"), caller=caller, origin=origin, preview=True, recipe_snapshot=recipe,
                  plan=AnalysisPlan(scope={**scope, "filters": [f.model_dump(mode="json") for f in filters]},
                                    resolved=_resolved(recipe)),
                  running=RunningJob(kind="preview", method=recipe.steps[step_index].method))
        self._prepare_scope(run, run.plan.scope)
        if await self._pause(creds, run, {"kind": "preview", "step_index": step_index}):
            await self.store.save(run)
            return run
        await self.store.save(run)
        await self._run_job(run.id, lambda current: self._preview_steps(creds, current, step_index), wait)
        return await self.store.get(run.id)

    async def step(self, creds: Credentials, caller: CallerInfo, run_id: str, step: PlanStep,
                   wait: float | None = None, author: ExecutionAuthor | None = None) -> tuple[Run, Result | None]:
        async with self._scope_locks.setdefault(run_id, asyncio.Lock()):
            return await self._step(creds, caller, run_id, step, wait, author)

    async def _step(self, creds, caller, run_id, step, wait, author):
        run = await self._owned(run_id, caller)
        if step.id:
            for record in run.steps:
                if record.step.id == step.id:
                    if (record.requested_step or record.step).model_dump() == step.model_dump():
                        return run, record.result
                    raise InvalidBinding("This step ID already has a different request.", step_id=step.id)
            if run.active_step and run.active_step.id == step.id:
                if run.active_step.model_dump() == step.model_dump():
                    return run, None
                raise InvalidBinding("This step ID is executing a different request.", step_id=step.id)
        if run.status != "open":
            raise RunClosed(_("The run is already {status}", status=run.status), run_id=run_id)
        if run.running:
            raise RunBusy(_("The previous step is still running. Request the next step when it has finished"), run_id=run_id)
        if run.origin == "mcp" and not (step.purpose and step.purpose.strip()):
            raise AnalysisContractError(_("Each analysis step needs a purpose explaining how it answers the question."),
                                        run_id=run_id, next_tool="run_step")
        if set(step.goal_ids) - {goal.id for goal in run.goals}:
            raise InvalidBinding("The step references an unknown goal.")
        if run.origin == "mcp" and run.goals and not step.goal_ids:
            raise AnalysisContractError("Link this step to at least one requested goal.", next_tool="run_step")
        if step.exploration and run.recipe_snapshot:
            if not self.policy.allow_recipe_extension or not run.recipe_invocation or not run.recipe_invocation.completed:
                raise MethodNotAllowed("Finish the Recipe successfully before adding exploration steps.")
        step = step.model_copy(update={"id": step.id or f"step_{len(run.steps) + 1}"})
        if any(record.step.id == step.id for record in run.steps):
            raise InvalidBinding("This step ID is already recorded. Inspect the existing result before continuing.",
                                 run_id=run_id, step_id=step.id)
        self._enforce(run, step)
        if "period" not in run.plan.scope:
            self._prepare_scope(run, run.plan.scope)
        if await self._pause(creds, run, {"kind": "step", "step": step.model_dump(mode="json"), "author": author.model_dump(mode="json") if author else None}):
            await self.store.save(run)
            return run, Result(status="needs_input", run_id=run.id, needs_input={**run.needs_input, "scope_revision": run.scope_revision, "next_tool": "set_run_scope"})
        run.running, run.error = RunningJob(kind="step", method=step.method), None
        run.active_step = step.model_copy(deep=True)
        await self.store.save(run)
        _done, result = await self._run_job(run_id, lambda r: self._execute(creds, r, step, author=author), wait)
        return await self.store.get(run_id), result

    async def complete(self, caller: CallerInfo, run_id: str, summary: str | None = None,
                       conclusion: RunConclusion | None = None, author: ExecutionAuthor | None = None) -> Run:
        async with self._scope_locks.setdefault(run_id, asyncio.Lock()):
            return await self._complete(caller, run_id, summary, conclusion, author)

    async def _complete(self, caller, run_id, summary, conclusion, author):
        run = await self._owned(run_id, caller)
        attaching = (run.status == "completed" and not run.summary and run.conclusion is not None
                     and run.conclusion.source == "execution" and conclusion is not None)
        if run.status != "open" and not attaching:
            raise RunClosed(_("The run is already {status}", status=run.status), run_id=run_id)
        if run.running:
            raise RunBusy("Wait for the running step before completing the analysis", run_id=run_id)
        unavailable_without_query = bool(run.goals and conclusion and conclusion.goal_outcomes
            and not run.steps and not run.query_attempts
            and all(outcome.status in ("unsupported", "blocked") for outcome in conclusion.goal_outcomes))
        if run.needs_input and not unavailable_without_query:
            raise InvalidBinding("Resolve the pending analysis period before completing the Run.")
        unsupported_only = bool(run.goals and conclusion and conclusion.goal_outcomes and not run.steps)
        if run.origin == "mcp" and (not run.steps and not unsupported_only or conclusion is None or not conclusion.answer.strip()
                                   or run.steps and not conclusion.findings
                                   or any(not finding.text.strip() or not finding.step_indices for finding in conclusion.findings)):
            raise AnalysisContractError(_("Complete the analysis with an answer and findings linked to recorded steps."),
                                        run_id=run_id, next_tool="complete_run")
        if conclusion and any(i < 0 or i >= len(run.steps) for finding in conclusion.findings for i in finding.step_indices):
            raise InvalidBinding("Conclusion evidence must reference recorded step indices")
        if run.goals:
            from .goals import validate_outcomes
            validate_outcomes(run, conclusion)
        if unavailable_without_query:
            run.needs_input, run.pending_execution = None, None
        run.conclusion = conclusion.model_copy(update={"source": "caller"}) if conclusion else None
        run.conclusion_author = author
        if conclusion and summary is None:
            summary = conclusion.answer
        run.status, run.summary = "completed", summary
        if not attaching:
            run.finished_at = _now()
        run.ensure_conclusion()
        await self.store.save(run)
        return run

    async def adhoc(self, creds: Credentials, caller: CallerInfo, step: PlanStep, scope: dict[str, Any],
                    wait: float | None = None,
                    origin: Literal["python", "api", "web", "mcp"] = "python",
                    question: str | None = None, author: ExecutionAuthor | None = None,
                    preview: bool = False) -> tuple[Run, Result | None]:
        if origin == "mcp":
            raise AnalysisContractError(_("MCP analysis methods must execute inside an existing Run. Start with start_analysis, then use run_step."),
                                        next_tool="start_analysis")
        self.registry.get(step.method)  # unknown names fail before anything is stored
        run = Run(id=new_id("run"), caller=caller, origin=origin, author=author, preview=preview, plan=AnalysisPlan(question=question, scope=scope),
                  running=RunningJob(kind="adhoc", method=step.method))
        self._prepare_scope(run, scope)
        if await self._pause(creds, run, {"kind": "adhoc", "step": step.model_dump(mode="json"), "author": author.model_dump(mode="json") if author else None}):
            await self.store.save(run)
            return run, Result(status="needs_input", run_id=run.id, needs_input={**run.needs_input, "scope_revision": run.scope_revision})
        await self.store.save(run)

        async def body(r: Run) -> Result:
            result = await self._execute(creds, r, step, author=author)
            r.status, r.finished_at = "completed", _now()
            r.ensure_conclusion()
            return result

        _done, result = await self._run_job(run.id, body, wait)
        return await self.store.get(run.id), result

    async def recover(self) -> int:
        """Jobs don't survive a restart: mark runs left running as interrupted (called at startup)."""
        runs = await self.store.running()
        for run in runs:
            run.error = {"code": "INTERRUPTED", "message": _("The server restarted and interrupted this run. Please request it again")}
            if run.running.kind != "step":
                run.status, run.finished_at = "failed", _now()
            run.running = None
            run.active_step = None
            for attempt in run.query_attempts:
                if attempt.status == "running":
                    attempt.status, attempt.error_code = "interrupted", "INTERRUPTED"
            await self.store.save(run)
        return len(runs)

    # ── access ────────────────────────────────────────────────────────────
    async def get(self, creds: Credentials, caller: CallerInfo, run_id: str) -> Run:
        """Owner, or a viewer the run is shared with whose catalog covers everything it used."""
        run = await self.store.get(run_id)
        if _owns(run, caller):
            return run
        if not _shared_with(run, caller):
            raise UnknownRun(_("Run not found: {run_id}", run_id=run_id))  # same answer as a missing run
        visible = {o.ref for o in (await self.provider.discover(creds)).objects if o.public}
        from ..recipes.routing import semantic_refs
        used = {r for s in run.steps for r in s.result.provenance.semantic_refs}
        used.update(semantic_refs([attempt.spec.model_dump(mode="json") for attempt in run.query_attempts]))
        used.update(ref for goal in run.goals for ref in goal.semantic_refs)
        used.update(semantic_refs(run.recipe_candidates))
        used.update(semantic_refs([item.model_dump(mode="json") for item in run.remediations]))
        if run.retry_of:
            used.update(semantic_refs(run.retry_of.model_dump(mode="json")))
        hidden = sorted(used - visible)
        if hidden:
            raise ProviderAccessDenied(_("This run uses measures or dimensions you don't have access to"), count=len(hidden))
        return run

    async def list(self, caller: CallerInfo, limit: int = 50, recipe: str | None = None) -> list[Run]:
        return await self.store.list(limit, recipe, subject=caller.subject)

    async def share(self, caller: CallerInfo, run_id: str, subjects: list[str]) -> Run:
        run = await self._owned(run_id, caller)
        run.shared_with = sorted(set(subjects))
        await self.store.save(run)
        return run

    async def delete(self, caller: CallerInfo, run_id: str) -> None:
        run = await self._owned(run_id, caller)
        if run.running:
            raise RunBusy(_("Wait for the current analysis to finish before deleting its run"), run_id=run_id)
        await self.store.delete(run_id)

    async def _owned(self, run_id: str, caller: CallerInfo) -> Run:
        run = await self.store.get(run_id)
        if not _owns(run, caller):
            raise UnknownRun(_("Run not found: {run_id}", run_id=run_id))
        return run

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
                run.error = {"code": e.code if known else "EXECUTION_TIMEOUT" if isinstance(e, TimeoutError) else "INTERNAL_ERROR",
                             "message": e.message if known else _("Execution timed out. The provider query may still be running; narrow the period before retrying.") if isinstance(e, TimeoutError) else _("An internal error occurred while running"),
                             "details": e.details if known else {}}
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
                step = saved_step.model_copy(update={"id": aliases[saved_step.id or f"step_{index + 1}"],
                    "bindings": _recipe_aliases(saved_step.bindings, aliases), "params": _recipe_aliases(saved_step.params, aliases)})
            try:
                result = await self._execute(creds, run, step, origin="recipe")
            except DecisionLayerError as e:  # a Recipe that can't run as written is a failed run, recorded
                run.steps.append(_record(step, Result(status="failed", warnings=[e.message]), _now()))
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

    async def _preview_steps(self, creds: Credentials, run: Run, step_index: int) -> None:
        run.validation = await self._recipe_validators(creds, run)
        for step in run.recipe_snapshot.steps[:step_index + 1]:
            result = await self._execute(creds, run, step, origin="recipe")
            if result.status != "success":
                break
        run.status, run.finished_at = "completed", _now()
        run.ensure_conclusion()

    def _enforce(self, run: Run, step: PlanStep, *, check_budget: bool = True) -> None:
        rec = run.recipe_snapshot
        max_steps = rec.limits.max_steps if rec else DEFAULT_MAX_STEPS
        if len(run.steps) >= max_steps:
            raise RunLimitExceeded(_("This run reached its step limit ({limit}). Finish it with complete_run", limit=max_steps))
        if check_budget and remaining_queries(run, self.policy) <= 0:
            raise RunLimitExceeded(_("This run has used its query budget. Finish it with complete_run"))
        if rec is None:
            return
        allowed = rec.allowed_methods if rec.mode == "investigation" else sorted({s.method for s in rec.steps})
        if step.method not in allowed and not step.exploration:
            raise MethodNotAllowed(_("Recipe '{recipe}' does not allow method {method}", recipe=rec.name, method=step.method), allowed=allowed)
        in_scope = {rec.semantic_scope.primary_metric, *rec.semantic_scope.related_metrics}
        method = self.registry.get(step.method)
        for role, spec in method.manifest.roles.items():
            if spec.kind != "measure":
                continue
            value = step.bindings.get(role)
            for ref in value if isinstance(value, list) else [value] if value else []:
                if ref not in in_scope:
                    if isinstance(ref, str) and ref.startswith("$"):
                        continue
                    raise InvalidBinding(_("'{ref}' is outside the metric scope of recipe '{recipe}'", ref=ref, recipe=rec.name), in_scope=sorted(in_scope))

    async def _execute(self, creds: Credentials, run: Run, step: PlanStep,
                       origin: Literal["recipe", "request"] = "request", author: ExecutionAuthor | None = None) -> Result:
        step = step.model_copy(update={"id": step.id or f"step_{len(run.steps) + 1}",
            "goal_ids": run.recipe_invocation.goal_ids if origin == "recipe" and run.recipe_invocation else step.goal_ids})
        installed = self.registry.get(step.method).manifest.version
        if step.method_version and step.method_version != installed:
            raise InvalidBinding("The recorded Method version is not installed. Review the Recipe before changing its version.",
                                 recorded=step.method_version, installed=installed)
        results = {s.step.id: s.result for s in run.steps if s.step.id}
        resolutions: list[dict] = []
        inputs = run.plan.scope.get("inputs", {})
        from .expressions import AmbiguousSelection
        try:
            resolved = step.model_copy(update={"bindings": resolve(step.bindings, run.recipe_snapshot, results, inputs, resolutions, "bindings"),
                                               "params": resolve(step.params, run.recipe_snapshot, results, inputs, resolutions, "params")})
        except AmbiguousSelection as e:
            result = Result(status="needs_input", needs_input={"question": e.message, "field": e.details["field"],
                            "candidates": [{"value": candidate["path"], "label": str(candidate["path"][-1]["value"])}
                                           for candidate in e.details["candidates"]]},
                            provenance=Provenance(method=self.registry.get(step.method).ref))
            result.run_id = run.id
            result.step_id = step.id
            record = _record(step, result, _now())
            record.requested_step, record.author = step.model_copy(deep=True), author
            run.steps.append(record)
            run.plan.steps.append(step.model_copy(deep=True))
            return result
        provided, fixed = parameter_values(run, resolved.method, resolved.params, origin)
        sources = {name: "recipe_fixed" if name in fixed else origin if name in provided else "method_default"
                   for name in self.registry.get(resolved.method).manifest.parameters}
        resolved = resolved.model_copy(update={"params": self.registry.resolve_params(resolved.method, provided)})
        self._enforce(run, resolved, check_budget=False)
        started = _now()
        ctx = await self._context(creds, run)
        ctx.step_id = step.id
        result = await self.registry.run(resolved.method, ctx, resolved.bindings,
                                         resolved.params)
        result.run_id = run.id
        result.step_id = step.id
        record = _record(resolved, result, started, sources)
        record.requested_step = step.model_copy(deep=True)
        record.input_resolutions = resolutions
        record.author = author
        if run.recipe_invocation and not step.exploration:
            record.invocation_id = run.recipe_invocation.id
            run.recipe_invocation.step_ids.append(step.id)
        run.steps.append(record)
        run.plan.steps.append(step.model_copy(deep=True))
        return result

    async def _context(self, creds: Credentials, run: Run) -> ExecutionContext:
        if run.query_attempt_baseline is None:
            legacy = len(run.validation_queries) + sum(len(s.result.provenance.queries) for s in run.steps)
            run.query_attempt_baseline = max(0, legacy - len(run.query_attempts))
        scope = run.plan.scope
        catalog = await self.provider.discover(creds)
        allowed = None
        if run.recipe_snapshot:
            allowed = {run.recipe_snapshot.semantic_scope.primary_metric, *run.recipe_snapshot.semantic_scope.related_metrics}
            for ref in list(allowed):
                obj = catalog.get(ref)
                if obj:
                    allowed.update(obj.ratio_parts or [])
                    if obj.count_measure:
                        allowed.add(obj.count_measure)
        async def persist():
            await self.store.save(run)
        return ExecutionContext(
            provider=self.provider, credentials=creds, catalog=catalog,
            scope=Scope(tuple(scope["date_range"]) if scope.get("date_range") else None, scope.get("time_dimension"),
                        [Filter.model_validate(f) for f in scope.get("filters") or []]),
            max_queries=min(remaining_queries(run, self.policy), self.policy.max_queries), execution_policy=self.policy,
            attempts=run.query_attempts, persist_attempts=persist, allowed_measures=allowed)

    async def _recipe_validators(self, creds: Credentials, run: Run) -> list[ValidationResult]:
        rec, out = run.recipe_snapshot, []
        date_range = tuple(run.plan.scope["date_range"]) if run.plan.scope.get("date_range") else None
        for ref in rec.validators:
            if ref.name == "complete_period":
                out.append(v.complete_period(date_range))
            elif ref.name == "freshness":
                ctx = await self._context(creds, run)
                try:
                    out.append(await v.freshness(ctx, rec.semantic_scope.primary_metric, date_range,
                                                 **({"tolerance_days": ref.params["tolerance_days"]}
                                                    if "tolerance_days" in ref.params else {})))
                finally:
                    run.validation_queries.extend(ctx.queries)
            else:
                out.append(ValidationResult(validator=ref.name, status="warning", code="UNKNOWN_VALIDATOR",
                                            message=_("Skipped unknown validator '{name}'", name=ref.name)))
        return out


def _record(step: PlanStep, result: Result, started: datetime,
            parameter_sources: dict[str, Literal["method_default", "recipe", "recipe_fixed", "request"]] | None = None) -> StepRecord:
    return StepRecord(step=step, method=result.provenance.method or "method://unknown@0.0.0", result=result,
                      started_at=started, finished_at=_now(), parameter_sources=parameter_sources or {})


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


def _owns(run: Run, caller: CallerInfo) -> bool:
    return bool(caller.subject) and run.caller.subject == caller.subject


def _shared_with(run: Run, caller: CallerInfo) -> bool:
    return bool(caller.subject) and (caller.subject in run.shared_with or "*" in run.shared_with)


def _now() -> datetime:
    return datetime.now(timezone.utc)
