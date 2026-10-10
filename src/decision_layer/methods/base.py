"""Atomic Method implementation and returned output contract."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from ..core.ids import method_ref
from ..core.models import Artifact, MethodManifest, SelectionOutput, ValidationResult
from .context import ExecutionContext


class Method(ABC):
    manifest: MethodManifest

    @property
    def ref(self) -> str:
        return method_ref(self.manifest.name, self.manifest.version)

    @abstractmethod
    async def run(self, ctx: ExecutionContext, bindings: dict[str, Any], params: dict[str, Any]) -> "MethodOutput":
        ...


class MethodOutput:
    """What a Method returns before the registry wraps it into a Result with provenance."""

    def __init__(self, primary: Artifact | None = None, artifacts: list[Artifact] | None = None,
                 warnings: list[str] | None = None, validation: list[ValidationResult] | None = None,
                 runtime: dict[str, str] | None = None, selections: dict[str, SelectionOutput] | None = None,
                 provides: list[str] | None = None) -> None:
        self.primary = primary
        self.artifacts = artifacts or []
        self.warnings = warnings or []
        self.validation = validation or []
        self.runtime = runtime or {}
        self.selections = selections or {}
        self.provides = provides
