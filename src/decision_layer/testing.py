"""Strict scripted semantic responses for Method tests; no warehouse emulator.

Fixtures assert whole DatasetSpecs before returning independently supplied values.
They do not prove provider joins, aggregation, authentication or causal validity.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .core.models import Column, Dataset, DatasetSpec, ProviderCapabilities, QueryProvenance, SemanticCatalog
from .semantic.provider import Credentials


@dataclass(frozen=True)
class QueryFixture:
    spec: DatasetSpec
    rows: list[list[Any]]
    error: Exception | None = None


class FixtureProvider:
    identity_mode = "credential"

    def __init__(self, catalog: SemanticCatalog, queries: Sequence[QueryFixture]) -> None:
        from copy import deepcopy
        self.catalog = catalog.model_copy(deep=True)
        self.name, self.instance = catalog.provider, catalog.instance
        self._queries = deepcopy(list(queries))
        self.calls: list[DatasetSpec] = []

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(aggregate_queries=True, entity_grain_queries=True,
                                    time_dimensions=True, compiled_sql=False, hierarchies=False,
                                    max_rows_per_query=50_000)

    async def discover(self, credentials: Credentials) -> SemanticCatalog:
        return self.catalog.model_copy(deep=True)

    async def resolve(self, refs: list[str], credentials: Credentials):
        from .core.errors import UnknownSemanticObject
        objects = []
        for ref in refs:
            obj = self.catalog.get(ref)
            if obj is None or not obj.public:
                raise UnknownSemanticObject("Fixture reference is unavailable.", ref=ref)
            objects.append(obj.model_copy(deep=True))
        return objects

    async def validate_dataset(self, spec: DatasetSpec, credentials: Credentials) -> None:
        refs = [*spec.measures, *spec.dimensions, *(item.member for item in spec.filters),
                *(ref for ref, _ in spec.order)]
        refs += [spec.time.dimension] if spec.time else []
        refs += [spec.entity] if spec.entity else []
        await self.resolve(refs, credentials)

    async def execute(self, spec: DatasetSpec, credentials: Credentials, *, with_sql: bool = False) -> Dataset:
        index = len(self.calls)
        self.calls.append(spec.model_copy(deep=True))
        if index >= len(self._queries):
            raise AssertionError(f"Unexpected query #{index + 1}: {spec.model_dump()}")
        fixture = self._queries[index]
        if spec != fixture.spec:
            raise AssertionError(f"Query #{index + 1} differs.\nExpected: {fixture.spec.model_dump()}\nActual: {spec.model_dump()}")
        if fixture.error:
            raise fixture.error
        refs = [*spec.measures, *spec.dimensions]
        if spec.entity and spec.entity not in refs:
            refs.append(spec.entity)
        if spec.time and spec.time.granularity and spec.time.dimension not in refs:
            refs.append(spec.time.dimension)
        objects = await self.resolve(refs, credentials)
        if any(len(row) != len(refs) for row in fixture.rows):
            raise AssertionError("Fixture row width does not match selected columns.")
        columns = [Column(ref=obj.ref, role="time" if obj.kind == "time_dimension" else obj.kind,
                          data_type=obj.data_type) for obj in objects]
        return Dataset(spec=spec.model_copy(deep=True), columns=columns,
                       rows=[list(row) for row in fixture.rows],
                       provenance=[QueryProvenance(provider=self.name, instance=self.instance,
                                                   native_query=spec.model_dump(mode="json"),
                                                   rows=len(fixture.rows), elapsed_ms=0)])

    def assert_consumed(self) -> None:
        if len(self.calls) != len(self._queries):
            raise AssertionError(f"Used {len(self.calls)} of {len(self._queries)} expected queries.")
