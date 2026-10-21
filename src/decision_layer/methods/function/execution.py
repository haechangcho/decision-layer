"""Worker-side input validation, calculation and result adaptation.

Only rows, contracts and reviewed callables cross this boundary; no provider client
or credentials are passed into calculation functions.
"""

from __future__ import annotations

import math
import inspect
from ...core.models import ValidationResult
from ..base import MethodOutput
from ..output import Estimate, Table


def run_checks(checks, arguments, *, option_checks=False, column_args=None):
    """Stop at the first failed check; programming errors still propagate."""
    code = "PYTHON_OPTION_CHECK" if option_checks else "PYTHON_CHECK"
    passed_message = (
        "Executed option check passed" if option_checks else "Executed check passed"
    )
    failed_message = (
        "Executed option check failed" if option_checks else "Executed check failed"
    )
    type_error = (
        "Option checks must return None/bool"
        if option_checks
        else "Checks must return None/bool or raise ValueError/AssertionError"
    )
    validation = []
    for check in checks:
        try:
            inputs = dict(arguments)
            if column_args:
                parameters = inspect.signature(check).parameters
                inputs.update(
                    {
                        name: value
                        for name, value in column_args.items()
                        if name in parameters
                    }
                )
            returned = check(**inputs)
            if returned is not None and returned is not True and returned is not False:
                raise TypeError(type_error)
            passed = returned is not False
            message = passed_message if passed else failed_message
        except (ValueError, AssertionError) as exc:
            passed = False
            message = str(exc) if option_checks else str(exc) or failed_message
        validation.append(
            ValidationResult(
                validator=f"{check.__module__}.{check.__qualname__}",
                code=code,
                status="pass" if passed else "fail",
                message=message,
            )
        )
        if not passed:
            break
    return validation


def _check_options(checks, options):
    return run_checks(checks, options, option_checks=True)


def prepare_inputs(rows_by_name, inputs, resolved=None):
    data, validation, column_args = {}, [], {}
    for name, spec in inputs.items():
        rows = rows_by_name[name]
        entity_alias = spec.entity if spec.entity in spec.columns else "unit"
        columns = [
            *([entity_alias] if spec.entity else []),
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
        numeric_columns = contract.get("numeric_columns", [])
        if numeric_columns:
            record(
                "FINITE_NUMERIC_COLUMNS",
                all(
                    isinstance(row.get(col), (int, float))
                    and not isinstance(row.get(col), bool)
                    and math.isfinite(row[col])
                    for row in rows
                    for col in numeric_columns
                ),
                f"{name}: numeric columns finite and non-null.",
            )
        keys = [entity_alias] if spec.entity else list(spec.dimensions)
        if spec.time_granularity:
            keys.append("time")
        keys = contract.get("grain_keys", keys)
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
    return data, column_args, validation


def adapt_result(value, output):
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
    return result


def _execute_python(
    fn, rows_by_name, inputs, options, checks, output, adapt, resolved=None
):
    data, column_args, validation = prepare_inputs(rows_by_name, inputs, resolved)
    if any(item.status == "fail" for item in validation):
        return MethodOutput(validation=validation)
    validation.extend(run_checks(checks, data, column_args=column_args))
    if any(item.status == "fail" for item in validation):
        return MethodOutput(validation=validation)
    value = fn(**data, **column_args, **options)
    if adapt:
        value = adapt(value)
    result = adapt_result(value, output)
    result.validation = [*validation, *result.validation]
    result.warnings.append(
        "Input checks do not establish source completeness, metric equivalence or causal identification."
    )
    return result
