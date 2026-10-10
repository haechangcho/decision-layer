"""Runs HTTP routes; analytical work stays in the canonical engine."""
from __future__ import annotations
from fastapi import Query, Request
from fastapi.responses import JSONResponse, Response
from ..i18n import _
from ..core.models import PlanStep, Recipe, Result, Run
from ..methods import registry
from ..recipes.from_run import RecipeCandidate, RunPromotionError, candidate_from_run, runtime_recipe_from_run
from ..service import MethodProposalRequest, RunCompleteRequest, RunRecipeRequest, RunScopeRequest, RunShareRequest, RunStartRequest, RunStepRequest, RunUseRecipeRequest
from ..service import BlockedAnalysisRequest, RemediationCreateRequest, RemediationReviewRequest, RemediationCheckRequest, RemediationRetryRequest
from ..runs import remediation
from ..i18n import _
from fastapi import APIRouter
from .dependencies import Caller, Creds, JobFailed, NoResult, accepted, run_origin, waited

from ..recipes.authoring import check_recipe_semantics

def create_router(settings, provider, recipes, engine):
    router = APIRouter()
    @router.post("/runs", response_model=Run, responses={202: {"description": "pipeline still running"}})
    async def run_start(req: RunStartRequest, creds: Creds, caller: Caller, request: Request, wait: float | None = None):
        """Start a Run. A pipeline Recipe executes right away (202 with the run while it is still running);
        an investigation Recipe waits for steps."""
        run = await engine.start(creds, caller, recipe=req.recipe, question=req.question, scope=req.scope.as_dict(),
                                 wait=waited(settings, wait), origin=run_origin(request), author=req.author,
                                 goals=req.goals, recipe_selection=req.recipe_selection,
                                 recipe_review=req.recipe_review, interactive=req.interactive)
        return JSONResponse(status_code=202, content=run.model_dump(mode="json")) if run.running else run

    @router.get("/runs", response_model=list[Run])
    async def runs_list(caller: Caller, limit: int = 50, recipe: str | None = None) -> list[Run]:
        """The caller's own runs, newest first."""
        return await engine.list(caller, limit, recipe)

    @router.post("/analyses:blocked", response_model=Run)
    async def analysis_blocked(req: BlockedAnalysisRequest, caller: Caller, request: Request):
        """Record an unanswered question and proposed improvements, without executing a query."""
        return await remediation.record_blocked(engine, caller, req, run_origin(request))

    @router.post("/runs/{run_id}/method-proposal")
    async def run_method_proposal(run_id: str, req: MethodProposalRequest, caller: Caller):
        from ..runs.proposals import method_proposal
        run = await engine._owned(run_id, caller)
        return method_proposal(run, req, settings.issue_repository)

    @router.post("/runs/{run_id}:use-recipe", response_model=Run)
    async def run_use_recipe(run_id: str, req: RunUseRecipeRequest, creds: Creds, caller: Caller, wait: float | None = None):
        run = await engine.use_recipe(creds, caller, run_id, req.recipe, req.selection, req.inputs, waited(settings, wait))
        return JSONResponse(status_code=202, content=run.model_dump(mode="json")) if run.running else run

    @router.get("/runs/{run_id}/recipe-candidate", response_model=RecipeCandidate)
    async def run_recipe_candidate(run_id: str, creds: Creds, caller: Caller, indices: list[int] = Query(...)) -> RecipeCandidate:
        run = await engine.get(creds, caller, run_id)
        candidate = candidate_from_run(run, indices)
        await check_recipe_semantics(candidate.recipe, provider, creds)
        return candidate

    @router.post("/runs/{run_id}/recipe", response_model=Recipe)
    async def run_recipe_register(run_id: str, creds: Creds, caller: Caller, body: RunRecipeRequest = RunRecipeRequest()) -> Recipe:
        run = await engine.get(creds, caller, run_id)
        if run.status != "completed" or run.running:
            raise RunPromotionError("Complete the analysis before registering its procedure.")
        from ..recipes.loader import UnknownRecipe
        name = f"analysis-from-{run.id.lower()}"
        if body.recipe is None:
            try:
                existing = recipes.get(name, include_drafts=True)
            except UnknownRecipe:
                existing = None
            if existing and existing.origin_runs == [run.id] and existing.status == "published":
                await check_recipe_semantics(existing, provider, creds)
                return existing
        recipe = (body.recipe or runtime_recipe_from_run(run)).model_copy(update={"name": name, "origin_runs": [run.id], "status": "published"})
        from ..recipes.authoring import validate_recipe
        validate_recipe(recipe)
        for step in recipe.steps:
            if step.method_version and registry.get(step.method).manifest.version != step.method_version:
                raise RunPromotionError("The recorded Method version is not installed. Edit the candidate before registering it.")
        await check_recipe_semantics(recipe, provider, creds)
        # A repeated click returns the same version instead of making another Recipe.
        from ..recipes.loader import UnknownRecipe
        try:
            existing = recipes.get(recipe.name, include_drafts=True)
        except UnknownRecipe:
            return recipes.save(recipe, None)
        if existing.origin_runs != [run.id] or existing.status != "published":
            from ..recipes.authoring import RecipeConflict
            raise RecipeConflict("A different Recipe already uses this name.")
        if existing.model_dump() != recipe.model_dump():
            from ..recipes.authoring import RecipeConflict
            raise RecipeConflict("This Run already has a different published Recipe. Save changes as a new version in the editor.")
        return existing

    @router.get("/runs/{run_id}", response_model=Run)
    async def run_get(run_id: str, creds: Creds, caller: Caller) -> Run:
        return await engine.get(creds, caller, run_id)

    @router.post("/runs/{run_id}/remediations", response_model=Run)
    async def remediation_create(run_id: str, req: RemediationCreateRequest, caller: Caller):
        return await remediation.create(engine, caller, run_id, req)

    @router.put("/runs/{run_id}/remediations/{item_id}", response_model=Run)
    async def remediation_review(run_id: str, item_id: str, req: RemediationReviewRequest, caller: Caller):
        return await remediation.review(engine, caller, run_id, item_id, req)

    @router.post("/runs/{run_id}/remediations/{item_id}:check", response_model=Run)
    async def remediation_check(run_id: str, item_id: str, req: RemediationCheckRequest, creds: Creds, caller: Caller):
        return await remediation.recheck(engine, creds, caller, run_id, item_id, req)

    @router.post("/runs/{run_id}/remediations/{item_id}:retry", response_model=Run)
    async def remediation_retry(run_id: str, item_id: str, req: RemediationRetryRequest, creds: Creds,
                                caller: Caller, request: Request, wait: float | None = None):
        run = await remediation.retry(engine, creds, caller, run_id, item_id, req, run_origin(request), waited(settings, wait))
        return JSONResponse(status_code=202, content=run.model_dump(mode="json")) if run.running else run

    @router.put("/runs/{run_id}/scope", response_model=Run)
    async def run_scope(run_id: str, req: RunScopeRequest, creds: Creds, caller: Caller, wait: float | None = None):
        run = await engine.set_scope(creds, caller, run_id, req.scope.as_dict(), req.base_revision, waited(settings, wait))
        return JSONResponse(status_code=202, content=run.model_dump(mode="json")) if run.running else run

    @router.delete("/runs/{run_id}", status_code=204)
    async def run_delete(run_id: str, caller: Caller) -> Response:
        await engine.delete(caller, run_id)
        return Response(status_code=204)

    @router.get("/runs/{run_id}/result", response_model=Result, responses={202: {"description": "still running"}})
    async def run_result(run_id: str, creds: Creds, caller: Caller):
        """The latest step's Result — 202 while a job runs, the recorded error if the job failed."""
        run = await engine.get(creds, caller, run_id)
        if run.running:
            return accepted(run)
        if run.error:
            raise JobFailed(run.error)
        if run.needs_input:
            return Result(status="needs_input", run_id=run.id, needs_input={**run.needs_input, "scope_revision": run.scope_revision})
        if not run.steps:
            raise NoResult(_("No step has run yet"), run_id=run_id)
        return run.steps[-1].result

    @router.post("/runs/{run_id}/steps", response_model=Result, responses={202: {"description": "still running"}})
    async def run_step(run_id: str, req: RunStepRequest, creds: Creds, caller: Caller, wait: float | None = None):
        run, result = await engine.step(creds, caller, run_id, PlanStep(**req.model_dump(exclude={"author"})), wait=waited(settings, wait), author=req.author)
        return result if result is not None else accepted(run)

    @router.post("/runs/{run_id}:complete", response_model=Run)
    async def run_complete(run_id: str, req: RunCompleteRequest, caller: Caller) -> Run:
        return await engine.complete(caller, run_id, req.summary, req.conclusion, req.author)

    @router.post("/runs/{run_id}:share", response_model=Run)
    async def run_share(run_id: str, req: RunShareRequest, caller: Caller) -> Run:
        """Owner only. Replaces the read-only share list; "*" = any authenticated caller."""
        return await engine.share(caller, run_id, req.subjects)

    return router
