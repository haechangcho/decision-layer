"""Ordinary Python functions with separately declared governed data inputs.

This is an adapter to the existing registry/context/worker, not another runtime.
No function body, async convention or Decision Layer output class is required.
"""

from __future__ import annotations
import inspect
import math
from hashlib import sha256
from typing import get_type_hints

from pydantic import TypeAdapter

from ..core.models import (
    DataInput,
    MethodManifest,
    ParamSpec,
    RoleSpec,
    ValidationResult,
)
from .authoring import _parameter
from .base import Method, MethodOutput
from .output import Estimate, Table


def _fingerprint(fn):
    try:
        return sha256(inspect.getsource(fn).encode()).hexdigest()
    except (OSError, TypeError):
        return "unavailable"


def _check_options(checks, options):
    validation = []
    for check in checks:
        try:
            value = check(**options)
            if value is not None and value is not True and value is not False:
                raise TypeError("Option checks must return None/bool")
            passed = value is not False
            message = (
                "Executed option check passed"
                if passed
                else "Executed option check failed"
            )
        except (ValueError, AssertionError) as exc:
            passed, message = False, str(exc)
        validation.append(
            ValidationResult(
                validator=f"{check.__module__}.{check.__qualname__}",
                code="PYTHON_OPTION_CHECK",
                status="pass" if passed else "fail",
                message=message,
            )
        )
        if not passed:
            break
    return validation


def _execute_python(
    fn, rows_by_name, inputs, options, checks, output, adapt, resolved=None
):
    data, validation, column_args = {}, [], {}
    for name, spec in inputs.items():
        rows = rows_by_name[name]
        columns = [
            *(["unit"] if spec.entity else []),
            *(["time"] if spec.time_granularity else []),
            *spec.dimensions,
            *spec.measures,
        ]
        contract = (resolved or {}).get(name, {})
        columns = contract.get("columns", columns)
        measures = contract.get("measures", spec.measures)
        for argument in spec.column_args:
            if argument not in contract.get("column_args", {}):
                raise ValueError(f"Missing resolved column argument: {name}.{argument}")
            value = contract["column_args"][argument]
            selected = (
                value
                if isinstance(value, list)
                else [value]
                if value is not None
                else []
            )
            if any(column not in columns for column in selected):
                raise ValueError(
                    f"Column argument is outside its input table: {argument}"
                )
            column_args[argument] = value

        def record(code, passed, message):
            validation.append(
                ValidationResult(
                    validator=f"python.input.{name}@1",
                    code=code,
                    status="pass" if passed else "fail",
                    message=message,
                )
            )

        record(
            "MINIMUM_ROWS",
            len(rows) >= spec.minimum_rows,
            f"{name}: {len(rows)} rows; minimum {spec.minimum_rows}.",
        )
        record(
            "REQUIRED_COLUMNS",
            all(set(columns) <= row.keys() for row in rows),
            f"{name}: required columns present.",
        )
        record(
            "FINITE_MEASURES",
            all(
                isinstance(row.get(col), (int, float))
                and not isinstance(row.get(col), bool)
                and math.isfinite(row[col])
                for row in rows
                for col in measures
            ),
            f"{name}: measure values finite and non-null.",
        )
        keys = ["unit"] if spec.entity else list(spec.dimensions)
        if spec.time_granularity:
            keys.append("time")
        record(
            "NON_NULL_GRAIN",
            all(row.get(key) is not None for row in rows for key in keys),
            f"{name}: grain keys are non-null.",
        )
        values = [tuple(row.get(key) for key in keys) for row in rows]
        record(
            "UNIQUE_GRAIN",
            len(set(values)) == len(values),
            f"{name}: returned grain is unique.",
        )
        if spec.format == "dataframe":
            import pandas as pd

            data[name] = pd.DataFrame(rows, columns=columns)
            data[name].attrs["semantic_refs"] = contract.get("semantic_refs", {})
        else:
            data[name] = rows
    if any(item.status == "fail" for item in validation):
        return MethodOutput(validation=validation)
    for check in checks:
        ident = f"{check.__module__}.{check.__qualname__}"
        try:
            returned = check(**data)
            if returned is not None and returned is not True and returned is not False:
                raise TypeError(
                    "Checks must return None/bool or raise ValueError/AssertionError"
                )
            passed, message = (
                returned is not False,
                "Executed check passed"
                if returned is not False
                else "Executed check failed",
            )
        except (ValueError, AssertionError) as exc:
            passed, message = False, str(exc) or "Executed check failed"
        validation.append(
            ValidationResult(
                validator=ident,
                code="PYTHON_CHECK",
                status="pass" if passed else "fail",
                message=message,
            )
        )
        if not passed:
            return MethodOutput(validation=validation)
    value = fn(**data, **column_args, **options)
    if adapt:
        value = adapt(value)
    if isinstance(value, (Table, Estimate)):
        result = value
    elif output == "estimate":
        result = (
            Estimate(value["value"], details=value)
            if isinstance(value, dict)
            else Estimate(value.item() if hasattr(value, "item") else value)
        )
    elif (
        output == "auto"
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
    ):
        result = Estimate(value)
    else:
        if hasattr(value, "to_dict"):
            value = value.to_dict(orient="records")
        result = Table([value] if isinstance(value, dict) else value)
    if output != "auto" and result.artifact_type != output:
        raise ValueError("Python output does not match the registered output adapter")
    result.validation = [*validation, *result.validation]
    result.warnings.append(
        "Input checks do not establish source completeness, metric equivalence or causal identification."
    )
    return result


