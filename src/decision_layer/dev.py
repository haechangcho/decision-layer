"""Local Method development on the ordinary registry, context and Run engine.

No remote installation, code upload or credential persistence. Direct execution
stays in the caller's event loop for Python breakpoints; preview uses RunEngine.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .core.models import QueryAttempt, QueryProvenance, Recipe, Result, Run, SemanticCatalog, SemanticObject
from .core.periods import ExecutionPolicy, PeriodChoice
from .methods import InvalidBinding, Method, MethodRegistry
from .methods.context import ExecutionContext, Refused, Scope
from .semantic.provider import Credentials, SemanticProvider


@dataclass
class MethodTrial:
    """Evidence for one local invocation, including attempts before an exception.

An exception is re-raised, not converted into a successful analytical result.
This is not a stored Run and cannot be opened on a remote Web server.
"""
    method: str
    bindings: dict[str, Any]
    params: dict[str, Any]
    context: ExecutionContext = field(repr=False)
    result: Result | None = None

    @property
    def queries(self) -> list[QueryProvenance]:
        return self.context.queries

    @property
    def attempts(self) -> list[QueryAttempt]:
        return self.context.attempts


class MethodSession:
    """An isolated registry and caller-scoped catalog for local development."""

    def __init__(self, provider: SemanticProvider, credentials: Credentials,
                 catalog: SemanticCatalog, *, policy: ExecutionPolicy | None = None) -> None:
        self.provider = provider
        self._credentials = credentials
        self.catalog = catalog.model_copy(deep=True)
        self.policy = policy or ExecutionPolicy()
        self.registry = MethodRegistry()
        self.last_trial: MethodTrial | None = None
        self._engine = None

    @classmethod
    async def connect(cls, provider: SemanticProvider, credentials: Credentials,
                      *, policy: ExecutionPolicy | None = None) -> MethodSession:
        return cls(provider, credentials, await provider.discover(credentials), policy=policy)

    @classmethod
    async def cube(cls, url: str, credentials: Credentials, *, instance: str = "local",
                   policy: ExecutionPolicy | None = None) -> MethodSession:
        from .semantic.providers.cube.client import CubeClient
        from .semantic.providers.cube.provider import CubeProvider
        return await cls.connect(CubeProvider(CubeClient(url), instance=instance), credentials, policy=policy)

    def metrics(self) -> list[SemanticObject]:
        return [obj.model_copy(deep=True) for obj in self.catalog.objects
                if obj.public and obj.kind == "measure"]

    def dimensions(self, metric: str | None = None) -> list[SemanticObject]:
        refs = self.object(metric).dimension_refs if metric else None
        return [obj.model_copy(deep=True) for obj in self.catalog.objects
                if obj.public and obj.kind in ("dimension", "time_dimension")
                and (refs is None or obj.ref in refs)]

    def object(self, ref: str) -> SemanticObject:
        from .core.errors import UnknownSemanticObject
        obj = self.catalog.get(ref)
        if obj is None or not obj.public:
            raise UnknownSemanticObject("Semantic object is unavailable.", ref=ref)
        return obj.model_copy(deep=True)

    async def refresh_catalog(self) -> SemanticCatalog:
        refresh = getattr(self.provider, "refresh_catalog", self.provider.discover)
        self.catalog = (await refresh(self._credentials)).model_copy(deep=True)
        return self.catalog.model_copy(deep=True)

    def register(self, method: Method, *, replace: bool = False) -> Method:
        if not replace and any(m.name == method.manifest.name for m in self.registry.manifests()):
            raise InvalidBinding("Method already registered locally; use replace=True after editing.")
        return self.registry.register(method)

    async def run(self, method: str, *, bindings: dict[str, Any], scope: Scope,
                  params: dict[str, Any] | None = None) -> MethodTrial:
        """Run in this event loop. Every invocation has a fresh context and budget.

Use last_trial.attempts after a provider exception. No auto-retry or query cache.
Scope is explicit; all-period execution also needs policy.allow_all=True.
"""
        ctx = ExecutionContext(self.provider, self._credentials, self.catalog.model_copy(deep=True),
                               scope=deepcopy(scope), max_queries=self.policy.max_queries,
                               execution_policy=self.policy)
        trial = MethodTrial(method, deepcopy(bindings), deepcopy(params or {}), ctx)
        self.last_trial = trial
        choice = PeriodChoice(mode="range", date_range=scope.date_range) if scope.date_range else PeriodChoice(mode="all")
        if issue := self.policy.issue(choice):
            raise Refused(issue)
        manifest = self.registry.get(method).manifest
        resolved = self.registry.resolve_params(method, trial.params)
        needs_period = manifest.requires_period or any(
            spec.meaning == "period" and spec.type == "boolean" and resolved.get(name) is True
            for name, spec in manifest.parameters.items())
        if needs_period and scope.date_range is None:
            raise Refused("This Method needs an explicit date range.")
        async with asyncio.timeout(self.policy.deadline_seconds):
            trial.result = await self.registry.run(method, ctx, trial.bindings, trial.params)
        return trial

    async def preview(self, recipe: Recipe, *, step_index: int,
                      scope: dict[str, Any]) -> Run:
        """Execute a new Recipe prefix with canonical RunEngine and memory storage.

Each call issues fresh queries. Worker execution is for pipeline inspection;
use run() for kernel breakpoints. Runs stay local, not on the API server.
"""
        from .auth import identify
        from .recipes.loader import RecipeStore
        from .runs.engine import RunEngine
        from .runs.store import MemoryRunStore
        caller = await identify(self.provider, self._credentials)
        if self._engine is None:
            self._engine = RunEngine(self.provider,
                                     RecipeStore(None, self.provider.name, self.provider.instance),
                                     MemoryRunStore(), registry=self.registry, policy=self.policy)
        return await self._engine.preview(self._credentials, caller, recipe, step_index, deepcopy(scope))

    def close(self) -> None:
        """Release Recipe-preview worker resources; direct runs need no workers."""
        if self._engine is not None:
            self._engine.jobs.shutdown()
            self._engine = None
