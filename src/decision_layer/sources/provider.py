"""Provider facade that applies the current source settings per request."""
from __future__ import annotations
from contextvars import ContextVar

from ..semantic.providers.cube.client import CubeClient
from ..semantic.provider import SemanticProvider
from ..semantic.providers.cube.provider import CubeProvider
from ..semantic.providers.dbt.provider import DbtSemanticLayerProvider
from .config import SourceConfigManager


def make_provider(name: str, url: str, instance: str, environment_id: int | None = None):
    if name == "cube":
        return CubeProvider(CubeClient(url), instance)
    if name == "dbt":
        return DbtSemanticLayerProvider(url, instance, environment_id)
    raise ValueError(f"Unsupported semantic provider: {name}")


class ConfiguredSemanticProvider:

    def __init__(self, manager: SourceConfigManager) -> None:
        self.manager = manager
        self._providers = {}
        self._bound = ContextVar("semantic_provider", default=None)

    def bind(self, source):
        key = (source.provider, source.api_url, source.instance, source.environment_id)
        if key not in self._providers:
            self._providers[key] = make_provider(*key)
        self._bound.set(self._providers[key])

    @property
    def name(self):
        return self._bound.get().name if self._bound.get() else self.manager.current_provider

    @property
    def instance(self) -> str:
        return self._bound.get().instance if self._bound.get() else self.manager.current_instance

    def capabilities(self):
        return make_provider(self.name, "http://localhost", self.instance).capabilities()

    @property
    def identity_mode(self):
        return make_provider(self.name, "http://localhost", self.instance).identity_mode

    async def _provider(self) -> SemanticProvider:
        if self._bound.get() is not None:
            return self._bound.get()
        source = await self.manager.effective(resolve_secret=False)
        key = (source.provider, source.api_url, source.instance, source.environment_id)
        if key not in self._providers:
            self._providers[key] = make_provider(*key)
        return self._providers[key]

    async def discover(self, credentials):
        return await (await self._provider()).discover(credentials)

    async def refresh_catalog(self, credentials):
        provider = await self._provider()
        return await getattr(provider, "refresh_catalog", provider.discover)(credentials)

    async def resolve(self, refs, credentials):
        return await (await self._provider()).resolve(refs, credentials)

    async def validate_dataset(self, spec, credentials):
        return await (await self._provider()).validate_dataset(spec, credentials)

    async def execute(self, spec, credentials, *, with_sql=False):
        return await (await self._provider()).execute(spec, credentials, with_sql=with_sql)


ConfiguredCubeProvider = ConfiguredSemanticProvider