class PythonMethod(Method):
    def __init__(
        self,
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
    ):
        if not inspect.isfunction(fn) or inspect.iscoroutinefunction(fn):
            raise ValueError("Register an ordinary synchronous Python function")
        if output not in ("auto", "table", "estimate"):
            raise ValueError("output must be auto, table or estimate")
        signature, hints = inspect.signature(fn), get_type_hints(fn)
        inputs = {
            key: value
            if isinstance(value, DataInput)
            else DataInput.model_validate(value)
            for key, value in inputs.items()
        }
        if not inputs or set(inputs) - set(signature.parameters):
            raise ValueError("Data inputs must name actual function arguments")
        column_args = [key for spec in inputs.values() for key in spec.column_args]
        if len(set(column_args)) != len(column_args):
            raise ValueError(
                "Each column argument must belong to exactly one data input"
            )
        if set(column_args) - set(signature.parameters) or set(column_args) & set(
            inputs
        ):
            raise ValueError(
                "Column arguments must name separate actual function arguments"
            )
        overrides = parameters or {}
        if set(overrides) - (
            set(signature.parameters) - set(inputs) - set(column_args)
        ):
            raise ValueError("Parameter types must name function options")
        roles, params, self.adapters = {}, {}, {}
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
            self.adapters[key] = TypeAdapter(annotation)
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
                role = RoleSpec(kind=kind)
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
        self.fn, self.inputs, self.checks, self.output, self.adapt = (
            fn,
            inputs,
            tuple(checks),
            output,
            adapt,
        )
        self.option_checks = tuple(option_checks)
        self.manifest = MethodManifest(
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

    async def run(self, ctx, bindings, params):
        rows, resolved, validation = {}, {}, []
        from ..core.models import Filter

        options = {
            name: adapter.validate_python(params[name])
            for name, adapter in self.adapters.items()
            if name in params
        }
        if self.option_checks:
            validation = await ctx.compute(_check_options, self.option_checks, options)
            if any(check.status == "fail" for check in validation):
                return MethodOutput(validation=validation)

        def bound(name):
            value = bindings[name]
            if self.manifest.roles[name].multiple:
                return value if isinstance(value, list) else [value]
            return value[0] if isinstance(value, list) else value

        for name, spec in self.inputs.items():
            data = await ctx.aggregate(
                measures={n: bound(n) for n in spec.measures},
                dimensions={
                    **{n: bound(n) for n in spec.dimensions},
                    **{n: bound(n) for n in spec.columns if bindings.get(n)},
                },
                entity=bound(spec.entity) if spec.entity else None,
                period=params.get(spec.period_parameter)
                if spec.period_parameter
                else None,
                period_role=spec.period_role,
                filters=[
                    Filter.model_validate(item)
                    for item in params.get(spec.filters_parameter, [])
                ]
                if spec.filters_parameter
                else None,
                time_granularity=spec.time_granularity,
                label=f"python:{name}",
            )
            rows[name] = data.records()
            aliases = {
                alias: ref for pairs in data.roles.values() for alias, ref in pairs
            }
            resolved[name] = {
                "columns": list(aliases),
                "semantic_refs": aliases,
                "measures": [
                    alias
                    for alias, ref in aliases.items()
                    if ref in data.dataset.spec.measures
                ],
                "grain": "entity" if spec.entity else "aggregate",
            }
            resolved[name]["column_args"] = {
                argument: (
                    [alias for alias, _ in data.roles.get(argument, [])]
                    if self.manifest.roles[argument].multiple
                    else next(
                        (alias for alias, _ in data.roles.get(argument, [])), None
                    )
                )
                for argument in spec.column_args
            }
        result = await ctx.compute(
            _execute_python,
            self.fn,
            rows,
            self.inputs,
            options,
            self.checks,
            self.output,
            self.adapt,
            resolved,
        )
        result.validation = [*validation, *result.validation]
        result.runtime.update(
            {
                "python.function": f"{self.fn.__module__}.{self.fn.__qualname__}",
                "python.function_sha256": _fingerprint(self.fn),
                "python.inputs": __import__("json").dumps(
                    {k: v.model_dump() for k, v in self.inputs.items()}
                ),
            }
        )
        result.runtime["python.resolved_inputs"] = __import__("json").dumps(resolved)
        for index, check in enumerate(self.option_checks):
            result.runtime[f"python.option_check.{index}.sha256"] = _fingerprint(check)
        for index, check in enumerate(self.checks):
            result.runtime[f"python.check.{index}.sha256"] = _fingerprint(check)
        if self.adapt:
            result.runtime["python.output_adapter.sha256"] = _fingerprint(self.adapt)
        return result


def python_method(
    fn,
    *,
    name: str,
    version: str,
    inputs: dict[str, DataInput],
    parameters=None,
    checks=(),
    output="auto",
    adapt=None,
    requires_packages=None,
    option_checks=(),
    provides=(),
    label=None,
) -> Method:
    """Register ordinary Python separately from data access. Scalar defaults infer option types.

    Inputs may be several governed tables. Function arguments contain data/options,
    never provider credentials. Checks receive named data inputs; failed checks stop
    calculation. A check is recorded as passed only after it actually executes.
    DataInput.column_args injects resolved column names (str/list[str]) into the
    ordinary function. Clients bind those roles to semantic refs, never raw columns.
    """
    return PythonMethod(
        fn,
        name=name,
        version=version,
        inputs=inputs,
        parameters=parameters,
        checks=checks,
        output=output,
        adapt=adapt,
        requires_packages=requires_packages,
        option_checks=option_checks,
        provides=provides,
        label=label or "",
    )
