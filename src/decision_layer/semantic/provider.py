"""Semantic provider contract (ARCHITECTURE §5). Methods never talk to a provider
directly; the Dataset Planner hands a DatasetSpec to one of these."""
from __future__ import annotations

from typing import Literal, Protocol

from ..core.models import Dataset, DatasetSpec, ProviderCapabilities, SemanticCatalog, SemanticObject


class Credentials(Protocol):
    """Who is asking. Providers enforce their own access rules with it."""
    def bearer(self) -> str | None: ...


class SemanticProvider(Protocol):
    name: str
    instance: str
    # Whether an accepted bearer token authenticates its JWT claims or a shared credential.
    identity_mode: Literal["jwt_claims", "credential"]

    def capabilities(self) -> ProviderCapabilities: ...

    async def discover(self, credentials: Credentials) -> SemanticCatalog: ...

    async def resolve(self, refs: list[str], credentials: Credentials) -> list[SemanticObject]: ...

    async def validate_dataset(self, spec: DatasetSpec, credentials: Credentials) -> None:
        """Raise InvalidDatasetSpec / UnknownSemanticObject / CapabilityMissing when the spec can't run."""
        ...

    async def execute(self, spec: DatasetSpec, credentials: Credentials, *, with_sql: bool = False) -> Dataset: ...
