"""Cube implementation of the SemanticProvider contract."""
from __future__ import annotations

import hashlib
import time
from typing import Any

from ....core.errors import (
    CapabilityMissing, DatasetTooLarge, InvalidDatasetSpec, ProviderError, UnknownSemanticObject,
)
from ....core.models import Dataset, DatasetSpec, ProviderCapabilities, QueryProvenance, SemanticCatalog, SemanticObject
from ...provider import Credentials
from .catalog_mapper import ViewIndex, map_meta
from .client import CubeClient
from .compiler import compile_spec, convert, spec_members
from ....i18n import _

PAGE_SIZE = 50_000               # Cube's default max rows per /load
MAX_ENTITY_ROWS = 500_000        # entity-grain safety cap (MVP; fail closed beyond it)
CATALOG_TTL_SECONDS = 60


class CubeProvider:
    name = "cube"
    identity_mode = "jwt_claims"

    def __init__(self, client: CubeClient, instance: str) -> None:
        self.client = client
        self.instance = instance
        # catalog per caller: /meta is already filtered by the caller's access rules
        self._cache: dict[str, tuple[float, SemanticCatalog, ViewIndex]] = {}

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(aggregate_queries=True, entity_grain_queries=True, time_dimensions=True,
                                    compiled_sql=True, hierarchies=True, max_rows_per_query=PAGE_SIZE)

    async def _catalog(self, credentials: Credentials) -> tuple[SemanticCatalog, ViewIndex]:
        token = credentials.bearer()
        key = hashlib.sha256((token or "").encode()).hexdigest()
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < CATALOG_TTL_SECONDS:
            return hit[1], hit[2]
        catalog, views = map_meta(await self.client.meta(token), self.instance)
        self._cache[key] = (time.monotonic(), catalog, views)
        return catalog, views

    async def discover(self, credentials: Credentials) -> SemanticCatalog:
        return (await self._catalog(credentials))[0]

    async def resolve(self, refs: list[str], credentials: Credentials) -> list[SemanticObject]:
        catalog, _views = await self._catalog(credentials)
        out = []
        for r in refs:
            obj = catalog.get(r)
            if obj is None:
                raise UnknownSemanticObject(_("'{ref}' was not found or you don't have access to it", ref=r), ref=r)
            out.append(obj)
        return out

    async def validate_dataset(self, spec: DatasetSpec, credentials: Credentials) -> None:
        catalog, _views = await self._catalog(credentials)
        await self.resolve(spec_members(spec), credentials)
        for r in spec.measures:
            if catalog.get(r).kind != "measure":
                raise InvalidDatasetSpec(_("'{ref}' is not a measure", ref=r), ref=r)
        for r in spec.dimensions:
            if catalog.get(r).kind == "measure":
                raise InvalidDatasetSpec(_("'{ref}' is not a dimension", ref=r), ref=r)
        if spec.time and catalog.get(spec.time.dimension).kind != "time_dimension":
            raise InvalidDatasetSpec(_("'{ref}' is not a time dimension", ref=spec.time.dimension))
        if spec.grain == "entity":
            entity = catalog.get(spec.entity)
            if entity.kind == "measure":
                raise InvalidDatasetSpec(_("entity '{ref}' must be a dimension", ref=spec.entity))
            # Measures of other cubes are fine at this grain: Cube aggregates every cube's measures by its own
            # primary key before joining ("multiplied measures"), so a per-entity value never fans out. What
            # can fail is a missing join path — execute() turns Cube's error into CapabilityMissing.

    async def execute(self, spec: DatasetSpec, credentials: Credentials, *, with_sql: bool = False) -> Dataset:
        await self.validate_dataset(spec, credentials)
        catalog, views = await self._catalog(credentials)
        compiled = compile_spec(spec, catalog, views)
        token = credentials.bearer()

        limit = spec.limit_rows or (MAX_ENTITY_ROWS if spec.grain == "entity" else PAGE_SIZE)
        rows: list[list[Any]] = []
        started = time.monotonic()
        pages = 0
        offset = 0
        while True:
            page_size = min(PAGE_SIZE, limit - len(rows))
            try:
                body = await self.client.load({**compiled.query, "limit": page_size, "offset": offset}, token)
            except ProviderError as e:
                if "join path" in e.message.lower():
                    raise CapabilityMissing(_("The semantic layer has no join path between the requested members"),
                                            members=spec_members(spec)) from e
                raise
            data = body.get("data", [])
            pages += 1
            rows.extend([convert(row.get(k), c.data_type) for k, c in zip(compiled.keys, compiled.columns)] for row in data)
            if len(data) < page_size:
                break
            if len(rows) >= limit:
                if spec.limit_rows is None:
                    raise DatasetTooLarge(_("The result exceeds {limit:,} rows. Narrow the period or filters", limit=limit), limit=limit)
                break
            offset += page_size

        sql = None
        if with_sql:
            sql_body = await self.client.sql(compiled.query, token)
            sql_list = (sql_body.get("sql") or {}).get("sql") or []
            sql = sql_list[0] if sql_list else None
        provenance = QueryProvenance(provider=self.name, instance=self.instance,
                                     native_query={**compiled.query, **({"_view": compiled.view} if compiled.view else {})},
                                     compiled_sql=sql, rows=len(rows), pages=pages,
                                     elapsed_ms=round((time.monotonic() - started) * 1000))
        return Dataset(spec=spec, columns=compiled.columns, rows=rows, provenance=[provenance])
