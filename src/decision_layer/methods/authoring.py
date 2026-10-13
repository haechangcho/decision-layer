"""Typed Python functions compile to the existing Method contract, without registration."""
from __future__ import annotations
import inspect
from functools import update_wrapper
from typing import Annotated, Literal, get_args, get_origin, get_type_hints
from pydantic import TypeAdapter
from ..core.models import Filter, MethodManifest, ParamSpec, RoleSpec
from .base import Method, MethodOutput
from .inputs import AnalysisDesign, Equality, SemanticRole
from .output import Estimate, Table, TimeSeries


def _role(annotation):
    multiple = get_origin(annotation) is list
    target = get_args(annotation)[0] if multiple else annotation
    import types
    from typing import Union
    if get_origin(target) in (types.UnionType, Union):
        kinds = []
        for candidate in get_args(target):
            if get_origin(candidate) is Annotated:
                marker = next((item for item in get_args(candidate)[1:] if isinstance(item, SemanticRole)), None)
                if marker:
                    kinds.append(marker.kind)
        if kinds and len(kinds) == len(get_args(target)) and set(kinds) <= {"measure", "dimension", "time_dimension"}:
            return RoleSpec(kind=kinds[0], accepted_kinds=kinds, multiple=multiple)
    if get_origin(target) is Annotated:
        marker = next((item for item in get_args(target)[1:] if isinstance(item, SemanticRole)), None)
        if marker:
            return RoleSpec(kind=marker.kind, multiple=multiple)
    return None


def _parameter(annotation, default):
    import types
    from typing import Union
    if get_origin(annotation) in (types.UnionType, Union) and type(None) in get_args(annotation):
        annotation = next(item for item in get_args(annotation) if item is not type(None))
    origin, args = get_origin(annotation), get_args(annotation)
    metadata = args[1:] if origin is Annotated else []
    base = args[0] if origin is Annotated else annotation
    required = default is inspect.Parameter.empty
    if "date_range" in metadata:
        kind = "date_range"
    elif get_origin(base) is list and get_origin(get_args(base)[0]) is Annotated and "date_range" in get_args(get_args(base)[0])[1:]:
        kind = "date_ranges"
    elif base is Equality:
        kind = "condition"
    elif base is AnalysisDesign:
        kind = "design"
    elif get_origin(base) is list and get_args(base)[0] is Filter:
        kind = "filters"
    elif get_origin(base) is Literal:
        values = get_args(base)
        if not all(isinstance(item, str) for item in values):
            raise ValueError("Only string Literal options are supported")
        return ParamSpec(type="enum", enum=list(values), required=required,
                         default=None if required else default)
    else:
        kind = {str: "string", bool: "boolean", int: "integer", float: "number"}.get(base)
    if kind is None:
        raise ValueError(f"Unsupported Method parameter annotation: {annotation}")
    schema = TypeAdapter(annotation).json_schema()
    return ParamSpec(type=kind, required=required, default=None if required else default,
                     minimum=schema.get("minimum"), maximum=schema.get("maximum"))


class FunctionMethod(Method):
    def __init__(self, fn, name, version, *, interpretation, kind, execution, provides,
                 requires_packages, requires_period):
        if not inspect.iscoroutinefunction(fn):
            raise ValueError("Method functions must be async; pure computation can use ordinary helpers")
        signature = inspect.signature(fn)
        hints = get_type_hints(fn, include_extras=True)
        if not signature.parameters or next(iter(signature.parameters)) != "ctx":
            raise ValueError("The first Method argument must be ctx")
        roles, params, self.adapters = {}, {}, {}
        for key, argument in list(signature.parameters.items())[1:]:
            if argument.kind != inspect.Parameter.KEYWORD_ONLY:
                raise ValueError("Method inputs must be keyword-only")
            annotation = hints.get(key)
            if role := _role(annotation):
                if argument.default not in (inspect.Parameter.empty, None):
                    raise ValueError("Semantic defaults may only be omitted")
                role.required = argument.default is inspect.Parameter.empty
                roles[key] = role
            else:
                params[key] = _parameter(annotation, argument.default)
                self.adapters[key] = TypeAdapter(annotation)
        output = hints.get("return")
        if output not in (Table, TimeSeries, Estimate):
            raise ValueError("Declare Table, TimeSeries or Estimate as the return type")
        self.fn, self.output = fn, output
        self.manifest = MethodManifest(name=name, version=version, kind=kind,
            description=inspect.getdoc(fn) or name, roles=roles, parameters=params,
            interpretation=interpretation, execution=execution, outputs=[output.artifact_type],
            provides=list(provides or []), requires_packages=requires_packages or {},
            requires_period=requires_period,
            requires_capabilities=["entity_grain_queries"] if any(role.kind == "entity" for role in roles.values()) else [])
        update_wrapper(self, fn)
        self.__signature__ = signature

    async def run(self, ctx, bindings, params):
        inputs = {**bindings, **{key: self.adapters[key].validate_python(value)
                                for key, value in params.items()}}
        result = await self.fn(ctx, **inputs)
        if not isinstance(result, self.output):
            raise ValueError("Method returned a value inconsistent with its declared return type")
        return result


def method(name: str, *, version: str, interpretation: str,
           kind="query", execution="semantic_pushdown", provides=None,
           requires_packages=None, requires_period=False):
    """Compile a reviewed function; callers explicitly register it in their registry."""
    def decorate(fn):
        return FunctionMethod(fn, name, version, interpretation=interpretation, kind=kind,
                              execution=execution, provides=provides,
                              requires_packages=requires_packages, requires_period=requires_period)
    return decorate
