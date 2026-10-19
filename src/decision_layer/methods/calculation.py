"""Legacy calculation/InputTable registration; new code uses python_method/DataInput.

Only reviewed Python is registered. This is neither a code upload API nor a
sandbox. Source extraction still goes through ExecutionContext and its budgets.
"""
from __future__ import annotations

import inspect
import math
from typing import Literal, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from ..core.models import MethodManifest, RoleSpec, ValidationResult
from .authoring import _parameter
from .base import Method, MethodOutput
from .output import Estimate, Table


class InputTable(BaseModel):
    """Map calculation column names to runtime binding roles, never SQL formulas.

    Example: measures={"sales": "metric"}, dimensions={"department": "group"}.
    Callers bind metric/group to references discovered from their provider.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)
    measures: dict[str, str]
    dimensions: dict[str, str] = Field(default_factory=dict)
    entity: str | None = None
    format: Literal["records", "dataframe"] = "records"
    minimum_rows: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def valid_mapping(self):
        if not self.measures:
            raise ValueError("At least one governed measure is required")
        if set(self.measures) & set(self.dimensions):
            raise ValueError("Input column aliases must be unique")
        if self.entity and "unit" in {*self.measures, *self.dimensions}:
            raise ValueError("unit is reserved for the entity key")
        names = [*self.measures, *self.dimensions, *self.measures.values(), *self.dimensions.values()]
        if self.entity:
            names.append(self.entity)
        if any(not name.isidentifier() for name in names):
            raise ValueError("Aliases and binding roles must be Python identifiers")
        roles = [*self.measures.values(), *self.dimensions.values(), *([self.entity] if self.entity else [])]
        if len(set(roles)) != len(roles):
            raise ValueError("Each input column needs a distinct binding role")
        return self


def _evaluate(fn, rows, params, table, validators, output, adapt):
    """Worker arguments contain extracted data, not an ExecutionContext/credentials."""
    columns = [*(["unit"] if table.entity else []), *table.dimensions, *table.measures]
    checks = []

    def check(code, passed, message):
        checks.append(ValidationResult(validator="calculation.input@1", code=code,
                                      status="pass" if passed else "fail", message=message))

    check("MINIMUM_ROWS", len(rows) >= table.minimum_rows,
          f"Observed {len(rows)} rows; required at least {table.minimum_rows}.")
    check("COMPLETE_COLUMNS", all(set(columns) <= row.keys() and all(row[name] is not None for name in columns) for row in rows),
          "Required input columns must be present and non-null.")
    check("FINITE_MEASURES", all(isinstance(row.get(name), (int, float)) and not isinstance(row.get(name), bool)
                                and math.isfinite(row[name]) for row in rows for name in table.measures),
          "Measure values must be finite numbers.")
    keys = ["unit"] if table.entity else list(table.dimensions)
    # A grouped extraction must contain one row per declared group; this checks
    # returned observations, not upstream completeness or official metric meaning.
    if keys:
        seen = [tuple(row.get(key) for key in keys) for row in rows]
        check("UNIQUE_GRAIN", len(set(seen)) == len(seen),
              "Returned analysis keys must be unique.")
    else:
        check("SCALAR_GRAIN", len(rows) == 1, "An ungrouped aggregate must return exactly one row.")
    if any(check.status == "fail" for check in checks):
        return MethodOutput(validation=checks)
    if table.format == "dataframe":
        import pandas as pd
        data = pd.DataFrame(rows, columns=columns)
    else:
        data = rows
    for validator in validators:
        observed = validator(data)
        if isinstance(observed, ValidationResult):
            observed = [observed]
        if not isinstance(observed, list) or not observed or any(not isinstance(item, ValidationResult) for item in observed):
            raise ValueError("A calculation validator must return explicit ValidationResult records")
        checks.extend(observed)
        if any(item.status == "fail" for item in observed):
            return MethodOutput(validation=checks)
    value = fn(data, **params)
    if adapt:
        result = adapt(value)
    elif isinstance(value, output):
        result = value
    elif output is Table:
        if hasattr(value, "to_dict"):
            value = value.to_dict(orient="records")
        result = Table(value)
    else:
        result = Estimate(value.item() if hasattr(value, "item") else value)
    if not isinstance(result, output):
        raise ValueError("Calculation adapter returned an undeclared output type")
    result.validation = [*checks, *result.validation]
    result.warnings.append("Input checks do not establish source completeness, metric equivalence or causal identification.")
    return result


class CalculationMethod(Method):
    def __init__(self, fn, *, name, version, table, output, adapt, validators,
                 requires_packages, requires_period):
        if not inspect.isfunction(fn) or inspect.iscoroutinefunction(fn):
            raise ValueError("Register an ordinary synchronous Python function")
        if output not in (Table, Estimate):
            raise ValueError("Declare Table or Estimate output")
        signature = inspect.signature(fn)
        arguments = list(signature.parameters.values())
        if not arguments or arguments[0].kind not in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            raise ValueError("The calculation's first argument must accept the input table")
        self.adapters, parameters = {}, {}
        hints = get_type_hints(fn, include_extras=True)
        for argument in arguments[1:]:
            if argument.kind not in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                raise ValueError("Calculation options must be named parameters")
            annotation = hints.get(argument.name)
            parameters[argument.name] = _parameter(annotation, argument.default)
            self.adapters[argument.name] = TypeAdapter(annotation)
        roles = {role: RoleSpec(kind="measure") for role in table.measures.values()}
        roles.update({role: RoleSpec(kind="dimension") for role in table.dimensions.values()})
        if table.entity:
            roles[table.entity] = RoleSpec(kind="entity")
        if set(roles) & set(parameters):
            raise ValueError("Binding roles and calculation options must have distinct names")
        packages = dict(requires_packages or {})
        if table.format == "dataframe":
            packages.setdefault("pandas", ">=2.2,<3")
        from packaging.requirements import Requirement
        for package, constraint in packages.items():
            requirement = Requirement(f"{package}{constraint}")
            if requirement.url or requirement.marker or requirement.extras or requirement.name != package:
                raise ValueError("Dependencies must use package names and version constraints")
        if any(not callable(validator) for validator in validators) or (adapt is not None and not callable(adapt)):
            raise ValueError("Validators and output adapter must be reviewed callables")
        self.fn, self.table, self.output, self.adapt = fn, table.model_copy(deep=True), output, adapt
        self.validators = tuple(validators)
        self.manifest = MethodManifest(name=name, version=version, description=inspect.getdoc(fn) or name,
            kind="stats", execution="dataframe", interpretation="association", roles=roles, parameters=parameters,
            outputs=[output.artifact_type], requires_packages=packages, requires_period=requires_period,
            requires_capabilities=["entity_grain_queries" if table.entity else "aggregate_queries"])

    async def run(self, ctx, bindings, params):
        kwargs = dict(measures={alias: bindings[role] for alias, role in self.table.measures.items()},
                      dimensions={alias: bindings[role] for alias, role in self.table.dimensions.items()})
        if self.table.entity:
            data = await ctx.entities(entity=bindings[self.table.entity], **kwargs)
        else:
            data = await ctx.aggregate(**kwargs)
        values = {key: self.adapters[key].validate_python(value) for key, value in params.items()}
        result = await ctx.compute(_evaluate, self.fn, data.records(), values, self.table,
                                   self.validators, self.output, self.adapt)
        result.runtime["calculation.function"] = f"{self.fn.__module__}.{self.fn.__qualname__}"
        result.runtime["calculation.input_mapping"] = self.table.model_dump_json()
        return result


def calculation(fn, *, name: str, version: str, table: InputTable, output=Table,
                adapt=None, validators=(), requires_packages=None, requires_period: bool = False) -> Method:
    """Adapt a native function without changing its body/signature; register the returned Method.

    Server workers require importable module-level functions. Notebook functions
    are for trusted local trials; move reviewed code into a package for deployment.
    """
    return CalculationMethod(fn, name=name, version=version, table=table, output=output, adapt=adapt,
                             validators=validators, requires_packages=requires_packages, requires_period=requires_period)
