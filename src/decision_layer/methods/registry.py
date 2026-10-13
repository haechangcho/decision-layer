"""Method contract and registry.

A Method is an atomic analytical capability (ADR-003). It declares its roles and
parameters in a manifest (drives API, MCP and the schema-driven UI), receives
bound semantic refs, asks the ExecutionContext for datasets, and returns a typed
Result. It never knows organisation-specific rules — that is a Recipe's job.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from math import isfinite
from typing import Any

from .. import __version__
from ..core.errors import DecisionLayerError
from ..core.models import MethodManifest, ParamSpec, Provenance, Result
from .context import ExecutionContext, NeedsInput, QueryBudgetExceeded, Refused
from .base import Method
from .inputs import AnalysisDesign, Equality, parameter_refs
from ..i18n import _


class InvalidBinding(DecisionLayerError):
    code = "INVALID_BINDING"
    http_status = 400


class MethodRegistry:
    def __init__(self) -> None:
        self._methods: dict[str, Method] = {}

    def register(self, method: Method) -> Method:
        Provenance(method=method.ref, semantic_refs=[], queries=[], runtime={})
        self._params(method, {}, partial=True)
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
            parameter_references = parameter_refs(spec.type, value) if spec.type in ("condition", "filters", "drill_path") else (value or []) if spec.type == "ref_list" else []
            if spec.semantic_kind and spec.type == "string" and value:
                parameter_references = [value]
            for ref in parameter_references:
                obj = ctx.obj(ref)
                if spec.type in ("condition", "filters") and obj.kind not in ("dimension", "time_dimension"):
                    raise InvalidBinding(_("Filter inputs require dimensions"))
                if spec.semantic_kind and obj.kind != spec.semantic_kind and not (spec.semantic_kind == "dimension" and obj.kind == "time_dimension"):
                    raise InvalidBinding(f"Parameter '{key}' requires {spec.semantic_kind}; got {obj.kind}")
                if ref not in refs:
                    refs.append(ref)
        first_query = len(ctx.queries)
        first_attempt = len(ctx.attempts)
        def used_refs():
            used = list(refs)
            for attempt in ctx.attempts[first_attempt:]:
                spec = attempt.spec
                candidates = [*spec.measures, *spec.dimensions, *(item.member for item in spec.filters)]
                candidates += [spec.time.dimension] if spec.time else []
                candidates += [spec.entity] if spec.entity else []
                used.extend(ref for ref in candidates if ref not in used)
            return used
        def provenance():
            import platform
            from .dependencies import runtime_versions
            return Provenance(method=method.ref, semantic_refs=used_refs(), queries=ctx.queries[first_query:],
                runtime={"decision-layer": __version__, "python": platform.python_version(),
                         **runtime_versions({"numpy": "", **method.manifest.requires_packages})})
        try:
            from .dependencies import dependency_issue
            if issue := dependency_issue(method.manifest.requires_packages):
                raise Refused(issue)
            for capability in method.manifest.requires_capabilities:
                if not getattr(ctx.provider.capabilities(), capability, False):
                    raise Refused(_("The provider lacks a required Method capability"), capability=capability)
            out = await method.run(ctx, bindings, params)
        except NeedsInput as e:
            return Result(status="needs_input", needs_input={"question": e.question, "field": e.field,
                                                             "candidates": e.candidates},
                          provenance=provenance())
        except (Refused, QueryBudgetExceeded) as e:
            return Result(status="refused", warnings=[e.message], provenance=provenance())
        failed = [v for v in out.validation if v.status == "fail"]
        artifacts = [*out.artifacts, *([out.primary] if out.primary is not None else [])]
        undeclared = {artifact.type for artifact in artifacts} - set(method.manifest.outputs)
        if undeclared:
            raise InvalidBinding(_("The Method returned an undeclared artifact type."), outputs=sorted(undeclared))
        if set(out.selections) - set(method.manifest.selection_outputs):
            raise InvalidBinding(_("The Method returned an undeclared selection output."))
        provided = out.provides if out.provides is not None else method.manifest.result_capabilities(params)
        if set(provided) - set(method.manifest.provides):
            raise InvalidBinding(_("The Method returned an undeclared result capability."))
        evidence = provenance()
        evidence.runtime.update(out.runtime)
        evidence.runtime["decision-layer"] = __version__
        return Result(
            status="refused" if failed else "success",
            interpretation=method.manifest.interpretation,
            provides=provided if not failed and out.primary is not None else [],
            primary=out.primary, artifacts=out.artifacts, warnings=out.warnings,
            validation=out.validation, provenance=evidence, selections=out.selections,
        )

    # ── checks ────────────────────────────────────────────────────────────
    def resolve_params(self, name: str, params: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
        return self._params(self.get(name), params, partial=partial)

    @staticmethod
    def _params(method: Method, params: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
        values = MethodRegistry.input_values(method.manifest.parameters, params, partial=partial)
        from pydantic import ValidationError
        for name, adapter in getattr(method, "adapters", {}).items():
            if values.get(name) is None:
                continue
            try:
                validated = adapter.validate_python(values[name])
                values[name] = adapter.dump_python(validated, mode="json")
            except ValidationError as exc:
                raise InvalidBinding(_("Invalid structured Method input"), parameter=name) from exc
        return values

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
            if p.type in ("condition", "filters", "design", "date_ranges"):
                from ..core.models import Filter
                from ..core.periods import checked_range
                try:
                    if p.type == "condition":
                        out[k] = Equality.model_validate(value).model_dump(mode="json")
                    elif p.type == "filters":
                        if not isinstance(value, list) or len(value) > 30:
                            raise ValueError("Expected at most 30 filters")
                        out[k] = [Filter.model_validate(item).model_dump(mode="json") for item in value]
                    elif p.type == "design":
                        out[k] = AnalysisDesign.model_validate(value).model_dump(mode="json", exclude_none=True)
                    else:
                        if not isinstance(value, list) or len(value) > 30:
                            raise ValueError("Expected at most 30 windows")
                        out[k] = [checked_range(item) for item in value]
                except (ValueError, TypeError, KeyError) as exc:
                    raise InvalidBinding(_("Invalid structured Method input"), parameter=k) from exc
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
            if p.type == "ranges" and any(any(a >= b for a, b in zip(edges, edges[1:])) for edges in value.values()):
                raise InvalidBinding(_("Range edges must be strictly increasing without duplicates."))
            if p.type == "group":
                scalar = lambda item: isinstance(item, (str, bool, int, float)) and not (isinstance(item, (int, float)) and not isfinite(item))
                valid = scalar(value)
                if isinstance(value, list):
                    valid = bool(value) and all(scalar(item) for item in value)
                elif isinstance(value, dict):
                    keys = set(value)
                    if keys in ({"values"}, {"exclude"}):
                        items = next(iter(value.values()))
                        valid = isinstance(items, list) and bool(items) and all(scalar(item) for item in items)
                    elif keys and keys <= {"gte", "lt"}:
                        valid = all(isinstance(item, (int, float)) and not isinstance(item, bool) and isfinite(item) for item in value.values())
                        valid = valid and ("gte" not in value or "lt" not in value or value["gte"] < value["lt"])
                    else:
                        valid = False
                if not valid:
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
                if role.accepted_kinds:
                    kind_ok = obj.kind in role.accepted_kinds
                if role.kind == "entity":
                    kind_ok = obj.kind == "dimension" and any(o.public and o.entity == ref for o in ctx.catalog.objects)
                if not kind_ok:
                    raise InvalidBinding(_("'{ref}' is a {kind} but role '{role}' needs a {expected}", ref=ref, kind=obj.kind, role=name, expected=role.kind))
                if role.metric_kinds and obj.metric_kind not in role.metric_kinds:
                    raise InvalidBinding(_("'{ref}' ({metric_kind}) can't be used for role '{role}' (allowed: {allowed})",
                                           ref=ref, metric_kind=obj.metric_kind, role=name, allowed=role.metric_kinds))
                if role.data_type and obj.data_type != role.data_type:
                    raise InvalidBinding(_("The semantic role has an incompatible data type"), role=name)
                refs.append(ref)
        return refs
