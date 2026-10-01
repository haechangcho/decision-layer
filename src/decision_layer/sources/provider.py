"""Cube provider facade that applies the current source settings per request."""
from __future__ import annotations

from ..semantic.providers.cube.client import CubeClient
from ..semantic.providers.cube.provider import CubeProvider
from .config import SourceConfigManager


class ConfiguredCubeProvider:
    name = "cube"

    def __init__(self, manager: SourceConfigManager) -> None:
        self.manager = manager
        self._providers: dict[tuple[str, str], CubeProvider] = {}

    @property
    def instance(self) -> str:
        return self.manager.settings.cube_instance

    def capabilities(self):
        return CubeProvider(CubeClient("http://localhost"), self.instance).capabilities()

    async def _provider(self) -> CubeProvider:
        source = await self.manager.effective(resolve_secret=False)
        key = (source.api_url, source.instance)
        if key not in self._providers:
            self._providers[key] = CubeProvider(CubeClient(source.api_url), source.instance)
        return self._providers[key]

    async def discover(self, credentials):
        return await (await self._provider()).discover(credentials)

    async def resolve(self, refs, credentials):
        return await (await self._provider()).resolve(refs, credentials)

    async def validate_dataset(self, spec, credentials):
        return await (await self._provider()).validate_dataset(spec, credentials)

    async def execute(self, spec, credentials, *, with_sql=False):
        return await (await self._provider()).execute(spec, credentials, with_sql=with_sql)
