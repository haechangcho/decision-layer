# Write, run and test your first Method

Write one ordinary Python function and register it explicitly. Definitions, joins and permissions stay in the semantic layer. These examples use implemented APIs, not proposed pseudocode. Existing class Methods remain supported.

To try **writing and editing your own Method**, open `examples/methods/patterns/write_your_method.en.ipynb` in VS Code/Jupyter. It contains function definition → registration → input selection → result inspection → code editing, rather than only running prepared scenarios. The Korean notebook has identical code. The final opt-in cell uses the same authored functions against your current Cube.

## 1. Start without a live connection

Run from the repository root. This first test needs Python 3.11+ and core dependencies; cases requiring statistical libraries are skipped.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m examples.methods.patterns --case by_group
.venv/bin/python -m pytest -q examples/methods/patterns/test_patterns.py
```

## 2. Write the function

`Measure` and `Dimension` receive references to existing semantic objects. `ctx` applies periods, filters, permissions and limits. The signature generates the manifest, avoiding duplicate role declarations and argument mapping. This is the tested source.

<<< @/../examples/methods/patterns/methods.py#group_metric

### How AI requests and Python calls supply inputs

Example request: “Show the top 3 departments by receipt count for store 364 in February 2001.”

The AI finds the receipt-count measure and department dimension in the semantic layer and fills these inputs:

- `metric`: path to the model and its receipt-count measure
- `group`: path to the model and its department dimension
- `limit`: the requested 3; uses the function default when omitted
- `scope`: February 2001, date basis and the store 364 filter

For example, `cube://journey/transaction/receipts` names:

- `cube://`: the Cube semantic provider
- `journey`: the configured Cube instance
- `transaction`: the Cube model
- `receipts`: a measure defined in that model

Once connected to Cube, find this path in the catalog and pass it to `run(metric=...)`. It is not a database table or SQL column path. You can also pass `cube://journey/product/department` from another model as `group`; Cube decides whether the models can be joined and how. In the practice path `cube://practice/observations/value`, `practice` names the practice connection and `observations` and `value` are names in the practice catalog.

In Python, pass `metric`, `group`, `limit` and `scope` directly to `run(...)`. At execution time:

- The value passed to `run(metric=...)` reaches the Method function as `metric`. `group` and `limit` work the same way.
- The period and filters in `scope` become part of `ctx`. `ctx.aggregate(...)` applies them to the query.
- The session's data connection, permissions and execution limits are used by `ctx` when it queries.

Missing or ambiguous inputs are handled as follows:

- If the requested metric or period is unclear, the AI asks the user.
- If the runtime returns `needs_input`, the AI relays its question.
- Missing required Method arguments cause an input error.

The Method uses `ctx.aggregate(...)` to query with the resolved period, filters, permissions and limits.

Python calls execute directly and do not conduct a conversation. The AI uses the registered Method's declared inputs when preparing MCP calls. It sends the analysis scope when creating the Run and Method arguments in its execution step; both reach the same execution context and registry. A required annotation declares a required input, not an automatically generated chat question. A Method may raise `NeedsInput` for an analytical choice it cannot resolve; the caller must obtain the answer and retry with valid inputs. Defaults are used only when supported by the Method or Recipe. Connection credentials and permission rules come from the configured execution environment.


## 3. Register, execute and verify

Run this in a notebook cell or an async function. `FixtureProvider` compares the entire request with an independently written `DatasetSpec`; it does not copy the Method request as its oracle. Incorrect query conditions fail even when numbers look right.

```python
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope
from examples.methods.patterns.methods import group_metric
from examples.methods.patterns.scenarios import scenarios, M, GROUP, DATE, FEB

scenario = next(s for s in scenarios() if s.name == "by_group")
provider = scenario.provider()
session = await MethodSession.fixture(provider)
session.register(group_metric)
trial = await session.run(
    group_metric,
    metric=M, group=GROUP,
    scope=Scope(FEB, DATE), limit=3,
)
assert [r["metric"] for r in trial.result.primary.data] == [30, 20, 10]
provider.assert_consumed()
print(trial.queries)
print([(a.label, a.status) for a in trial.attempts])
session.close()
```

## 4. Connect a real semantic source

```python
import os
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope, Filter
from decision_layer.semantic.credentials import RequestCredentials

session = await MethodSession.cube(
    os.environ["CUBE_API_URL"], RequestCredentials(os.environ["CUBE_TOKEN"]),
    instance="journey",
)
metrics = session.catalog.search(kind="measure", text="sales")
metric = metrics[0].ref  # Inspect titles/definitions before choosing.
print(session.object(metric))
print(session.catalog.relations(metric))  # declared or unknown, not a join guarantee
print(session.catalog.search(kind="dimension", text="department", compatible_with=metric))
print(session.catalog.search(kind="time_dimension"))
# Copy actual references from this caller-visible catalog into the invocation.
# session.register(group_metric)
# trial = await session.run(group_metric, metric=metric,
#     group=selected_dimension,
#     scope=Scope(selected_period, selected_time),
#     filters=[Filter(member=selected_filter_dimension, operator="equals", values=[selected_value])])
session.close()
```

Discovery returns caller-visible objects. `compatible_with` validates the reference as a discovery hint; it does not remove unknown joins or guarantee queryability. The provider validates actual combinations.

## 5. Edit, debug and share

After editing, use `session.register(group_metric, replace=True)`. Ordinary breakpoints work; inspect `session.last_trial.attempts` for successful/failed requests and labels. Direct execution stays in the caller process and is not a stored Run. `session.preview(recipe, step_index=..., scope=...)` executes a fresh Recipe prefix through the same RunEngine.

For deployment, install reviewed modules in the server environment and register them in server bootstrap. Import does not register automatically; Web cannot upload Python. Use a Recipe to compose existing Methods into an organizational investigation.

Next: [authoring patterns](method-patterns.md), [manual scenarios](method-scenarios.md), [advanced analysis](statistical-methods.md), [internal contract](../reference/method-contract.md).
