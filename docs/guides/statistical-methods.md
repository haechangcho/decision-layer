# Statistical Methods with ordinary Python

New Method authors declare data roles and use native library APIs. They do not need an `AnalysisDesign` object, assumption checkboxes, seed input or direct manifest manipulation. Python calls use the same argument names as the function. Internal contracts still govern semantic access, scope, limits and provenance.

## Install once

Optional libraries are installed in the development/server environment, never during Method execution. Use the tested Python 3.11 constraints; actual runtime versions are recorded.

```bash
python3.11 -m venv .venv-method
.venv-method/bin/python -m pip install -c examples/methods/patterns/constraints-py311.txt -e '.[dev,stats,dowhy,econml]'
```
## Register and use

Use a fresh fixture session or a real Cube connection. The four data roles are outcome, treatment, confounders and unit; current period and shared filters belong to execution scope.

```python
from decision_layer.methods import Scope, register_builtins
from examples.methods.patterns.scenarios import M, TREAT, BASELINE, UNIT, DATE, FEB

register_builtins(session.registry)
trial = await session.run(
    "stats.binary_regression",  # Use "stats.linear_dml" for constant binary DML.
    outcome=M,
    treatment=TREAT,
    confounders=[BASELINE],
    unit=UNIT,
    scope=Scope(FEB, DATE),
)
print(trial.result.primary.data)
```
Measure confounders can be passed directly under `confounders`; the catalog determines which fields become native measures or dimensions. Map-style and legacy canonical inputs remain accepted for REST/MCP and existing Recipes.

## Author with the native library API

Write ordinary Python calculation functions, use `ctx.entities` for governed extraction and `ctx.compute` for computation. The calculation also accepts a DataFrame without Decision Layer. DoWhy calls remain explicit:

```python
from dowhy import CausalModel

model = CausalModel(data=observations, treatment="treatment", outcome="outcome", graph=graph)
estimand = model.identify_effect(proceed_when_unidentifiable=False)
estimate = model.estimate_effect(
    estimand, method_name="backdoor.linear_regression",
    control_value=0, treatment_value=1, target_units="ate", confidence_intervals=False,
)
```

The hands-on `examples/methods/patterns/write_your_method.en.ipynb` contains native DoWhy calculation and a small Method wrapper. Reviewed server functions must live in importable Python modules. No generic estimator facade is required.

<<< @/../src/decision_layer/methods/advanced.py#binary_regression

## Data checks and interpretation

Check primary unit, non-null unique keys, finite values, missingness, treatment groups, bounded encoding, regression rank and observed support. Native binary regression requires at least 30 observations per arm and fitted propensities in [0.05, 0.95]; these thresholds are diagnostics, not proof of positivity. DML has its own fit conditions. Inadequate data refuses estimation.

The reviewed Methods always report association, `assumptions_status="not_verified"` and `causal_claim="not_established"`. They record the assumed graph, estimator, contrast, fixed seed/folds and diagnostics where applicable. No confidence interval is reported. A graph, refutation or a note does not establish identification. Treatment/covariate timing, unmeasured confounding, independence and interference still need evidence before any causal claim. Notes cannot override validation or semantic definitions.

## Two-period group contrast

`stats.two_period_contrast` requires a complete unit × time panel with exactly two ordered buckets, fixed treatment groups and finite outcomes. The earlier bucket is pre and later bucket is post; a longer panel refuses rather than silently choosing endpoints. Parallel trends are not claimed. Optional `windows` partitions extraction without overlap; `granularity` controls the requested month/day buckets. These are meaningful data-shape inputs, not assumption flags.

## Compatibility

`stats.adjusted_difference`, `stats.dml` and `stats.did` retain their original 1.0.0 contracts for pinned Recipes. Their old design-object schema is compatibility-only, not the authoring API. New callers use `stats.binary_regression`, `stats.linear_dml` and `stats.two_period_contrast`. Existing Runs and versions are not rewritten or automatically aliased.

## Python, pytest and notebook

Use the same calculation in Python and pytest; the optional notebook shows writing, registration, direct arguments and table results. Local calculation stays in the caller process for debugging. Server calculation uses the existing bounded child process without provider credentials; it is not an arbitrary-code sandbox. See [manual scenarios](method-scenarios.md).
