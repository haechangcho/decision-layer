"""Public adapter for ordinary Python functions with governed data inputs.

Registration compiles a canonical manifest. Execution queries inputs, runs the
credential-free calculation worker and attaches evidence to the same MethodOutput.
"""

from __future__ import annotations

import inspect
import json
from hashlib import sha256

from .base import Method, MethodOutput
from .data_input import DataInput
from .function.registration import compile_function
from .function.inputs import query_inputs

# Retain these import paths for existing worker callers.
from .function.execution import _check_options, _execute_python


def _fingerprint(fn):
    try:
        return sha256(inspect.getsource(fn).encode()).hexdigest()
    except (OSError, TypeError):
        return "unavailable"


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
        self.manifest, self.adapters = compile_function(
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
            label=label,
        )
        self.fn = fn
        self.inputs = self.manifest.data_inputs
        self.checks = tuple(checks)
        self.option_checks = tuple(option_checks)
        self.output = output
        self.adapt = adapt

    async def run(self, ctx, bindings, params):
        validation = []

        options = {
            name: adapter.validate_python(params[name])
            for name, adapter in self.adapters.items()
            if name in params
        }
        if self.option_checks:
            validation = await ctx.compute(_check_options, self.option_checks, options)
            if any(check.status == "fail" for check in validation):
                return MethodOutput(validation=validation)

        rows, resolved = await query_inputs(
            ctx, self.inputs, self.manifest.roles, bindings, params
        )
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
                "python.inputs": json.dumps(
                    {k: v.model_dump() for k, v in self.inputs.items()}
                ),
            }
        )
        result.runtime["python.resolved_inputs"] = json.dumps(resolved)
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
    Column declarations matching function arguments inject resolved column names.
    Legacy DataInput.column_args remains supported. Clients select semantic refs,
    never raw columns. role="entity_key" declares the key in ordinary bindings.
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
