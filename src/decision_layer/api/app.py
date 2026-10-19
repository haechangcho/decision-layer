"""FastAPI assembly and lifecycle. Routes live beside this file by resource."""

from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .. import __version__
from ..core.models import CallerInfo
from ..semantic.provider import SemanticProvider
from ..sources.config import SourceConfigManager
from ..sources.provider import ConfiguredSemanticProvider
from ..sources.store import open_source_store
from ..recipes.loader import RecipeStore
from ..runs.engine import RunEngine
from ..runs.jobs import JobRunner
from ..runs.store import RunStore, open_store
from ..settings import Settings
from .dependencies import Caller
from .http import install_http_handlers


def create_app(
    settings: Settings | None = None,
    provider: SemanticProvider | None = None,
    store: RunStore | None = None,
    recipes: RecipeStore | None = None,
) -> FastAPI:
    settings = settings or Settings()
    settings.validate_deployment()
    source_manager = SourceConfigManager(
        open_source_store(settings.database_url), settings
    )
    provider = provider or ConfiguredSemanticProvider(source_manager)
    from ..methods.loading import configured_registry

    registry = configured_registry(settings)
    from ..methods.assets import MethodAssets

    assets = MethodAssets(settings.method_assets_dir, registry)
    recipes = recipes or RecipeStore(
        settings.recipes_dir, provider.name, provider.instance, registry=registry
    )
    recipes.registry = registry
    engine = RunEngine(
        provider,
        recipes,
        store or open_store(settings.database_url),
        jobs=JobRunner(settings.job_workers),
        policy=settings.execution_policy,
        registry=registry,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await source_manager.effective(resolve_secret=False)
        await engine.recover()
        yield
        engine.jobs.shutdown()

    app = FastAPI(title="Decision Layer", version=__version__, lifespan=lifespan)

    install_http_handlers(app, settings)
    app.state.method_assets = assets
    app.state.settings = settings
    app.state.provider = provider
    app.state.source_manager = source_manager

    @app.get("/health")
    async def health() -> dict:
        await source_manager.effective(resolve_secret=False)
        return {
            "status": "ok",
            "version": __version__,
            "provider": provider.name,
            "instance": provider.instance,
        }

    @app.get("/me", response_model=CallerInfo)
    async def me(caller: Caller) -> CallerInfo:
        """The identity runs are stored under for this caller."""
        return caller

    from .sources import create_router as sources_router

    app.include_router(sources_router(settings, provider, source_manager))
    from .semantic import create_router as semantic_router

    app.include_router(semantic_router(provider, engine))
    from .methods import create_router as methods_router

    app.include_router(methods_router(settings, engine))
    from .recipes import create_router as recipes_router

    app.include_router(recipes_router(settings, provider, recipes, engine))
    from .runs import create_router as runs_router

    app.include_router(runs_router(settings, provider, recipes, engine))
    return app


app = create_app()
