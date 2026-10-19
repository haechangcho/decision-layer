"""Compile ordinary function signatures into the canonical Method manifest."""

from __future__ import annotations

import inspect
from typing import get_type_hints
from pydantic import TypeAdapter

from ...core.models import (
    DataInput as InputContract,
    MethodManifest,
    ParamSpec,
    RoleSpec,
)
from ..authoring import _parameter
from ..data_input import DataInput


def compile_function(
    fn,
    *,
    name,
    version,
    inputs,
    parameters,
    checks,
    output,
    adapt,
    requires_packages,
    option_checks=(),
    provides=(),
    label=None,
) -> tuple[MethodManifest, dict[str, TypeAdapter]]:
    if not inspect.isfunction(fn) or inspect.iscoroutinefunction(fn):
        raise ValueError("Register an ordinary synchronous Python function")
    if output not in ("auto", "table", "estimate"):
        raise ValueError("output must be auto, table or estimate")
    signature, hints = inspect.signature(fn), get_type_hints(fn)
    inputs = {
        key: value
        if isinstance(value, InputContract)
        else DataInput.model_validate(value)
        for key, value in inputs.items()
    }
    if not inputs or set(inputs) - set(signature.parameters):
        raise ValueError("Data inputs must name actual function arguments")
    explicit_arguments = {key for spec in inputs.values() for key in spec.column_args}
    inputs = {
        name: spec.contract(signature, explicit_arguments)
        if isinstance(spec, DataInput)
        else spec
        for name, spec in inputs.items()
    }
    column_args = [key for spec in inputs.values() for key in spec.column_args]
    if len(set(column_args)) != len(column_args):
        raise ValueError("Each column argument must belong to exactly one data input")
    if set(column_args) - set(signature.parameters) or set(column_args) & set(inputs):
        raise ValueError(
            "Column arguments must name separate actual function arguments"
        )
    overrides = parameters or {}
    if set(overrides) - (set(signature.parameters) - set(inputs) - set(column_args)):
        raise ValueError("Parameter types must name function options")
    roles, params, adapters = {}, {}, {}
    for key, argument in signature.parameters.items():
        if argument.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
            inspect.Parameter.POSITIONAL_ONLY,
        ):
            raise ValueError(
                "Use named function arguments; wrap variadic or positional-only library calls"
            )
        if key in inputs or key in column_args:
            continue
        annotation = overrides.get(key, hints.get(key))
        if annotation is None and type(argument.default) in (str, bool, int, float):
            annotation = type(argument.default)
        if annotation is None:
            raise ValueError(
                f"Declare parameters={{'{key}': type}} for an option without a scalar default/type"
            )
        params[key] = _parameter(annotation, argument.default)
        adapters[key] = TypeAdapter(annotation)
    for spec in inputs.values():
        if spec.filters_parameter:
            if (
                not spec.filters_parameter.isidentifier()
                or spec.filters_parameter in signature.parameters
            ):
                raise ValueError(
                    "Filter parameters must be separate named query inputs"
                )
            params[spec.filters_parameter] = ParamSpec(type="filters", default=[])
        for key, kind in [
            *((n, "measure") for n in spec.measures),
            *((n, "dimension") for n in spec.dimensions),
            *([(spec.entity, "entity")] if spec.entity else []),
        ]:
            role = spec.columns.get(key, RoleSpec(kind=kind))
            if key in roles and roles[key] != role:
                raise ValueError(
                    "Shared input bindings must have the same semantic kind"
                )
            roles[key] = role
        for key, role in spec.columns.items():
            if key in roles and roles[key] != role:
                raise ValueError(
                    "Shared input bindings must have the same semantic contract"
                )
            roles[key] = role
        if spec.period_parameter:
            if spec.period_parameter in signature.parameters:
                raise ValueError(
                    "Query period parameters must not shadow function arguments"
                )
            params[spec.period_parameter] = ParamSpec(
                type="date_range", required=True, meaning="period"
            )
    if set(roles) & set(params):
        raise ValueError("Data bindings and options must have distinct names")
    if any(not callable(check) for check in (*checks, *option_checks)) or (
        adapt is not None and not callable(adapt)
    ):
        raise ValueError("Checks/output adapters must be reviewed callables")
    packages = dict(requires_packages or {})
    if any(spec.format == "dataframe" for spec in inputs.values()):
        packages.setdefault("pandas", ">=2.2,<3")
    from packaging.requirements import Requirement

    for package, constraint in packages.items():
        requirement = Requirement(f"{package}{constraint}")
        if (
            requirement.url
            or requirement.marker
            or requirement.extras
            or requirement.name != package
        ):
            raise ValueError(
                "Dependencies require package names and version constraints"
            )
    manifest = MethodManifest(
        name=name,
        version=version,
        kind="stats",
        description=inspect.getdoc(fn) or name,
        roles=roles,
        parameters=params,
        execution="dataframe",
        interpretation="association",
        requires_period=True,
        requires_packages=packages,
        outputs=["table", "estimate"] if output == "auto" else [output],
        requires_capabilities=list(
            dict.fromkeys(
                "entity_grain_queries" if s.entity else "aggregate_queries"
                for s in inputs.values()
            )
        ),
        provides=list(provides),
        label=label or "",
        data_inputs=inputs,
    )
    return manifest, adapters
