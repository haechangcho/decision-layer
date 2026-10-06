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

from datetime import datetime, timezone
from typing import Any, Literal

from ..core.errors import DecisionLayerError, ProviderAccessDenied
from ..core.ids import new_id, recipe_ref
from ..core.models import (
    AnalysisPlan, CallerInfo, ExecutionAuthor, Filter, PlanStep, Recipe, Result, Run, RunConclusion, RunningJob, StepRecord, ValidationResult,
)
from ..methods import registry as default_registry
from ..methods.base import InvalidBinding, MethodRegistry
from ..methods.context import ExecutionContext, Scope
from ..recipes.loader import RecipeStore
from ..semantic.provider import Credentials, SemanticProvider
from ..validation import builtin as v
from .expressions import resolve
from .jobs import JobRunner
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


class RunEngine:
    def __init__(self, provider: SemanticProvider, recipes: RecipeStore, store: RunStore,
                 registry: MethodRegistry = default_registry, jobs: JobRunner | None = None) -> None:
        self.provider, self.recipes, self.store, self.registry = provider, recipes, store, registry
        self.jobs = jobs or JobRunner()

    # ── lifecycle ─────────────────────────────────────────────────────────
    # Execution entry points take `wait`: seconds to wait for the background job (None = until done).
    # They return the run as stored; `run.running` is still set when the job outlived the wait.
    async def start(self, creds: Credentials, caller: CallerInfo, *, recipe: str | None, question: str | None,
                    scope: dict[str, Any], wait: float | None = None,
                    origin: Literal["python", "api", "web", "mcp"] = "python",
                    author: ExecutionAuthor | None = None) -> Run:
        rec = self.recipes.get(recipe) if recipe else None
        if rec and rec.default_scope is not None:
            scope = {**rec.default_scope.model_dump(mode="json"), **scope}
        filters = [*(rec.semantic_scope.required_filters if rec else []),
                   *(Filter.model_validate(f) for f in scope.get("filters") or [])]
        run = Run(id=new_id("run"), caller=caller, origin=origin, author=author,
                  plan=AnalysisPlan(question=question, recipe=recipe_ref(rec.name, rec.version) if rec else None,
                                    scope={**scope, "filters": [f.model_dump(mode="json") for f in filters]},
                                    resolved=_resolved(rec)),
                  recipe_snapshot=rec)
        if rec:
            run.validation = await self._recipe_validators(creds, run)
        if not (rec and rec.mode == "pipeline"):
            await self.store.save(run)
            return run
        run.running = RunningJob(kind="pipeline")
        await self.store.save(run)
        await self._run_job(run.id, lambda r: self._pipeline(creds, r), wait)
        return await self.store.get(run.id)

    async def preview(self, creds: Credentials, caller: CallerInfo, recipe: Recipe, step_index: int,
                      scope: dict[str, Any], wait: float | None = None,
                      origin: Literal["python", "api", "web", "mcp"] = "python") -> Run:
        if recipe.mode != "pipeline" or step_index < 0 or step_index >= len(recipe.steps):
            raise PreviewStepInvalid(_("Choose an existing pipeline step to preview"), step_index=step_index)
        if recipe.default_scope is not None:
            scope = {**recipe.default_scope.model_dump(mode="json"), **scope}
        filters = [*recipe.semantic_scope.required_filters,
                   *(Filter.model_validate(value) for value in scope.get("filters") or [])]
        run = Run(id=new_id("run"), caller=caller, origin=origin, preview=True, recipe_snapshot=recipe,
                  plan=AnalysisPlan(scope={**scope, "filters": [f.model_dump(mode="json") for f in filters]},
                                    resolved=_resolved(recipe)),
                  running=RunningJob(kind="preview", method=recipe.steps[step_index].method))
        await self.store.save(run)
        await self._run_job(run.id, lambda current: self._preview_steps(creds, current, step_index), wait)
        return await self.store.get(run.id)

    async def step(self, creds: Credentials, caller: CallerInfo, run_id: str, step: PlanStep,
                   wait: float | None = None, author: ExecutionAuthor | None = None) -> tuple[Run, Result | None]:
        run = await self._owned(run_id, caller)
        if run.status != "open":
            raise RunClosed(_("The run is already {status}", status=run.status), run_id=run_id)
        if run.running:
            raise RunBusy(_("The previous step is still running. Request the next step when it has finished"), run_id=run_id)
        self._enforce(run, step)
        run.running, run.error = RunningJob(kind="step", method=step.method), None
        await self.store.save(run)
        _done, result = await self._run_job(run_id, lambda r: self._execute(creds, r, step, author=author), wait)
        return await self.store.get(run_id), result

    async def complete(self, caller: CallerInfo, run_id: str, summary: str | None = None,
                       conclusion: RunConclusion | None = None, author: ExecutionAuthor | None = None) -> Run:
        run = await self._owned(run_id, caller)
        attaching = (run.status == "completed" and not run.summary and run.conclusion is not None
                     and run.conclusion.source == "execution" and conclusion is not None)
        if run.status != "open" and not attaching:
            raise RunClosed(_("The run is already {status}", status=run.status), run_id=run_id)
        if run.running:
            raise RunBusy("Wait for the running step before completing the analysis", run_id=run_id)
        if conclusion and any(i < 0 or i >= len(run.steps) for finding in conclusion.findings for i in finding.step_indices):
            raise InvalidBinding("Conclusion evidence must reference recorded step indices")
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
                    question: str | None = None, author: ExecutionAuthor | None = None) -> tuple[Run, Result | None]:
        self.registry.get(step.method)  # unknown names fail before anything is stored
        run = Run(id=new_id("run"), caller=caller, origin=origin, author=author, plan=AnalysisPlan(question=question, scope=scope),
                  running=RunningJob(kind="adhoc", method=step.method))
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
        visible = {o.ref for o in (await self.provider.discover(creds)).objects}
        hidden = sorted({r for s in run.steps for r in s.result.provenance.semantic_refs} - visible)
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
                return await body(run)
            except Exception as e:
                known = isinstance(e, DecisionLayerError)
                run.error = {"code": e.code if known else "INTERNAL_ERROR",
                             "message": e.message if known else _("An internal error occurred while running"),
                             "details": e.details if known else {}}
                if run.running and run.running.kind != "step":
                    run.status, run.finished_at = "failed", _now()
                raise
            finally:
                run.running = None
                await self.store.save(run)

        return await self.jobs.settle(self.jobs.submit(job), wait)

    # ── internals ─────────────────────────────────────────────────────────
    async def _pipeline(self, creds: Credentials, run: Run) -> None:
        for step in run.recipe_snapshot.steps:
            try:
                result = await self._execute(creds, run, step, origin="recipe")
            except DecisionLayerError as e:  # a Recipe that can't run as written is a failed run, recorded
                run.steps.append(_record(step, Result(status="failed", warnings=[e.message]), _now()))
                run.status, run.finished_at = "failed", _now()
                break
            if result.status != "success":
                break  # needs_input / refused: stays open, the caller continues with explicit steps
        else:
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

    def _enforce(self, run: Run, step: PlanStep) -> None:
        rec = run.recipe_snapshot
        max_steps = rec.limits.max_steps if rec else DEFAULT_MAX_STEPS
        if len(run.steps) >= max_steps:
            raise RunLimitExceeded(_("This run reached its step limit ({limit}). Finish it with complete_run", limit=max_steps))
        if self._queries_left(run) <= 0:
            raise RunLimitExceeded(_("This run has used its query budget. Finish it with complete_run"))
        if rec is None:
            return
        allowed = rec.allowed_methods if rec.mode == "investigation" else sorted({s.method for s in rec.steps})
        if step.method not in allowed:
            raise MethodNotAllowed(_("Recipe '{recipe}' does not allow method {method}", recipe=rec.name, method=step.method), allowed=allowed)
        in_scope = {rec.semantic_scope.primary_metric, *rec.semantic_scope.related_metrics}
        method = self.registry.get(step.method)
        for role, spec in method.manifest.roles.items():
            if spec.kind != "measure":
                continue
            value = step.bindings.get(role)
            for ref in value if isinstance(value, list) else [value] if value else []:
                if ref not in in_scope:
                    raise InvalidBinding(_("'{ref}' is outside the metric scope of recipe '{recipe}'", ref=ref, recipe=rec.name), in_scope=sorted(in_scope))
        self._apply_parameter_policy(run, step.method, step.params, origin="request")

    @staticmethod
    def _apply_parameter_policy(run: Run, method: str, params: dict[str, Any],
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

    def _queries_left(self, run: Run) -> int:
        budget = run.recipe_snapshot.limits.max_queries if run.recipe_snapshot else DEFAULT_MAX_QUERIES
        return budget - sum(len(s.result.provenance.queries) for s in run.steps)

    async def _execute(self, creds: Credentials, run: Run, step: PlanStep,
                       origin: Literal["recipe", "request"] = "request", author: ExecutionAuthor | None = None) -> Result:
        installed = self.registry.get(step.method).manifest.version
        if step.method_version and step.method_version != installed:
            raise InvalidBinding("The recorded Method version is not installed. Review the Recipe before changing its version.",
                                 recorded=step.method_version, installed=installed)
        results = {s.step.id: s.result for s in run.steps if s.step.id}
        resolved = step.model_copy(update={"bindings": resolve(step.bindings, run.recipe_snapshot, results),
                                           "params": resolve(step.params, run.recipe_snapshot, results)})
        provided, fixed = self._apply_parameter_policy(run, resolved.method, resolved.params, origin)
        sources = {name: "recipe_fixed" if name in fixed else origin if name in provided else "method_default"
                   for name in self.registry.get(resolved.method).manifest.parameters}
        resolved = resolved.model_copy(update={"params": self.registry.resolve_params(resolved.method, provided)})
        started = _now()
        result = await self.registry.run(resolved.method, await self._context(creds, run), resolved.bindings,
                                         resolved.params)
        result.run_id = run.id
        record = _record(resolved, result, started, sources)
        record.author = author
        run.steps.append(record)
        run.plan.steps.append(resolved)
        return result

    async def _context(self, creds: Credentials, run: Run) -> ExecutionContext:
        scope = run.plan.scope
        return ExecutionContext(
            provider=self.provider, credentials=creds, catalog=await self.provider.discover(creds),
            scope=Scope(tuple(scope["date_range"]) if scope.get("date_range") else None, scope.get("time_dimension"),
                        [Filter.model_validate(f) for f in scope.get("filters") or []]),
            max_queries=self._queries_left(run))

    async def _recipe_validators(self, creds: Credentials, run: Run) -> list[ValidationResult]:
        rec, out = run.recipe_snapshot, []
        date_range = tuple(run.plan.scope["date_range"]) if run.plan.scope.get("date_range") else None
        for ref in rec.validators:
            if ref.name == "complete_period":
                out.append(v.complete_period(date_range))
            elif ref.name == "freshness":
                ctx = await self._context(creds, run)
                out.append(await v.freshness(ctx, rec.semantic_scope.primary_metric, date_range,
                                             **({"tolerance_days": ref.params["tolerance_days"]}
                                                if "tolerance_days" in ref.params else {})))
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


def _owns(run: Run, caller: CallerInfo) -> bool:
    return bool(caller.subject) and run.caller.subject == caller.subject


def _shared_with(run: Run, caller: CallerInfo) -> bool:
    return bool(caller.subject) and (caller.subject in run.shared_with or "*" in run.shared_with)


def _now() -> datetime:
    return datetime.now(timezone.utc)
