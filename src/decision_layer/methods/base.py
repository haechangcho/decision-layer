"""Method contract and registry.

A Method is an atomic analytical capability (ADR-003). It declares its roles and
parameters in a manifest (drives API, MCP and the schema-driven UI), receives
bound semantic refs, asks the ExecutionContext for datasets, and returns a typed
Result. It never knows organisation-specific rules — that is a Recipe's job.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .. import __version__
from ..core.errors import DecisionLayerError
from ..core.ids import method_ref
from ..core.models import Artifact, MethodManifest, Provenance, Result, ValidationResult
from .context import ExecutionContext, NeedsInput, QueryBudgetExceeded, Refused
from ..i18n import _


class InvalidBinding(DecisionLayerError):
    code = "INVALID_BINDING"
    http_status = 400


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
                 warnings: list[str] | None = None, validation: list[ValidationResult] | None = None) -> None:
        self.primary = primary
        self.artifacts = artifacts or []
        self.warnings = warnings or []
        self.validation = validation or []


class MethodRegistry:
    def __init__(self) -> None:
        self._methods: dict[str, Method] = {}

    def register(self, method: Method) -> Method:
        self._methods[method.manifest.name] = method
        return method

    def get(self, name: str) -> Method:
        if name not in self._methods:
            raise InvalidBinding(_("Unknown method: {name}", name=name), available=sorted(self._methods))
        return self._methods[name]

    def manifests(self) -> list[MethodManifest]:
        return [m.manifest for m in self._methods.values()]

    async def run(self, name: str, ctx: ExecutionContext, bindings: dict[str, Any],
                  params: dict[str, Any] | None = None) -> Result:
        method = self.get(name)
        params = self._params(method, params or {})
        refs = self._check_bindings(method, ctx, bindings)
        first_query = len(ctx.queries)
        provenance = lambda: Provenance(  # noqa: E731
            method=method.ref, semantic_refs=refs, queries=ctx.queries[first_query:],
            runtime={"decision-layer": __version__})
        try:
            out = await method.run(ctx, bindings, params)
        except NeedsInput as e:
            return Result(status="needs_input", needs_input={"question": e.question, "field": e.field,
                                                             "candidates": e.candidates},
                          provenance=provenance())
        except (Refused, QueryBudgetExceeded) as e:
            return Result(status="refused", warnings=[e.message], provenance=provenance())
        failed = [v for v in out.validation if v.status == "fail"]
        return Result(
            status="refused" if failed else "success",
            interpretation=method.manifest.interpretation,
            primary=out.primary, artifacts=out.artifacts, warnings=out.warnings,
            validation=out.validation, provenance=provenance(),
        )

    # ── checks ────────────────────────────────────────────────────────────
    @staticmethod
    def _params(method: Method, params: dict[str, Any]) -> dict[str, Any]:
        spec = method.manifest.parameters
        unknown = set(params) - set(spec)
        if unknown:
            raise InvalidBinding(_("Unknown parameters: {names}", names=sorted(unknown)), allowed=sorted(spec))
        out = {k: p.default for k, p in spec.items()}
        out.update(params)
        missing = [k for k, p in spec.items() if p.required and out.get(k) is None]
        if missing:
            raise InvalidBinding(_("Missing required parameters: {names}", names=missing))
        for k, p in spec.items():
            if p.type == "enum" and out.get(k) is not None and out[k] not in (p.enum or []):
                raise InvalidBinding(_("{name} must be one of {values}", name=k, values=p.enum))
        return out

    @staticmethod
    def _check_bindings(method: Method, ctx: ExecutionContext, bindings: dict[str, Any]) -> list[str]:
        roles = method.manifest.roles
        unknown = set(bindings) - set(roles)
        if unknown:
            raise InvalidBinding(_("Unknown roles: {names}", names=sorted(unknown)), roles=sorted(roles))
        refs: list[str] = []
        for name, role in roles.items():
            value = bindings.get(name)
            if value in (None, []):
                if role.required:
                    raise InvalidBinding(_("Role '{role}' needs a semantic ref ({description})", role=name, description=role.description))
                continue
            values = value if isinstance(value, list) else [value]
            if not role.multiple and len(values) > 1:
                raise InvalidBinding(_("Role '{role}' takes a single ref", role=name))
            for ref in values:
                obj = ctx.obj(ref)
                kind_ok = obj.kind == role.kind or (role.kind == "dimension" and obj.kind == "time_dimension")
                if not kind_ok:
                    raise InvalidBinding(_("'{ref}' is a {kind} but role '{role}' needs a {expected}", ref=ref, kind=obj.kind, role=name, expected=role.kind))
                if role.metric_kinds and obj.metric_kind not in role.metric_kinds:
                    raise InvalidBinding(_("'{ref}' ({metric_kind}) can't be used for role '{role}' (allowed: {allowed})",
                                           ref=ref, metric_kind=obj.metric_kind, role=name, allowed=role.metric_kinds))
                refs.append(ref)
        return refs


registry = MethodRegistry()
