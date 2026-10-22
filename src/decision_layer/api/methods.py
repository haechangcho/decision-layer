"""Methods HTTP routes; analytical work stays in the canonical engine."""
from __future__ import annotations
from fastapi import Request
from ..core.models import MethodManifest, PlanStep, Result
from ..service import MethodRunRequest
from ..methods.assets import DraftRequest, RevisionRequest
from ..core.errors import DecisionLayerError
from ..methods.invocation import invocation_inputs
from fastapi import APIRouter
from .dependencies import Caller, Creds, accepted, localized, run_origin, waited
from pydantic import BaseModel, ConfigDict, Field


class FormatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=150_000)

def create_router(settings, engine):
    registry = engine.registry
    router = APIRouter()
    @router.get("/methods", response_model=list[MethodManifest])
    async def methods() -> list[MethodManifest]:
        return [localized(m) for m in registry.manifests()]

    @router.get("/method-guides/{name}")
    async def authoring_guide(name: str):
        from ..methods.skills import get_authoring_guide
        return get_authoring_guide(name)

    def permitted(caller, publish=False):
        from .dependencies import require_method_permission
        from ..methods.assets import AssetError
        if not settings.allow_method_editing or not settings.method_assets_dir:
            raise AssetError("Method editing is disabled by the operator")
        require_method_permission(settings, caller, publish=publish)

    @router.get("/methods/{name}/source")
    async def source(name: str, caller: Caller, request: Request):
        asset = registry.get(name)
        store = request.app.state.method_assets
        can_edit = can_publish = False
        try:
            permitted(caller);can_edit = True
            permitted(caller, True);can_publish = True
        except DecisionLayerError:
            pass
        skill = asset.manifest.implementation == "skill"
        snapshot = None if skill else getattr(asset, "source_snapshot", None)
        return {"name":name, "version":asset.manifest.version,"implementation":asset.manifest.implementation,
                "content":asset.source_text if skill else snapshot.editor_content if snapshot else None,
                "code":snapshot,"permissions":{"edit":can_edit,"publish":can_publish},
                "draft":store.draft(name) if can_edit else None,
                "history":[{key:value for key,value in entry.items() if key in ("version","published_by","published_at")}
                           for entry in store.history(name)]}

    @router.put("/methods/{name}/draft")
    async def save_draft(name: str, req: DraftRequest, caller: Caller, request: Request):
        permitted(caller)
        return request.app.state.method_assets.save(name, req, caller.subject)

    @router.post("/methods/{name}/source:format")
    async def format_source(name: str, req: FormatRequest, caller: Caller):
        from starlette.concurrency import run_in_threadpool
        from ..methods.assets import AssetError
        from ..methods.formatting import format_python

        permitted(caller)
        if registry.get(name).manifest.implementation != "python":
            raise AssetError("Formatting is available for Python Methods only")
        content = await run_in_threadpool(format_python, req.content)
        return {"content": content, "changed": content != req.content}

    @router.post("/methods/{name}/draft:check")
    async def check_draft(name: str, req: RevisionRequest, caller: Caller, request: Request):
        python = registry.get(name).manifest.implementation == "python"
        permitted(caller, python)
        if python and not req.reviewed:
            from ..methods.assets import AssetError
            raise AssetError("Review and trust this Python module before executing registration checks")
        return await request.app.state.method_assets.check(name, req.revision)

    @router.post("/methods/{name}/draft:publish")
    async def publish_draft(name: str, req: RevisionRequest, caller: Caller, request: Request):
        permitted(caller, True)
        entry = request.app.state.method_assets.publish(name, req, caller.subject)
        return {"name":name,"version":entry["version"],"published_at":entry["published_at"]}

    @router.get("/methods/{name}/guide")
    async def method_guide(name: str):
        from ..methods.skills import SkillMethod
        from ..methods.registry import InvalidBinding
        asset = registry.get(name)
        if not isinstance(asset, SkillMethod):
            raise InvalidBinding("This is an executable Python Method, not a Skill")
        return asset.guide

    @router.get("/methods/{name}", response_model=MethodManifest)
    async def method(name: str, version: str | None = None) -> MethodManifest:
        return localized(registry.get(name, version).manifest)

    @router.post("/methods/{name}:run", response_model=Result, responses={202: {"description": "still running"}})
    async def method_run(name: str, req: MethodRunRequest, creds: Creds, caller: Caller, request: Request,
                         wait: float | None = None):
        """Ad-hoc Method run, stored as a single-step Run owned by the caller. Answers the Result when it
        finishes within `wait` seconds, else 202 {run_id, poll} — then poll GET /runs/{run_id}/result."""
        bindings = invocation_inputs(registry.get(name, req.method_version).manifest, bindings=req.bindings,
                                     measures=req.measures, dimensions=req.dimensions, entity=req.entity)
        scope = req.scope.as_dict()
        scope["filters"] = [*(scope.get("filters") or []), *[item.model_dump(mode="json") for item in req.filters]]
        run, result = await engine.adhoc(creds, caller, PlanStep(method=name, method_version=req.method_version, bindings=bindings, params=req.params),
                                         scope, wait=waited(settings, wait), origin=run_origin(request), question=req.question, author=req.author)
        return result if result is not None else accepted(run)

    return router
