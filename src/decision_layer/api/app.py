"""REST API (ARCHITECTURE §17). Routes are resource-oriented, not tied to a UI."""
from __future__ import annotations

from contextlib import asynccontextmanager
import hmac
from typing import Annotated, Literal

import yaml

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse

from .. import __version__
from ..auth import credentials, identify
from ..i18n import _, negotiate, set_locale
from ..core.errors import DecisionLayerError, ProviderAccessDenied, ProviderError, UnknownSemanticObject
from ..core.models import (
    CallerInfo, Dataset, DatasetSpec, MethodManifest, PlanStep, ProviderCapabilities, Recipe, Result, Run, SemanticCatalog,
    SemanticObject,
)
from ..methods import registry
from ..semantic.credentials import AnonymousServiceCredentials, RequestCredentials, ServiceCredentials
from ..semantic.providers.cube.client import CubeClient, CubeConnectionError
from ..semantic.providers.cube.provider import CubeProvider
from ..sources.config import EffectiveSource, SourceConfigError, SourceConfigInput, SourceConfigManager
from ..sources.provider import ConfiguredCubeProvider
from ..sources.store import open_source_store
from ..recipes.loader import RecipeStore, parse_recipe
from ..recipes.from_run import RecipeCandidate, candidate_from_run
from ..runs.engine import RunEngine
from ..runs.jobs import JobRunner
from ..runs.store import RunStore, open_store
from ..service import MethodRunRequest, RecipePreviewRequest, RecipePublishRequest, RecipeSaveRequest, RecipeYamlRequest, RunCompleteRequest, RunShareRequest, RunStartRequest, RunStepRequest
from ..settings import Settings
from ..i18n import _

PREVIEW_ROWS = 1000
MAX_WAIT_SECONDS = 300


def run_origin(request: Request) -> Literal["api", "web", "mcp"]:
    hint = request.headers.get("X-Decision-Layer-Client")
    return hint if hint in ("web", "mcp") else "api"


class JobFailed(DecisionLayerError):
    """The run's last background job raised; code/message are the recorded ones."""
    http_status = 422

    def __init__(self, error: dict) -> None:
        super().__init__(error.get("message", ""))
        self.code = error.get("code", "JOB_FAILED")


class NoResult(DecisionLayerError):
    code = "NO_RESULT"
    http_status = 404


class SourceAdminRequired(DecisionLayerError):
    code = "SOURCE_ADMIN_REQUIRED"
    http_status = 403


async def get_credentials(request: Request, authorization: Annotated[str | None, Header()] = None):
    """The caller's bearer token is passed through to the provider (ADR-024); service credentials
    are a local/dev fallback that must be switched on explicitly (ADR-029)."""
    settings: Settings = request.app.state.settings
    source: EffectiveSource = await request.app.state.source_manager.effective(resolve_secret=False)
    if source.auth_method == "api_secret" and not authorization:
        source = await request.app.state.source_manager.effective()
    return credentials(authorization, allow_service=settings.allow_service_credentials,
                       secret=source.api_secret, groups=source.service_groups, auth_method=source.auth_method)


Creds = Annotated[RequestCredentials | ServiceCredentials | AnonymousServiceCredentials, Depends(get_credentials)]


async def get_caller(request: Request, creds: Creds) -> CallerInfo:
    return await identify(request.app.state.provider, creds)


Caller = Annotated[CallerInfo, Depends(get_caller)]


def localized(m: MethodManifest) -> MethodManifest:
    """Manifest texts are English in code; serve them in the request's language."""
    return m.model_copy(update={
        "description": _(m.description),
        "roles": {k: r.model_copy(update={"description": _(r.description)}) for k, r in m.roles.items()},
        "parameters": {k: p.model_copy(update={"description": _(p.description)}) for k, p in m.parameters.items()},
    })


