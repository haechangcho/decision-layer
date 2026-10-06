"""Method contract and registry.

A Method is an atomic analytical capability (ADR-003). It declares its roles and
parameters in a manifest (drives API, MCP and the schema-driven UI), receives
bound semantic refs, asks the ExecutionContext for datasets, and returns a typed
Result. It never knows organisation-specific rules — that is a Recipe's job.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import date
from math import isfinite
from typing import Any

from .. import __version__
from ..core.errors import DecisionLayerError
from ..core.ids import method_ref
from ..core.models import Artifact, MethodManifest, ParamSpec, Provenance, Result, SelectionOutput, ValidationResult
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
                 warnings: list[str] | None = None, validation: list[ValidationResult] | None = None,
                 runtime: dict[str, str] | None = None, selections: dict[str, SelectionOutput] | None = None) -> None:
        self.primary = primary
        self.artifacts = artifacts or []
        self.warnings = warnings or []
        self.validation = validation or []
        self.runtime = runtime or {}
        self.selections = selections or {}


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
        params = self.resolve_params(name, params or {})
        refs = self._check_bindings(method, ctx, bindings)
        for key, spec in method.manifest.parameters.items():
            value = params.get(key)
            parameter_refs = [item["member"] for item in value or []] if spec.type == "drill_path" else (value or []) if spec.type == "ref_list" else []
            if spec.semantic_kind and spec.type == "string" and value:
                parameter_refs = [value]
            for ref in parameter_refs:
                obj = ctx.obj(ref)
                if spec.semantic_kind and obj.kind != spec.semantic_kind and not (spec.semantic_kind == "dimension" and obj.kind == "time_dimension"):
                    raise InvalidBinding(f"Parameter '{key}' requires {spec.semantic_kind}; got {obj.kind}")
                if ref not in refs:
                    refs.append(ref)
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
        if set(out.selections) - set(method.manifest.selection_outputs):
            raise InvalidBinding("The Method returned an undeclared selection output.")
        evidence = provenance()
        evidence.runtime.update(out.runtime)
        evidence.runtime["decision-layer"] = __version__
        return Result(
            status="refused" if failed else "success",
            interpretation=method.manifest.interpretation,
            primary=out.primary, artifacts=out.artifacts, warnings=out.warnings,
            validation=out.validation, provenance=evidence, selections=out.selections,
        )

    # ── checks ────────────────────────────────────────────────────────────
    def resolve_params(self, name: str, params: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
        return self._params(self.get(name), params, partial=partial)

    @staticmethod
    def _params(method: Method, params: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
        return MethodRegistry.input_values(method.manifest.parameters, params, partial=partial)

    @staticmethod
    def input_values(spec: dict[str, ParamSpec], params: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
        unknown = set(params) - set(spec)
        if unknown:
            raise InvalidBinding(_("Unknown parameters: {names}", names=sorted(unknown)), allowed=sorted(spec))
        out = {k: deepcopy(p.default) for k, p in spec.items()}
        out.update(params)
        missing = [k for k, p in spec.items() if p.required and out.get(k) is None]
        if missing and not partial:
            raise InvalidBinding(_("Missing required parameters: {names}", names=missing))
        for k, p in spec.items():
            value = out.get(k)
            if value is None:
                if p.default is not None:
                    raise InvalidBinding(_("{name} must be a {type}", name=k, type=p.type))
                continue
            if p.type == "enum" and value not in (p.enum or []):
                raise InvalidBinding(_("{name} must be one of {values}", name=k, values=p.enum))
            if p.type == "boolean" and not isinstance(value, bool):
                raise InvalidBinding(_("{name} must be a {type}", name=k, type=p.type))
            if p.type == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
                raise InvalidBinding(_("{name} must be a {type}", name=k, type=p.type))
            if p.type == "number" and (isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value)):
                raise InvalidBinding(_("{name} must be a {type}", name=k, type=p.type))
            if p.type == "string" and not isinstance(value, str):
                raise InvalidBinding(_("{name} must be a {type}", name=k, type=p.type))
            if p.type == "date_range" and (not isinstance(value, (list, tuple)) or len(value) != 2
                                           or not all(isinstance(day, str) for day in value)):
                raise InvalidBinding(_("{name} has an invalid structure", name=k))
            if p.type == "date_range":
                try:
                    start, end = (date.fromisoformat(day) for day in value)
                    if start > end:
                        raise ValueError
                except ValueError as exc:
                    raise InvalidBinding(_("{name} has an invalid structure", name=k)) from exc
            if p.type == "drill_path" and (not isinstance(value, list) or any(
                    not isinstance(item, dict) or not isinstance(item.get("member"), str) or "value" not in item
                    for item in value)):
                raise InvalidBinding(_("{name} has an invalid structure", name=k))
            if p.type == "number_list" and (not isinstance(value, list) or any(
                    isinstance(item, bool) or not isinstance(item, (int, float)) or not isfinite(item)
                    for item in value)):
                raise InvalidBinding(_("{name} has an invalid structure", name=k))
            if p.type == "ref_list" and (not isinstance(value, list) or any(not isinstance(item, str) for item in value)):
                raise InvalidBinding(_("{name} has an invalid structure", name=k))
            if p.type == "ranges" and (not isinstance(value, dict) or any(
                    not isinstance(edges, list) or any(isinstance(edge, bool) or not isinstance(edge, (int, float))
                    or not isfinite(edge) for edge in edges) for edges in value.values())):
                raise InvalidBinding(_("{name} has an invalid structure", name=k))
            if p.minimum is not None and value < p.minimum:
                raise InvalidBinding(_("{name} must be at least {minimum}", name=k, minimum=p.minimum))
            if p.maximum is not None and value > p.maximum:
                raise InvalidBinding(_("{name} must be at most {maximum}", name=k, maximum=p.maximum))
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
