"""Methods HTTP routes; analytical work stays in the canonical engine."""
from __future__ import annotations
from fastapi import Request
from ..core.models import MethodManifest, PlanStep, Result
from ..methods import registry
from ..service import MethodRunRequest
from fastapi import APIRouter
from .dependencies import Caller, Creds, accepted, localized, run_origin, waited

def create_router(settings, engine):
    router = APIRouter()
    @router.get("/methods", response_model=list[MethodManifest])
    async def methods() -> list[MethodManifest]:
        return [localized(m) for m in registry.manifests()]

    @router.get("/methods/{name}", response_model=MethodManifest)
    async def method(name: str) -> MethodManifest:
        return localized(registry.get(name).manifest)

    @router.post("/methods/{name}:run", response_model=Result, responses={202: {"description": "still running"}})
    async def method_run(name: str, req: MethodRunRequest, creds: Creds, caller: Caller, request: Request,
                         wait: float | None = None):
        """Ad-hoc Method run, stored as a single-step Run owned by the caller. Answers the Result when it
        finishes within `wait` seconds, else 202 {run_id, poll} — then poll GET /runs/{run_id}/result."""
        run, result = await engine.adhoc(creds, caller, PlanStep(method=name, bindings=req.bindings, params=req.params),
                                         req.scope.as_dict(), wait=waited(settings, wait), origin=run_origin(request), question=req.question, author=req.author)
        return result if result is not None else accepted(run)

    return router
