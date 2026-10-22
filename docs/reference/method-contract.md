# Method API

Look up arguments and options when registering a function. See [Connect a Python function](../tutorials/write-your-method) for the full flow.

## `python_method`

```python
from decision_layer.methods import Column, DataInput, Scope, python_method

method = python_method(
    function,
    name="my_team.analysis",
    version="1.0.0",
    inputs={"data": DataInput(columns={...})},
)
```

| Argument | Meaning |
|---|---|
| First argument | Python function to execute |
| `name`, `version` | Required Method name and version |
| `inputs` | Required mapping from data arguments to `DataInput` |
| `output` | Optional. Infer the shape by default, or select `"table"` or `"estimate"` |
| `requires_packages` | Required package versions, such as `{"statsmodels": ">=0.14,<0.16"}` |
| `checks` | Additional data checks |
| `option_checks` | Option checks executed before querying |
| `adapt` | Optional function converting the returned value to a supported shape |
| `provides` | Capability names used by Recipes and analysis goals |

Ordinary function arguments become calculation options, with types and defaults inferred from the signature. Use `parameters` for explicit overrides. The docstring supplies the Method description.

`requires_packages` checks installed versions; it does not install packages at runtime.

## `DataInput` and `Column`

Each `inputs` key names a function argument receiving a DataFrame. Declare a separate input for each table.

```python
inputs={
    "data": DataInput(
        columns={
            "value": Column(source="measure", dtype="number"),
            "group": Column(source="dimension"),
        },
        minimum_rows=10,
    ),
}
```

| `Column` option | Meaning |
|---|---|
| `source` | Required: `"measure"`, `"dimension"`, or a list allowing both |
| `dtype` | Require `"number"`, `"string"`, `"boolean"` or `"time"`; omitted means unrestricted |
| `multiple=True` | Select several metrics or dimensions; default `False` |
| `required=False` | Optional input; default `True` |
| `role="entity_key"` | Key identifying each row, such as customer or order ID |
| `description` | Explanation of the input |

An `entity_key` must be one required dimension declared as an entity key by the semantic provider. Each DataInput allows one. Selecting a key does not establish statistical independence.

Function arguments matching declared columns receive DataFrame column names. Multiple columns receive names such as `confounders_0`, `confounders_1` and are passed as a list. Select actual Cube references through `bindings` at execution time.

| Common `DataInput` option | Meaning |
|---|---|
| `minimum_rows` | Minimum row count; default `1` |
| `format` | Default `"dataframe"`; `"records"` provides a list of row dicts |
| `time_granularity` | Query by `"day"`, `"week"`, `"month"`, `"quarter"` or `"year"` |
| `period_parameter` | Option naming a comparison date range |
| `period_role="comparison"` | Query a separately selected comparison period |
| `filters_parameter` | Option supplying additional query filters |

## Return values

| Function result | Adaptation |
|---|---|
| DataFrame or list of row dicts | Table with default settings |
| Number | Estimate with default settings |
| `{"value": number, ...}` | Estimate by default: `value` is the primary estimate; other fields are details |
| Other dict | One-row table with default settings |

Usually, omit `output`. Use `output="table"` to keep a dict with a numeric `value` as a table. Booleans, strings and `None` do not count as numeric values. Non-finite numeric results are rejected.

Explicit `output="table"` and `output="estimate"` take precedence over inference. Values that cannot be converted to the selected shape raise an error. Convert unsupported external-library objects inside the function or through `adapt`.

## Checks and errors

Decision Layer checks required inputs, types and declared data conditions. Each Method does not need its own handling for those checks.

- `checks` run after querying and before calculation. Arguments use the DataInput names.
- `option_checks` receive only calculation options and run before querying.
- Returning `False` or raising `ValueError` or `AssertionError` records a failed check and stops calculation. `None` or `True` passes.
- Exceptions in the calculation function itself propagate as Python errors. Programming failures are not successful results.

## Local sessions

| API | Purpose |
|---|---|
| `session.register(method)` | Add a Method to the session |
| `session.list_methods()` | List registered manifests |
| `await session.run(name, bindings=..., params=..., scope=...)` | Execute locally and inspect the result |

`bindings` selects semantic references; `params` supplies calculation options. Use `Scope(date_range=(start, end), time_dimension=date_reference)` for dates.

Inspect `trial.result` and `trial.attempts` for results and query attempts. Trials are not automatically stored on the server. Continue with [Register in a project](../guides/method-projects.md) for service use.

For advanced control over queries, see the [SDK examples](https://github.com/haechangcho/decision-layer/blob/main/tests/support/methods/functions.py). See the [implementation](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/python.py) for the complete registration signature.