def create_app(settings: Settings | None = None, provider: CubeProvider | None = None,
               store: RunStore | None = None, recipes: RecipeStore | None = None) -> FastAPI:
    settings = settings or Settings()
    source_manager = SourceConfigManager(open_source_store(settings.database_url), settings)
    provider = provider or ConfiguredCubeProvider(source_manager)
    recipes = recipes or RecipeStore(settings.recipes_dir, provider.name, provider.instance)
    engine = RunEngine(provider, recipes, store or open_store(settings.database_url),
                       jobs=JobRunner(settings.job_workers))

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await engine.recover()
        yield
        engine.jobs.shutdown()

    def waited(wait: float | None) -> float:
        return max(0.0, min(settings.request_wait_seconds if wait is None else wait, MAX_WAIT_SECONDS))

    def accepted(run: Run) -> JSONResponse:
        return JSONResponse(status_code=202, content={
            "run_id": run.id, "status": "running", "running": run.running.model_dump(mode="json") if run.running else None,
            "poll": f"/runs/{run.id}/result"})

    app = FastAPI(title="Decision Layer", version=__version__, lifespan=lifespan)

    @app.middleware("http")
    async def locale(request: Request, call_next):
        set_locale(negotiate(request.headers.get("accept-language"), settings.locale))
        response = await call_next(request)
        response.headers["Content-Language"] = negotiate(request.headers.get("accept-language"), settings.locale)
        return response
    app.state.settings = settings
    app.state.provider = provider
    app.state.source_manager = source_manager

    @app.exception_handler(DecisionLayerError)
    async def _app_error(_request: Request, exc: DecisionLayerError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content={"error": exc.to_dict()})

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": __version__, "provider": provider.name, "instance": provider.instance}

    @app.get("/me", response_model=CallerInfo)
    async def me(caller: Caller) -> CallerInfo:
        """The identity runs are stored under for this caller."""
        return caller

    @app.get("/sources/current/capabilities", response_model=ProviderCapabilities)
    async def capabilities() -> ProviderCapabilities:
        return provider.capabilities()


    def require_source_admin(request: Request, admin_key: Annotated[str | None, Header(alias="X-Decision-Layer-Admin-Key")] = None) -> None:
        """Editing the shared connection is gated only where DL_SOURCE_ADMIN_TOKEN is set (a shared
        deployment). Without it this is a single-user/local install and editing is open (ADR-033)."""
        expected = request.app.state.settings.source_admin_token
        if not expected:
            return
        if not admin_key or not hmac.compare_digest(admin_key, expected):
            raise SourceAdminRequired(_("Enter the source administrator key configured by the server."))

    @app.get("/sources/current")
    async def source_current() -> dict:
        return await source_manager.view()

    @app.put("/sources/current")
    async def source_save(value: SourceConfigInput, _admin: None = Depends(require_source_admin)) -> dict:
        await source_manager.save(value)
        return await source_manager.view()

    @app.post("/sources/current:test")
    async def source_test(value: SourceConfigInput, _admin: None = Depends(require_source_admin),
                          authorization: Annotated[str | None, Header()] = None) -> dict:
        try:
            config = value
            effective = await source_manager.effective(resolve_secret=False)
            api_url = effective.api_url if effective.environment_overrides["api_url"] else config.api_url
            auth_method = effective.auth_method if effective.environment_overrides["auth_method"] else config.auth_method
            groups = (effective.service_groups if effective.environment_overrides["service_groups"]
                      else tuple(config.service_groups or effective.service_groups))
            if auth_method != "token" and not settings.allow_service_credentials:
                raise SourceConfigError("SOURCE_DEV_AUTH_DISABLED", "Development authentication is disabled on this deployment.", 403)
            secret = None
            if auth_method == "api_secret":
                supplied = config.api_secret.get_secret_value() if config.api_secret else None
                current = await source_manager.effective()
                secret = current.api_secret if effective.environment_overrides["api_secret"] else supplied or current.api_secret
                if not secret:
                    raise SourceConfigError("SOURCE_SECRET_REQUIRED", "Enter the Cube API secret to test this connection.", 400)
            creds = credentials(authorization, allow_service=settings.allow_service_credentials,
                                secret=secret, groups=groups, auth_method=auth_method)
            test_provider = (provider if not isinstance(provider, ConfiguredCubeProvider)
                             else CubeProvider(CubeClient(api_url), effective.instance))
            catalog = await test_provider.discover(creds)
        except ProviderAccessDenied as exc:
            raise SourceConfigError("SOURCE_AUTH_FAILED", "Cube rejected these credentials. Check the token, secret, required claims and Cube auth configuration.", 401) from exc
        except CubeConnectionError as exc:
            raise SourceConfigError("SOURCE_UNREACHABLE", "Cube could not be reached at this address. Check the URL, port, network and TLS certificate.", 502) from exc
        except ProviderError as exc:
            raise SourceConfigError("SOURCE_PROVIDER_ERROR", "Cube returned an error. Check the API URL and Cube server logs for model compilation or upstream failures.", 502) from exc
        public = [obj for obj in catalog.objects if obj.public]
        if not public:
            raise SourceConfigError("SOURCE_NO_CUBES", "Cube responded, but this identity can see no semantic objects. Deploy a Cube model and grant access.", 422)
        return {"status": "connected", "provider": "cube", "instance": catalog.instance,
                "objects": len(public), "measures": sum(o.kind == "measure" for o in public),
                "dimensions": sum(o.kind == "dimension" for o in public),
                "time_dimensions": sum(o.kind == "time_dimension" for o in public)}

    @app.get("/sources/current/readiness")
    async def source_readiness(creds: Creds) -> dict:
        catalog = await provider.discover(creds)
        public = [obj for obj in catalog.objects if obj.public]
        items = []
        for metric in (obj for obj in public if obj.kind == "measure"):
            entity_ref = metric.entity
            related = [obj for obj in public if entity_ref and obj.entity == entity_ref]
            times = [obj for obj in related if obj.kind == "time_dimension"]
            any_times = any(obj.kind == "time_dimension" for obj in public)
            has_key = bool(entity_ref and any(obj.ref == entity_ref for obj in public))
            ratio_parts = metric.ratio_parts
            ratio_ok = bool(ratio_parts and all(any(obj.ref == ref and obj.kind == "measure" for obj in public)
                                                for ref in ratio_parts))
            checks = {
                "decomposition": {"status": "ready" if ratio_ok else ("missing" if metric.metric_kind == "ratio" else "not_applicable"),
                                  "parts": list(ratio_parts) if ratio_parts else [],
                                  "impact": None if ratio_ok or metric.metric_kind != "ratio" else "This ratio cannot be decomposed into its declared numerator and denominator."},
                "time": {"status": "ready" if times else ("unknown" if any_times else "missing"),
                         "dimensions": [o.ref for o in times],
                         "impact": None if times else ("A related time dimension could not be confirmed from metadata. Select and verify one when running."
                                                       if any_times else "Time-series analysis is unavailable: no time dimension is visible.")},
                "entity_key": {"status": "ready" if has_key else "missing", "ref": entity_ref,
                               "impact": None if has_key else "Matched/entity-level comparisons may be unavailable."},
            }
            items.append({"metric": metric.model_dump(mode="json"), "checks": checks})
        return {"provider": catalog.provider, "instance": catalog.instance, "metrics": items,
                "note": "Readiness reflects declarations visible in the semantic catalog; preview queries are still required to confirm joinability and access."}

    @app.get("/semantic/catalog", response_model=SemanticCatalog)
    async def catalog(creds: Creds, include_private: bool = False) -> SemanticCatalog:
        cat = await provider.discover(creds)
        if include_private:
            return cat
        return cat.model_copy(update={"objects": [o for o in cat.objects if o.public]})

    @app.get("/semantic/objects", response_model=list[SemanticObject])
    async def objects(creds: Creds, ref: Annotated[list[str], Query()]) -> list[SemanticObject]:
        return await provider.resolve(ref, creds)

    @app.post("/datasets/preview", response_model=Dataset)
    async def preview(spec: DatasetSpec, creds: Creds, with_sql: bool = False) -> Dataset:
        """Run a DatasetSpec and return up to PREVIEW_ROWS rows (provenance keeps the full count)."""
        dataset = await provider.execute(spec, creds, with_sql=with_sql)
        return dataset.model_copy(update={"rows": dataset.rows[:PREVIEW_ROWS]})

    @app.get("/methods", response_model=list[MethodManifest])
    async def methods() -> list[MethodManifest]:
        return [localized(m) for m in registry.manifests()]

    @app.get("/methods/{name}", response_model=MethodManifest)
    async def method(name: str) -> MethodManifest:
        return localized(registry.get(name).manifest)

    @app.post("/methods/{name}:run", response_model=Result, responses={202: {"description": "still running"}})
    async def method_run(name: str, req: MethodRunRequest, creds: Creds, caller: Caller, request: Request,
                         wait: float | None = None):
        """Ad-hoc Method run, stored as a single-step Run owned by the caller. Answers the Result when it
        finishes within `wait` seconds, else 202 {run_id, poll} — then poll GET /runs/{run_id}/result."""
        run, result = await engine.adhoc(creds, caller, PlanStep(method=name, bindings=req.bindings, params=req.params),
                                         req.scope.as_dict(), wait=waited(wait), origin=run_origin(request), question=req.question)
        return result if result is not None else accepted(run)

    @app.get("/recipes", response_model=list[Recipe])
    async def recipes_list(_caller: Caller) -> list[Recipe]:
        return recipes.list()

    @app.get("/recipes:drafts", response_model=list[Recipe])
    async def recipe_drafts(_caller: Caller) -> list[Recipe]:
        return recipes.list_drafts()

    @app.post("/recipes:format")
    async def recipe_format(recipe: Recipe, _caller: Caller) -> dict[str, str]:
        recipes.validate(recipe)
        return {"yaml": yaml.safe_dump(recipe.model_dump(mode="json"), allow_unicode=True, sort_keys=False)}

    @app.post("/recipes:parse", response_model=Recipe)
    async def recipe_parse(req: RecipeYamlRequest, _caller: Caller) -> Recipe:
        from ..recipes.authoring import RecipeEditError

        try:
            document = yaml.safe_load(req.yaml)
            if not isinstance(document, dict):
                raise RecipeEditError(_("Recipe YAML must be a mapping."))
            parsed = parse_recipe(document, provider.name, provider.instance)
        except yaml.YAMLError as error:
            raise RecipeEditError(_("Recipe YAML syntax is invalid: {error}", error=error)) from error
        except ValueError as error:
            raise RecipeEditError(_("Recipe YAML structure is invalid: {error}", error=error)) from error
        recipes.validate(parsed)
        return parsed

    async def check_recipe_semantics(recipe: Recipe, creds: Creds) -> None:
        paths: dict[str, str] = {}

        def collect(value, path: str) -> None:
            if isinstance(value, str) and value.startswith("cube://"):
                paths.setdefault(value, path)
            elif isinstance(value, dict):
                for key, child in value.items():
                    collect(child, f"{path}.{key}" if path else key)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    collect(child, f"{path}[{index}]")

        collect(recipe.model_dump(mode="json"), "")
        try:
            await provider.resolve(sorted(paths), creds)
        except UnknownSemanticObject as error:
            if field := paths.get(error.details.get("ref")):
                error.details["field"] = field
            raise

    @app.post("/recipes:validate")
    async def recipe_validate(recipe: Recipe, _caller: Caller, creds: Creds, live: bool = False) -> dict[str, bool]:
        """Validate the shared static contract and, optionally, caller-visible semantic references."""
        recipes.validate(recipe)
        if live:
            await check_recipe_semantics(recipe, creds)
        return {"valid": True, "semantic_checked": live}

    @app.post("/recipes:preview", response_model=Run, responses={202: {"description": "preview still running"}})
    async def recipe_preview(req: RecipePreviewRequest, creds: Creds, caller: Caller, request: Request, wait: float | None = None):
        """Execute an unsaved pipeline prefix with normal validation, access and query limits."""
        recipes.validate(req.recipe)
        run = await engine.preview(creds, caller, req.recipe, req.step_index, req.scope.as_dict(), wait=waited(wait), origin=run_origin(request))
        return JSONResponse(status_code=202, content=run.model_dump(mode="json")) if run.running else run

    @app.get("/recipes/{name}/edit", response_model=Recipe)
    async def recipe_edit(name: str, _caller: Caller) -> Recipe:
        return recipes.get(name, include_drafts=True)

    @app.post("/recipes/{name}/publish", response_model=Recipe)
    async def recipe_publish(name: str, req: RecipePublishRequest, _caller: Caller, creds: Creds) -> Recipe:
        draft = recipes.get(name, req.base_version, include_drafts=True)
        recipes.validate(draft)
        await check_recipe_semantics(draft, creds)
        return recipes.publish(name, req.base_version)

    @app.get("/recipes/{name}", response_model=Recipe)
    async def recipe_get(name: str, _caller: Caller) -> Recipe:
        return recipes.get(name)

    @app.put("/recipes/{name}", response_model=Recipe)
    async def recipe_save(name: str, req: RecipeSaveRequest, _caller: Caller) -> Recipe:
        from ..recipes.authoring import RecipeEditError

        if req.recipe.name != name:
            raise RecipeEditError("Recipe name must match the URL.")
        return recipes.save(req.recipe, req.base_version)

    @app.post("/runs", response_model=Run, responses={202: {"description": "pipeline still running"}})
    async def run_start(req: RunStartRequest, creds: Creds, caller: Caller, request: Request, wait: float | None = None):
        """Start a Run. A pipeline Recipe executes right away (202 with the run while it is still running);
        an investigation Recipe waits for steps."""
        run = await engine.start(creds, caller, recipe=req.recipe, question=req.question, scope=req.scope.as_dict(),
                                 wait=waited(wait), origin=run_origin(request))
        return JSONResponse(status_code=202, content=run.model_dump(mode="json")) if run.running else run

    @app.get("/runs", response_model=list[Run])
    async def runs_list(caller: Caller, limit: int = 50, recipe: str | None = None) -> list[Run]:
        """The caller's own runs, newest first."""
        return await engine.list(caller, limit, recipe)

    @app.get("/runs/{run_id}/recipe-candidate", response_model=RecipeCandidate)
    async def run_recipe_candidate(run_id: str, creds: Creds, caller: Caller, indices: list[int] = Query(...)) -> RecipeCandidate:
        run = await engine.get(creds, caller, run_id)
        candidate = candidate_from_run(run, indices)
        await check_recipe_semantics(candidate.recipe, creds)
        return candidate

    @app.get("/runs/{run_id}", response_model=Run)
    async def run_get(run_id: str, creds: Creds, caller: Caller) -> Run:
        return await engine.get(creds, caller, run_id)

    @app.get("/runs/{run_id}/result", response_model=Result, responses={202: {"description": "still running"}})
    async def run_result(run_id: str, creds: Creds, caller: Caller):
        """The latest step's Result — 202 while a job runs, the recorded error if the job failed."""
        run = await engine.get(creds, caller, run_id)
        if run.running:
            return accepted(run)
        if run.error:
            raise JobFailed(run.error)
        if not run.steps:
            raise NoResult(_("No step has run yet"), run_id=run_id)
        return run.steps[-1].result

    @app.post("/runs/{run_id}/steps", response_model=Result, responses={202: {"description": "still running"}})
    async def run_step(run_id: str, req: RunStepRequest, creds: Creds, caller: Caller, wait: float | None = None):
        run, result = await engine.step(creds, caller, run_id, PlanStep(**req.model_dump()), wait=waited(wait))
        return result if result is not None else accepted(run)

    @app.post("/runs/{run_id}:complete", response_model=Run)
    async def run_complete(run_id: str, req: RunCompleteRequest, caller: Caller) -> Run:
        return await engine.complete(caller, run_id, req.summary)

    @app.post("/runs/{run_id}:share", response_model=Run)
    async def run_share(run_id: str, req: RunShareRequest, caller: Caller) -> Run:
        """Owner only. Replaces the read-only share list; "*" = any authenticated caller."""
        return await engine.share(caller, run_id, req.subjects)

    return app


app = create_app()
