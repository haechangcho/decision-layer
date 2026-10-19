# Write a Python Method

Write an ordinary Python function and declare the data it needs. Decision Layer
queries the selected data, passes it to your function and records server execution in a Run.

Start with the [Method authoring notebook](https://github.com/haechangcho/decision-layer/blob/main/docs/tutorials/methods/write_your_method.en.ipynb).
It walks through ranking and OLS, registration and execution on prepared data.

## Define the function and its inputs

This function ranks the `value` column. `DataInput` declares a metric and a grouping
dimension. Choose the actual revenue metric and product dimension at execution time.

```python
from decision_layer.methods import Column, DataInput, python_method


def rank_values(data, descending=True):
    """Rank groups by the selected metric, retaining ties."""
    return data[["group", "value"]].assign(
        rank=data["value"].rank(method="min", ascending=not descending)
    )


METHOD = python_method(
    rank_values,
    name="my_team.rank",
    version="1.0.0",
    inputs={
        "data": DataInput(columns={
            "value": Column(source="measure"),
            "group": Column(source="dimension"),
        }),
    },
)
```

- `python_method` combines the function, name, version and input contract.
- `Column` declares a queried column. A function argument with the same name receives its resolved column name.
- `descending` becomes a calculation option inferred from the function default.
- `METHOD` is the object the project loader reads from the file.

Return a DataFrame, number or dict. The default `output="auto"` adapts tables and
estimates. Set `output="table"` or `output="estimate"` to require one result shape.

## Declare the analysis inputs

| Declaration | Meaning |
| --- | --- |
| `Column(source="measure")` | Select a metric |
| `Column(source="dimension")` | Select a dimension |
| `Column(source=["measure", "dimension"])` | Accept either kind |
| `Column(source="dimension", role="entity_key")` | Define each row by a key, such as customer or order ID |
| `Column(source="measure", dtype="number")` | Require numeric data |
| `Column(source="dimension", multiple=True)` | Select several variables |
| `DataInput(..., minimum_rows=10)` | Require at least ten queried rows |

Shared code checks missing bindings, semantic kinds and declared data constraints.
Review analysis-specific assumptions yourself. Use normal Python exceptions when
the function cannot continue, or register `checks=[check_function]` to record a
failed check as structured validation.

## Use the registered Method

Continue with [Use a Method project](method-projects.md) for files, CLI checks,
the admin UI and AI connections.

AI discovers installed Methods through `list_methods` and `find_methods`, and reads
input contracts with `describe_method`. It selects metrics and dimensions from the
semantic catalog and asks the user when meaning or period is ambiguous.

Before writing another calculation, check whether a [Recipe](recipes.md) can
compose existing Methods. See [Method contracts](../reference/method-contract.md)
for the advanced API that controls multiple semantic queries directly.
